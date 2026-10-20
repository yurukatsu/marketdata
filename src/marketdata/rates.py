import pandas as pd

from .configs import Instrument


def curve_asof(history: pd.DataFrame, date: str | pd.Timestamp) -> pd.Series:
    """列ごとの利回り時系列から、date 当日または直前の営業日の値を取り出す。

    返り値の name は実際に使った日付（全列で最も新しい日付）。祝日などで欠ける列は前日値で埋める。
    """
    data = history.copy()
    data.index = pd.to_datetime(data.index)
    upto = data.sort_index().loc[: pd.Timestamp(date)].dropna(how="all")
    if upto.empty:
        raise ValueError(f"{date} 以前の利回りデータがありません。")
    return upto.ffill().iloc[-1].rename(upto.index[-1])


def rates_summary(
    short_history: pd.DataFrame,
    long_history: pd.DataFrame,
    short_instruments: list[Instrument],
    base_date: str | pd.Timestamp,
    compare_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """国別の短期（2年）・10年・タームスプレッドの水準と変化幅の表。

    列: short_tenor, short, short_chg_bp, long, long_chg_bp, spread_bp, spread_chg_bp
    index は long_history の列順（国名）。短期がない国は NaN。
    """
    countries = list(long_history.columns)
    short_now = curve_asof(short_history, base_date).reindex(countries)
    short_prev = curve_asof(short_history, compare_date).reindex(countries)
    long_now = curve_asof(long_history, base_date).reindex(countries)
    long_prev = curve_asof(long_history, compare_date).reindex(countries)

    table = pd.DataFrame(
        {
            "short_tenor": pd.Series({i.name: i.tenor or "2Y" for i in short_instruments}),
            "short": short_now,
            "short_chg_bp": (short_now - short_prev) * 100,
            "long": long_now,
            "long_chg_bp": (long_now - long_prev) * 100,
            "spread_bp": (long_now - short_now) * 100,
            "spread_chg_bp": ((long_now - short_now) - (long_prev - short_prev)) * 100,
        }
    ).reindex(countries)
    table.index.name = "country"
    table.attrs["base_date"] = long_now.name
    table.attrs["compare_date"] = long_prev.name
    return table
