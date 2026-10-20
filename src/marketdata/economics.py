"""経済指標の発表カレンダー（LSEG Search API の INDICATOR_QUOTES ビュー + 履歴値）。"""

from datetime import timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

from .client import LSEGClient
from .configs import Instrument, load_universe
from .paths import CONFIG_DIR

SEARCH_FIELDS = "RIC,NextReleaseDate,PreviousReleaseDate,Frequency"


IndicatorSet = dict[str, list[Instrument]]  # 国名 -> 指標リスト


def load_indicators(path: Path = CONFIG_DIR / "econ_indicators.yaml") -> IndicatorSet:
    """国名 -> 指標リスト。yaml の並び順が表の並び順になる。"""
    return load_universe(path)


def _search_release_dates(rics: list[str], chunk_size: int = 40) -> pd.DataFrame:
    frames = []
    for i in range(0, len(rics), chunk_size):
        chunk = rics[i : i + chunk_size]
        flt = " or ".join(f"RIC eq '{r}'" for r in chunk)
        frames.append(
            ld.discovery.search(
                view=ld.discovery.Views.INDICATOR_QUOTES,
                filter=flt,
                select=SEARCH_FIELDS,
                top=len(chunk) * 2,
            )
        )
    df = pd.concat(frames, ignore_index=True).drop_duplicates("RIC")
    for col in ["NextReleaseDate", "PreviousReleaseDate"]:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None).dt.normalize()
    return df.set_index("RIC")


def _latest_values(rics: list[str], start: str, end: str, chunk_size: int = 50) -> pd.DataFrame:
    """RIC ごとの直近2回の値と対象期間。"""
    rows = {}
    for i in range(0, len(rics), chunk_size):
        chunk = rics[i : i + chunk_size]
        hist = ld.get_history(universe=chunk, fields=["VALUE"], start=start, end=end)
        if len(chunk) == 1:
            hist.columns = chunk
        hist.index = pd.to_datetime(hist.index)
        for ric in chunk:
            s = hist[ric].dropna() if ric in hist else pd.Series(dtype=float)
            rows[ric] = {
                "last_value": s.iloc[-1] if len(s) else None,
                "last_period": s.index[-1] if len(s) else pd.NaT,
                "prev_value": s.iloc[-2] if len(s) > 1 else None,
                "prev_period": s.index[-2] if len(s) > 1 else pd.NaT,
            }
    return pd.DataFrame.from_dict(rows, orient="index")


def fetch_release_calendar(
    client: LSEGClient,
    indicators: IndicatorSet,
    end: str | pd.Timestamp,
    lookback_days: int = 550,
) -> pd.DataFrame:
    """指標ごとの次回・前回発表日と、直近2回の値（対象期間つき）。"""
    client.open()
    meta = []
    for country, items in indicators.items():
        for i in items:
            meta.append(
                {
                    "country": country,
                    "indicator": i.name,
                    "ric": i.ticker,
                    "unit": i.unit or "",
                    "order": len(meta),  # yaml の並び順
                }
            )
    df = pd.DataFrame(meta)
    rics = df["ric"].tolist()

    end_ts = pd.Timestamp(end)
    dates = _search_release_dates(rics)
    values = _latest_values(
        rics, f"{end_ts - timedelta(days=lookback_days):%Y-%m-%d}", f"{end_ts:%Y-%m-%d}"
    )
    df = df.join(dates, on="ric").join(values, on="ric")
    return df.rename(
        columns={
            "NextReleaseDate": "next_release",
            "PreviousReleaseDate": "previous_release",
            "Frequency": "frequency",
        }
    )


def releases_in_window(
    calendar: pd.DataFrame,
    base_date: str | pd.Timestamp,
    days: int = 7,
) -> pd.DataFrame:
    """基準日から days 日間（base_date <= 発表日 < base_date + days）の発表一覧。

    未発表 = 予定（前回値を表示）、窓の中で発表済み = 発表済（実績と前回値を表示）。
    日付 → yaml の並び順（国・指標）でソートする。
    """
    start = pd.Timestamp(base_date).normalize()
    end = start + timedelta(days=days)

    upcoming = calendar[(calendar["next_release"] >= start) & (calendar["next_release"] < end)]
    released = calendar[
        (calendar["previous_release"] >= start) & (calendar["previous_release"] < end)
    ]
    rows = pd.concat(
        [
            upcoming.assign(
                date=upcoming["next_release"],
                event="予定",
                actual=None,
                previous=upcoming["last_value"],
                period=upcoming["last_period"],
            ),
            released.assign(
                date=released["previous_release"],
                event="発表済",
                actual=released["last_value"],
                previous=released["prev_value"],
                period=released["last_period"],
            ),
        ],
        ignore_index=True,
    )
    cols = ["date", "event", "country", "indicator", "actual", "previous", "period", "unit"]
    return rows.sort_values(["date", "order"]).reset_index(drop=True)[[*cols, "frequency", "ric"]]
