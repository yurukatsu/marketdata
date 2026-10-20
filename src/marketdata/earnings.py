import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .client import LSEGClient
from .labels import COUNTRY_JA, GICS_SECTOR_JA, to_ja
from .paths import REFERENCE_DIR

# 次回: I/B/E/S の予定日（FI1 = 次の決算。中間・四半期を含む）
# 直近: ファンダメンタルの実際の発表日（FI0 = 直近の決算）。
#       香港・インドなどで欠ける銘柄は I/B/E/S の実績発表日で補完する
EARNINGS_FIELDS = {
    "TR.RIC": "ric",
    "TR.CommonName": "company",
    # 本社所在国（上場国ではない。香港上場の中国企業は China）
    "TR.HeadquartersCountry": "country_en",
    "TR.GICSSector": "sector_en",
    "TR.ExpectedReportDate(Period=FI1)": "next_date",
    "TR.ExpectedReportDate(Period=FI1).periodenddate": "next_period_end",
    "TR.F.OriginalAnnouncementDate(Period=FI0)": "last_date",
    "TR.F.PeriodEndDate(Period=FI0)": "last_period_end",
    "TR.EPSActReportDate(Period=FI0)": "ibes_last_date",
    "TR.EPSActReportDate(Period=FI0).periodenddate": "ibes_last_period_end",
}
DATE_COLUMNS = [v for v in EARNINGS_FIELDS.values() if v.endswith(("_date", "_period_end"))]


def load_benchmark(path: Path = REFERENCE_DIR / "bm.csv") -> pd.DataFrame:
    """ベンチマーク構成銘柄を読み込む。

    CSV の weight は "0.10%" と小数第2位で丸められているため、
    cap 比率から計算し直す（丸め後の値とは ±0.005% 以内で一致）。
    """
    bm = pd.read_csv(path, dtype={"sedol": str}, encoding="utf-8-sig")
    bm["weight"] = bm["cap"] / bm["cap"].sum()
    return bm


def fetch_earnings_dates(
    client: LSEGClient,
    sedols: list[str],
    chunk_size: int = 50,
    retries: int = 3,
) -> pd.DataFrame:
    """SEDOL ごとに次回・直近の決算発表日を取得する。"""
    frames = []
    for i in range(0, len(sedols), chunk_size):
        universe = [f"{s}@SEDOL" for s in sedols[i : i + chunk_size]]
        for attempt in range(retries):
            try:
                frames.append(client.get_data(universe=universe, fields=list(EARNINGS_FIELDS)))
                break
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)

    df = pd.concat(frames, ignore_index=True)
    # 列名が重複する（Period End Date が2つ）ので位置でリネームする
    expected = ["sedol", *EARNINGS_FIELDS.values()]
    if len(df.columns) != len(expected):
        raise ValueError(f"想定外の列: {list(df.columns)}")
    df.columns = expected
    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    missing = df["last_date"].isna()
    df.loc[missing, "last_date"] = df.loc[missing, "ibes_last_date"]
    df.loc[missing, "last_period_end"] = df.loc[missing, "ibes_last_period_end"]

    df["country"] = to_ja(df["country_en"], COUNTRY_JA)
    df["sector"] = to_ja(df["sector_en"], GICS_SECTOR_JA)
    return df.drop(columns=["ibes_last_date", "ibes_last_period_end"])


def earnings_in_window(
    dates: pd.DataFrame,
    bm: pd.DataFrame,
    base_date: str | date,
    days: int = 7,
) -> pd.DataFrame:
    """基準日から days 日間（base_date <= 発表日 < base_date + days）に決算発表がある銘柄を返す。

    日付の昇順、同日内は benchmark weight の降順でソートする。
    """
    start = pd.Timestamp(base_date).normalize()
    end = start + timedelta(days=days)

    info = ["sedol", "ric", "company", "country", "sector"]
    events = pd.concat(
        [
            dates[[*info, "next_date", "next_period_end"]]
            .rename(columns={"next_date": "datetime", "next_period_end": "period_end"})
            .assign(event="次回（予定）"),
            dates[[*info, "last_date", "last_period_end"]]
            .rename(columns={"last_date": "datetime", "last_period_end": "period_end"})
            .assign(event="直近（実績）"),
        ],
        ignore_index=True,
    ).dropna(subset=["datetime"])
    events["date"] = events["datetime"].dt.normalize()

    in_window = events[(events["date"] >= start) & (events["date"] < end)]
    # 発表直後は次回予定日がまだ更新されず実績と重なることがあるので、同一銘柄・同日は1件にする
    in_window = in_window.drop_duplicates(subset=["sedol", "date"], keep="last")

    return (
        in_window.merge(bm[["sedol", "isin", "name", "weight", "cap"]], on="sedol", how="left")
        .sort_values(["date", "weight"], ascending=[True, False])
        .reset_index(drop=True)[
            [
                "date",
                "event",
                "name",
                "country",
                "sector",
                "weight",
                "cap",
                "period_end",
                "datetime",
                "ric",
                "sedol",
                "isin",
            ]
        ]
    )


def season_end_date(dates: pd.DataFrame, base_date: str | date) -> pd.Timestamp:
    """基準日直前の四半期末を決算期とする銘柄の、次回予定日の最終日（= 決算シーズンの終わり）。"""
    base = pd.Timestamp(base_date).normalize()
    quarter_end = base - pd.offsets.QuarterEnd()
    upcoming = dates[(dates["next_date"] >= base) & (dates["next_period_end"] == quarter_end)]
    if upcoming.empty:
        raise ValueError(f"{quarter_end:%Y-%m-%d} 期の次回予定日がありません。")
    return upcoming["next_date"].max().normalize()


def next_earnings_counts(
    dates: pd.DataFrame,
    bm: pd.DataFrame,
    base_date: str | date,
    end_date: str | date | None = None,
) -> pd.DataFrame:
    """基準日〜end_date（省略時は決算シーズンの終わり）の次回予定日を日別に集計する。

    返り値: index=date（期間中の全日付）、列 count / weight（weight 合計）
    """
    start = pd.Timestamp(base_date).normalize()
    end = pd.Timestamp(end_date) if end_date else season_end_date(dates, start)

    upcoming = dates.assign(date=dates["next_date"].dt.normalize()).merge(
        bm[["sedol", "weight"]], on="sedol", how="left"
    )
    upcoming = upcoming[(upcoming["date"] >= start) & (upcoming["date"] <= end)]
    return (
        upcoming.groupby("date")
        .agg(count=("sedol", "size"), weight=("weight", "sum"))
        .reindex(pd.date_range(start, end, name="date"), fill_value=0)
    )
