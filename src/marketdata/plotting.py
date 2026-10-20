"""レポート用の図（matplotlib）。

Chrome 等の外部ブラウザに依存せず、EC2 などのヘッドレス環境でも PNG を出力できる。
日本語フォントはパッケージ同梱の Noto Sans JP（Regular / Bold, SIL OFL）を使う。
"""

import itertools
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.dates import DateFormatter, WeekdayLocator
from matplotlib.figure import Figure
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

for _font in (Path(__file__).parent / "fonts").glob("*.ttf"):
    font_manager.fontManager.addfont(_font)

COLORS = {
    "positive": "#2a78d6",
    "negative": "#e34948",
    "benchmark": "#3d3d3a",
    "bar": "#2a78d6",
    "bar_muted": "#b7d3f6",
    "text": "#0b0b0b",
    "text_secondary": "#52514e",
    "text_muted": "#8f8e8a",
    "grid": "#e6e5e1",
    "band": "#f3f2ef",
    "surface": "#ffffff",
    "badge_plan": "#dbe9fb",
    "badge_plan_text": "#184f95",
    "badge_actual": "#efeeea",
    "badge_actual_text": "#52514e",
}
SOURCE = "出所：LSEG"
WEEKDAYS = "月火水木金土日"

# PowerPoint 16:9 スライドに貼りやすいサイズ（12.8 x 7.2 inch x 200 dpi = 2560 x 1440 px）
FIGSIZE = (12.8, 7.2)
DPI = 200

plt.rcParams.update(
    {
        "font.family": "Noto Sans JP",
        "font.size": 12,
        "text.color": COLORS["text"],
        "axes.labelcolor": COLORS["text_secondary"],
        "axes.edgecolor": COLORS["grid"],
        "axes.facecolor": COLORS["surface"],
        "figure.facecolor": COLORS["surface"],
        "xtick.color": COLORS["text_muted"],
        "ytick.color": COLORS["text_muted"],
    }
)


def _header(fig: Figure, title: str, subtitle: str = "", source: str | None = SOURCE) -> None:
    """太字タイトル（メッセージ）＋ グレーのサブタイトル ＋ 左下の出所。"""
    fig.text(0.02, 0.955, title, fontsize=22, weight="bold", va="top")
    if subtitle:
        fig.text(0.02, 0.885, subtitle, fontsize=13, color=COLORS["text_secondary"], va="top")
    if source:
        fig.text(0.02, 0.02, source, fontsize=10, color=COLORS["text_muted"], va="bottom")


def _new_figure(title: str, subtitle: str, source: str | None) -> tuple[Figure, plt.Axes]:
    # 上部 15% をタイトル、下部 5% を出所用に空ける
    fig = plt.figure(figsize=FIGSIZE, layout=ConstrainedLayoutEngine(rect=(0.01, 0.05, 0.98, 0.80)))
    ax = fig.add_subplot()
    _header(fig, title, subtitle, source)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig, ax


def _md(d: pd.Timestamp) -> str:
    return f"{d.month}/{d.day}"


def period_returns(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """列ごとに start〜end の単純リターンを計算する。

    起点は start 当日、または直前の営業日の終値（休場日でも前週末比などになるように）。
    """
    data = df.copy()
    data.index = pd.to_datetime(data.index)
    data = data.sort_index().ffill()

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    before_start = data.loc[:start_ts]
    if before_start.empty:
        raise ValueError(f"{start} 以前のデータがありません。取得開始日を前倒ししてください。")
    upto_end = data.loc[:end_ts]

    result = pd.DataFrame(
        {
            "start_date": before_start.apply(lambda s: s.last_valid_index()),
            "start_value": before_start.iloc[-1],
            "end_date": upto_end.apply(lambda s: s.last_valid_index()),
            "end_value": upto_end.iloc[-1],
        }
    )
    result["return"] = (
        result["end_value"].div(result["start_value"]).sub(1).replace([np.inf, -np.inf], np.nan)
    )
    result.index.name = "name"
    return result.dropna(subset=["return"]).sort_values("return", ascending=False)


def plot_returns(
    returns: pd.DataFrame,
    title: str,
    subtitle: str = "",
    highlight: str | None = None,
    reference: tuple[str, float] | None = None,
    source: str | None = SOURCE,
) -> Figure:
    """period_returns の結果を降順の横棒グラフにする。

    プラス=青、マイナス=赤。highlight の行（ベンチマーク）はダークグレーで描き、
    そのリターンに参照線を引く。reference=(ラベル, 値) で参照線だけ指定することもできる。
    """
    r = returns.sort_values("return")  # barh は下から描画されるので昇順で渡す
    names, values = list(r.index), r["return"].to_numpy()
    colors = [
        COLORS["benchmark"]
        if n == highlight
        else COLORS["positive"]
        if v >= 0
        else COLORS["negative"]
        for n, v in zip(names, values, strict=True)
    ]
    if highlight in r.index and reference is None:
        reference = (highlight, r.loc[highlight, "return"])

    fig, ax = _new_figure(title, subtitle, source)
    y = np.arange(len(r))
    ax.barh(y, values, color=colors, height=0.62, zorder=2)
    ax.axvline(0, color=COLORS["text_secondary"], linewidth=1, zorder=3)

    span = max(abs(values).max(), 1e-6)
    ax.set_xlim(min(values.min(), 0) - span * 0.16, max(values.max(), 0) + span * 0.16)
    ax.set_ylim(-0.6, len(r) - 0.4 + (0.7 if reference else 0))

    if reference:
        label, value = reference
        ax.axvline(value, color=COLORS["text_muted"], linewidth=1, zorder=1)
        ax.text(
            value,
            len(r) - 0.3,
            f"{label} {value:+.2%}",
            ha="center",
            va="bottom",
            fontsize=11,
            color=COLORS["text_secondary"],
            bbox={"fc": COLORS["surface"], "ec": "none", "pad": 2},
            zorder=4,
        )

    # 値ラベルを棒の先に置くので x 軸は出さない
    offset = span * 0.012
    for yi, n, v in zip(y, names, values, strict=True):
        ax.text(
            v + (offset if v >= 0 else -offset),
            yi,
            f"{v:+.2%}",
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=12,
            weight="bold" if n == highlight else "normal",
            color=COLORS["text"],
        )
    ax.set_xticks([])
    ax.set_yticks(y, names)
    ax.tick_params(axis="y", length=0, labelsize=13, labelcolor=COLORS["text"], pad=10)
    for label in ax.get_yticklabels():
        if label.get_text() == highlight:
            label.set_fontweight("bold")
    return fig


def plot_period_returns(
    df: pd.DataFrame,
    start: str,
    end: str,
    title: str = "期間リターン",
    highlight: str | None = None,
) -> tuple[pd.DataFrame, Figure]:
    """period_returns + plot_returns のショートカット。"""
    returns = period_returns(df, start, end)
    return returns, plot_returns(returns, title, f"{start} ～ {end}", highlight=highlight)


def plot_earnings_counts(
    counts: pd.DataFrame,
    title: str,
    subtitle: str = "",
    highlight: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    top_n_labels: int = 3,
    source: str | None = SOURCE,
) -> Figure:
    """日付ごとの決算発表予定件数の縦棒グラフ。counts は index=date, 列 count。

    発表のない土日は詰めて表示する。highlight=(開始日, 終了日) の期間は帯と濃い色で強調し、
    件数ラベルは強調期間と上位 top_n_labels 日にだけ付ける。
    """
    days = counts[(counts.index.dayofweek < 5) | (counts["count"] > 0)]
    x = np.arange(len(days))
    in_window = (
        (days.index >= highlight[0]) & (days.index <= highlight[1])
        if highlight
        else np.ones(len(days), dtype=bool)
    )

    fig, ax = _new_figure(title, subtitle, source)
    ax.bar(
        x,
        days["count"],
        width=0.72,
        color=np.where(in_window, COLORS["bar"], COLORS["bar_muted"]),
        zorder=2,
    )

    ymax = days["count"].max() * 1.15
    ax.set_ylim(0, ymax)
    if highlight and in_window.any():
        lo, hi = x[in_window].min() - 0.5, x[in_window].max() + 0.5
        ax.axvspan(lo, hi, color=COLORS["band"], zorder=0)
        ax.text(
            (lo + hi) / 2,
            ymax * 0.97,
            f"今週 {_md(highlight[0])}～{_md(highlight[1])}",
            ha="center",
            va="top",
            fontsize=11,
            weight="bold",
            color=COLORS["text_secondary"],
        )

    labeled = set(days["count"].nlargest(top_n_labels).index)
    if highlight:
        labeled |= set(days.index[in_window])
    for xi, (d, c) in zip(x, days["count"].items(), strict=True):
        if d in labeled and c > 0:
            ax.text(xi, c, f"{c}", ha="center", va="bottom", fontsize=11, color=COLORS["text"])

    # 週の頭（月曜、または期間の初日）に日付目盛り
    ticks = [i for i, d in enumerate(days.index) if i == 0 or d.dayofweek == 0]
    ax.set_xticks(ticks, [_md(days.index[i]) for i in ticks])
    ax.set_xlim(-0.8, len(days) - 0.2)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    ax.grid(axis="y", color=COLORS["grid"], linewidth=1, zorder=0)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(COLORS["text_muted"])
    ax.tick_params(length=0, labelsize=11, pad=6)
    return fig


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _paginate(items: list[tuple], rows_per_page: int) -> list[list[tuple]]:
    """("group", ...) / ("row", ...) の並びをページに分ける。

    グループ見出しがページ最終行に来ないようにし、ページ頭が行ならグループ見出しを
    ("continued", ...) として再掲する。
    """
    pages: list[list[tuple]] = []
    page: list[tuple] = []
    group = None
    for item in items:
        if len(page) >= rows_per_page or (item[0] == "group" and len(page) >= rows_per_page - 1):
            pages.append(page)
            page = []
        if item[0] == "group":
            group = item
        elif not page:
            page.append(("continued", *group[1:]))
        page.append(item)
    if page:
        pages.append(page)
    return pages


def plot_earnings_table(
    calendar: pd.DataFrame,
    title: str,
    subtitle: str = "",
    rows_per_page: int = 18,
    source: str | None = SOURCE,
) -> list[Figure]:
    """earnings_in_window の結果を、日付ごとにグループ化した表（ページ分割）にする。

    weight 列は値の横に小さな棒を描き、区分（予定 / 実績）はバッジで表示する。
    """
    # 行アイテム: ("group", date, 社数, weight 合計) / ("row", Series)
    # ページ頭が行ならグループ見出しを「続き」として再掲する
    items: list[tuple] = []
    for d, g in calendar.groupby("date", sort=True):
        items.append(("group", d, len(g), g["weight"].sum()))
        items.extend(("row", row) for _, row in g.iterrows())

    pages = _paginate(items, rows_per_page)

    max_weight = calendar["weight"].max() if len(calendar) else 1
    # 列: (見出し, x 位置, 揃え)
    cols = {
        "event": ("区分", 0.0275, "center"),
        "name": ("銘柄", 0.07, "left"),
        "country": ("国", 0.42, "left"),
        "sector": ("セクター", 0.53, "left"),
        "weight": ("weight", 0.765, "right"),
        "cap": ("cap (bn)", 0.92, "right"),
        "period_end": ("決算期", 1.0, "right"),
    }
    bar_x, bar_w = 0.775, 0.075

    figs = []
    for n, page in enumerate(pages, start=1):
        fig = plt.figure(figsize=FIGSIZE)
        page_no = f"｜{n}/{len(pages)} ページ" if len(pages) > 1 else ""
        _header(fig, title, subtitle + page_no, source)
        ax = fig.add_axes((0.02, 0.07, 0.96, 0.77))
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(rows_per_page + 1, 0)

        for label, x, ha in cols.values():
            ax.text(x, 0.5, label, ha=ha, va="center", fontsize=10, color=COLORS["text_muted"])
        ax.axhline(1, color=COLORS["text_muted"], linewidth=0.8)

        for i, item in enumerate(page):
            yc = i + 1.5
            if item[0] in ("group", "continued"):
                _, d, count, weight = item
                ax.add_patch(Rectangle((0, yc - 0.5), 1, 1, color=COLORS["band"], zorder=0))
                cont = " 続き" if item[0] == "continued" else ""
                ax.text(
                    0.005,
                    yc,
                    f"{_md(d)}（{WEEKDAYS[d.dayofweek]}）{cont}",
                    va="center",
                    fontsize=12.5,
                    weight="bold",
                )
                ax.text(
                    0.17,
                    yc,
                    f"{count}社 · weight 計 {weight:.2%}",
                    va="center",
                    fontsize=11,
                    color=COLORS["text_secondary"],
                )
                continue

            row = item[1]
            planned = str(row["event"]).startswith("次回")
            ax.text(
                cols["event"][1],
                yc,
                "予定" if planned else "実績",
                ha="center",
                va="center",
                fontsize=9.5,
                color=COLORS["badge_plan_text" if planned else "badge_actual_text"],
                bbox={
                    "boxstyle": "round,pad=0.3,rounding_size=0.6",
                    "fc": COLORS["badge_plan" if planned else "badge_actual"],
                    "ec": "none",
                },
            )
            cells = {
                "name": _truncate(str(row["name"]), 44),
                "country": "" if pd.isna(row["country"]) else row["country"],
                "sector": "" if pd.isna(row["sector"]) else row["sector"],
                "weight": f"{row['weight']:.2%}",
                "cap": f"{row['cap'] / 1e9:,.2f}",
                "period_end": "" if pd.isna(row["period_end"]) else f"{row['period_end']:%Y/%m}",
            }
            for key, text in cells.items():
                _, x, ha = cols[key]
                ax.text(x, yc, text, ha=ha, va="center", fontsize=11.5)
            ax.add_patch(
                Rectangle(
                    (bar_x, yc - 0.17),
                    bar_w * row["weight"] / max_weight,
                    0.34,
                    color=COLORS["bar"],
                    linewidth=0,
                )
            )
            ax.axhline(yc + 0.5, color=COLORS["grid"], linewidth=0.6, zorder=0)
        figs.append(fig)
    return figs


def plot_top_by_date(
    calendar: pd.DataFrame,
    title: str,
    subtitle: str = "",
    top_n: int = 3,
    source: str | None = SOURCE,
) -> Figure:
    """earnings_in_window の結果から、日付ごとに weight 上位 top_n 社を1行に並べた表。

    行=日付（その日の社数・weight 合計を併記）、列=1位〜top_n 位。
    """
    days = calendar.groupby("date", sort=True)
    n_rows = max(days.ngroups, 1)

    fig = plt.figure(figsize=FIGSIZE)
    _header(fig, title, subtitle, source)
    ax = fig.add_axes((0.02, 0.07, 0.96, 0.77))
    ax.axis("off")
    ax.set_xlim(0, 1)
    # 1行に収まらない日数でも詰まりすぎないよう、行の高さは最大7日分を基準にする
    ax.set_ylim(max(n_rows, 7) + 0.5, 0)

    date_w = 0.14
    slot_w = (1 - date_w) / top_n
    slot_x = [date_w + i * slot_w for i in range(top_n)]

    ax.text(0.005, 0.25, "日付", va="center", fontsize=10, color=COLORS["text_muted"])
    for i, x in enumerate(slot_x, start=1):
        ax.text(x + 0.01, 0.25, f"{i}位", va="center", fontsize=10, color=COLORS["text_muted"])
    ax.axhline(0.5, color=COLORS["text_muted"], linewidth=0.8)

    for r, (d, g) in enumerate(days):
        y0 = r + 0.5  # 行の上端
        ax.text(
            0.005,
            y0 + 0.38,
            f"{_md(d)}（{WEEKDAYS[d.dayofweek]}）",
            va="center",
            fontsize=14,
            weight="bold",
        )
        ax.text(
            0.005,
            y0 + 0.68,
            f"{len(g)}社 · weight 計 {g['weight'].sum():.2%}",
            va="center",
            fontsize=10,
            color=COLORS["text_secondary"],
        )
        for x, (_, row) in zip(slot_x, g.nlargest(top_n, "weight").iterrows(), strict=False):
            right = x + slot_w - 0.015
            name = _truncate(str(row["name"]), 28)
            ax.text(x + 0.01, y0 + 0.38, name, va="center", fontsize=12.5)
            ax.text(
                right,
                y0 + 0.38,
                f"{row['weight']:.2%}",
                ha="right",
                va="center",
                fontsize=12.5,
                weight="bold",
            )
            event = "予定" if str(row["event"]).startswith("次回") else "実績"
            parts = [v for v in (row["country"], row["sector"]) if isinstance(v, str) and v]
            meta = " · ".join([*parts, event])
            ax.text(
                x + 0.01, y0 + 0.68, meta, va="center", fontsize=10, color=COLORS["text_secondary"]
            )
        for x in slot_x:
            ax.plot([x, x], [y0 + 0.12, y0 + 0.88], color=COLORS["grid"], linewidth=0.8)
        ax.axhline(y0 + 1, color=COLORS["grid"], linewidth=0.6)
    return fig


def tenor_years(label: str) -> float:
    """年限ラベル（"6M", "10Y" など）を年数に換算する。"""
    unit, n = label[-1].upper(), float(label[:-1])
    return {"M": n / 12, "Y": n}[unit]


def plot_yield_curve(
    base: pd.Series,
    previous: pd.Series,
    title: str,
    subtitle: str = "",
    base_label: str = "最新",
    previous_label: str = "1週前",
    source: str | None = SOURCE,
) -> Figure:
    """上段に2時点のイールドカーブ、下段に変化幅（bp）の棒グラフ。

    base / previous は index=年限ラベル（"10Y" など）、値=利回り（%）、name=日付。
    横軸は年限を年数に換算した実際の時間スケール。
    """
    tenors = list(base.index)
    x = np.array([tenor_years(t) for t in tenors])
    change_bp = (base - previous).to_numpy() * 100

    fig = plt.figure(figsize=FIGSIZE, layout=ConstrainedLayoutEngine(rect=(0.01, 0.05, 0.98, 0.80)))
    _header(fig, title, subtitle, source)
    ax_curve, ax_diff = fig.subplots(2, 1, sharex=True, height_ratios=[3, 2])
    for ax in (ax_curve, ax_diff):
        for spine in ax.spines.values():
            spine.set_visible(False)

    # 上段: カーブ（基準=青、1週前=グレー）
    series = [
        (previous, f"{previous.name:%Y/%m/%d}（{previous_label}）", COLORS["text_muted"]),
        (base, f"{base.name:%Y/%m/%d}（{base_label}）", COLORS["positive"]),
    ]
    for s, label, color in series:
        ax_curve.plot(
            x,
            s.to_numpy(),
            color=color,
            linewidth=2,
            marker="o",
            markersize=7,
            markeredgecolor=COLORS["surface"],
            markeredgewidth=2,
            label=label,
            zorder=3,
        )
    # 値ラベルは1週前カーブと反対側に置いて線と重ならないようにする
    for xi, v, p in zip(x, base.to_numpy(), previous.to_numpy(), strict=True):
        above = v >= p
        ax_curve.annotate(
            f"{v:.2f}",
            (xi, v),
            xytext=(0, 9 if above else -9),
            textcoords="offset points",
            ha="center",
            va="bottom" if above else "top",
            fontsize=10,
            color=COLORS["text"],
        )
    lo = min(base.min(), previous.min())
    hi = max(base.max(), previous.max())
    pad = (hi - lo) * 0.15 or 0.1
    ax_curve.set_ylim(lo - pad, hi + pad * 1.5)
    ax_curve.yaxis.set_major_formatter(lambda v, _: f"{v:.2f}%")
    ax_curve.grid(axis="y", color=COLORS["grid"], linewidth=1, zorder=0)
    ax_curve.tick_params(length=0, labelsize=11)
    ax_curve.legend(loc="upper left", frameon=False, fontsize=11, ncols=2)

    # 下段: 変化幅（bp）。上昇=青、低下=赤
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"] for v in change_bp]
    # 棒の幅は年限の最小間隔に合わせる（1Y・2Y・3Y が詰まっても重ならないように）
    width = np.diff(np.sort(x)).min() * 0.6 if len(x) > 1 else 0.6
    ax_diff.bar(x, change_bp, width=width, color=colors, zorder=2)
    ax_diff.axhline(0, color=COLORS["text_secondary"], linewidth=1, zorder=3)
    span = max(abs(change_bp).max(), 1)
    ax_diff.set_ylim(min(change_bp.min(), 0) - span * 0.35, max(change_bp.max(), 0) + span * 0.35)
    for xi, v in zip(x, change_bp, strict=True):
        ax_diff.annotate(
            f"{v:+.1f}",
            (xi, v),
            xytext=(0, 4 if v >= 0 else -4),
            textcoords="offset points",
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=10.5,
            color=COLORS["text"],
        )
    ax_diff.set_yticks([])
    ax_diff.set_ylabel("変化幅（bp）", fontsize=11)
    ax_diff.set_xticks(x, tenors)
    ax_diff.set_xlim(0, x.max() + 1)
    ax_diff.tick_params(axis="x", length=0, labelsize=12, labelcolor=COLORS["text"], pad=6)
    return fig


SERIES_COLORS = ["#2a78d6", "#eb6834"]  # カテゴリ色（固定順）: 左軸, 右軸


def plot_dual_axis(
    prices: pd.DataFrame,
    left: str,
    right: str,
    title: str,
    subtitle: str = "",
    units: dict[str, str] | None = None,
    end_labels: dict[str, str] | None = None,
    highlight: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    source: str | None = SOURCE,
) -> Figure:
    """2系列の価格を、左右別スケールの Y 軸で1枚に描く（値は指数化せずそのまま）。

    各軸の上に「色見本 + 系列名（単位）」を置いて、どの線がどの軸かを示す。
    end_labels={列名: 文字列} を線の右端に表示する。highlight=(開始日, 終了日) は帯で強調する。
    """
    units = units or {}
    data = prices[[left, right]].sort_index().ffill().dropna(how="all")

    fig, ax_left = _new_figure(title, subtitle, source)
    ax_right = ax_left.twinx()
    for spine in ax_right.spines.values():
        spine.set_visible(False)
    if highlight:
        # 帯はデータの最終日までに収める（基準日の値がまだ無い場合に右へはみ出さないように）
        band_start, band_end = highlight[0], min(highlight[1], data.index[-1])
        ax_left.axvspan(band_start, band_end, color=COLORS["band"], zorder=0)
        ax_left.text(
            band_start + (band_end - band_start) / 2,
            0.985,
            "直近1週間",
            transform=ax_left.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10.5,
            weight="bold",
            color=COLORS["text_secondary"],
        )

    ends = {}
    for ax, col, color in [(ax_left, left, SERIES_COLORS[0]), (ax_right, right, SERIES_COLORS[1])]:
        s = data[col].dropna()
        ax.plot(s.index, s.to_numpy(), color=color, linewidth=2, zorder=3)
        ax.plot(
            s.index[-1],
            s.iloc[-1],
            "o",
            color=color,
            markersize=8,
            markeredgecolor=COLORS["surface"],
            markeredgewidth=2,
            zorder=4,
        )
        pad = (s.max() - s.min()) * 0.12 or abs(s.iloc[-1]) * 0.05
        ax.set_ylim(s.min() - pad, s.max() + pad)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
        ax.tick_params(length=0, labelsize=11)
        ylo, yhi = ax.get_ylim()
        ends[col] = (ax, s.index[-1], s.iloc[-1], (s.iloc[-1] - ylo) / (yhi - ylo))

    # 右端ラベル（2行）: 2本の終点が軸の高さの 18% 以内なら上下に離す
    (_, _, _, f_left), (_, _, _, f_right) = ends[left], ends[right]
    shift = {left: 0, right: 0}
    if abs(f_left - f_right) < 0.18:
        upper, lower = (left, right) if f_left >= f_right else (right, left)
        shift[upper], shift[lower] = 24, -24
    for col, (ax, x_end, y_end, _) in ends.items():
        label = col + (f"\n{end_labels[col]}" if end_labels and col in end_labels else "")
        ax.annotate(
            label,
            (x_end, y_end),
            xytext=(12, shift[col]),
            textcoords="offset points",
            va="center",
            fontsize=11.5,
            color=COLORS["text"],
            annotation_clip=False,
        )

    # 軸の見出し（色見本 + 系列名 + 単位）
    axis_titles = [(left, 0.0, "left", SERIES_COLORS[0]), (right, 1.0, "right", SERIES_COLORS[1])]
    for col, x, ha, color in axis_titles:
        name = f"{col}（{units[col]}）" if col in units else col
        key = ax_left.annotate(
            "━━",
            (x, 1.03),
            xycoords="axes fraction",
            ha=ha,
            va="bottom",
            fontsize=11,
            color=color,
        )
        ax_left.annotate(
            name,
            (1, 0) if ha == "left" else (0, 0),
            xycoords=key,
            xytext=(6, 0) if ha == "left" else (-6, 0),
            textcoords="offset points",
            ha=ha,
            va="bottom",
            fontsize=11,
            color=COLORS["text_secondary"],
        )

    span = data.index[-1] - data.index[0]
    ax_left.set_xlim(data.index[0], data.index[-1] + span * 0.22)
    ax_left.grid(axis="y", color=COLORS["grid"], linewidth=1, zorder=0)
    # 2週ごと（月曜）に日付目盛り
    ax_left.xaxis.set_major_locator(WeekdayLocator(byweekday=0, interval=2))
    ax_left.xaxis.set_major_formatter(DateFormatter("%-m/%-d"))
    ax_left.tick_params(axis="x", labelsize=11, labelcolor=COLORS["text_secondary"])
    return fig


def plot_rates_table(
    table: pd.DataFrame,
    title: str,
    subtitle: str = "",
    reference_rows: list[str] | None = None,
    notes: list[str] | None = None,
    source: str | None = SOURCE,
) -> Figure:
    """rates_summary の結果を、水準と変化幅（bp, ミニ棒つき）の表にする。

    reference_rows（米国など）は先頭に灰色の帯で表示し、新興国と区切る。
    """
    reference_rows = [r for r in (reference_rows or []) if r in table.index]
    rows = reference_rows + [r for r in table.index if r not in reference_rows]
    n_rows = len(rows)

    fig = plt.figure(figsize=FIGSIZE)
    _header(fig, title, subtitle, source)
    if notes:
        note = "　".join(notes)
        fig.text(0.02, 0.048, note, fontsize=9.5, color=COLORS["text_muted"], va="bottom")
    ax = fig.add_axes((0.02, 0.09, 0.96, 0.75))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(n_rows + 2, 0)

    # 変化幅列: (値の右端, 棒のゼロ位置, 棒の片側幅)
    chg_cols = {
        "short_chg_bp": (0.345, 0.41, 0.045),
        "long_chg_bp": (0.635, 0.70, 0.045),
        "spread_chg_bp": (0.905, 0.955, 0.04),
    }
    groups = [
        ("短期（2年）", 0.14, 0.46),
        ("10年", 0.49, 0.75),
        ("10年 − 短期（タームスプレッド）", 0.78, 1.0),
    ]
    sub_headers = [
        ("年限", 0.16, "center"),
        ("利回り(%)", 0.26, "right"),
        ("変化(bp)", 0.345, "right"),
        ("利回り(%)", 0.55, "right"),
        ("変化(bp)", 0.635, "right"),
        ("水準(bp)", 0.83, "right"),
        ("変化(bp)", 0.905, "right"),
    ]
    for label, lo, hi in groups:
        ax.text((lo + hi) / 2, 0.45, label, ha="center", va="center", fontsize=11.5, weight="bold")
        ax.plot([lo, hi], [0.85, 0.85], color=COLORS["text_muted"], linewidth=0.8)
    ax.text(0.005, 1.4, "国", va="center", fontsize=10, color=COLORS["text_muted"])
    for label, x, ha in sub_headers:
        ax.text(x, 1.4, label, ha=ha, va="center", fontsize=10, color=COLORS["text_muted"])
    ax.axhline(2, color=COLORS["text_muted"], linewidth=0.8)

    scale = {c: max(table[c].abs().max(skipna=True), 1e-9) for c in chg_cols}

    def fmt(v: float, spec: str) -> str:
        return "—" if pd.isna(v) else format(v, spec)

    for i, country in enumerate(rows):
        r = table.loc[country]
        yc = i + 2.5
        if country in reference_rows:
            ax.add_patch(Rectangle((0, yc - 0.5), 1, 1, color=COLORS["band"], zorder=0))
        is_ref = country in reference_rows
        ax.text(
            0.005,
            yc,
            f"{country}（参考）" if is_ref else country,
            va="center",
            fontsize=12,
            weight="bold" if is_ref else "normal",
        )
        tenor = r["short_tenor"] if pd.notna(r["short"]) else ""
        ax.text(
            0.16,
            yc,
            tenor + ("※" if tenor and tenor != "2Y" else ""),
            ha="center",
            va="center",
            fontsize=10.5,
            color=COLORS["text_secondary"],
        )
        cells = [
            (0.26, fmt(r["short"], ".2f")),
            (0.55, fmt(r["long"], ".2f")),
            (0.83, fmt(r["spread_bp"], "+.0f")),
        ]
        for x, text in cells:
            ax.text(x, yc, text, ha="right", va="center", fontsize=12)
        for col, (x_val, x_zero, half) in chg_cols.items():
            v = r[col]
            ax.text(x_val, yc, fmt(v, "+.1f"), ha="right", va="center", fontsize=12)
            if pd.notna(v) and v != 0:
                w = half * v / scale[col]
                ax.add_patch(
                    Rectangle(
                        (x_zero, yc - 0.16),
                        w,
                        0.32,
                        color=COLORS["positive"] if v > 0 else COLORS["negative"],
                        linewidth=0,
                    )
                )
            ax.plot([x_zero, x_zero], [yc - 0.3, yc + 0.3], color=COLORS["grid"], linewidth=0.8)
        line_color = COLORS["text_muted"] if i == len(reference_rows) - 1 else COLORS["grid"]
        ax.axhline(yc + 0.5, color=line_color, linewidth=0.6, zorder=0)
    return fig


def _fmt_indicator(v, unit: str) -> str:
    """経済指標の値。単位に応じて桁数を変え、大きな値は bn / mn で省略する。"""
    if v is None or pd.isna(v):
        return "—"
    if abs(v) >= 1e9:
        return f"{v / 1e9:,.2f} bn"
    if abs(v) >= 1e6:
        return f"{v / 1e6:,.0f} mn"
    if unit == "pt":
        return f"{v:.1f}"
    if unit == "千人":
        return f"{v:+,.0f}千人"
    if unit == "%":
        return f"{v:.2f}%"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


def _fmt_period(ts, frequency) -> str:
    """対象期間。四半期は 2026Q3、月末日なら 2026/09、それ以外（政策金利の決定日など）は日付。"""
    if ts is None or pd.isna(ts):
        return ""
    if isinstance(frequency, str) and frequency == "Quarterly":
        return f"{ts.year}Q{ts.quarter}"
    if ts.is_month_end:
        return f"{ts:%Y/%m}"
    return f"{ts:%Y/%m/%d}"


def plot_econ_calendar(
    events: pd.DataFrame,
    title: str,
    subtitle: str = "",
    rows_per_page: int = 18,
    source: str | None = SOURCE,
) -> list[Figure]:
    """releases_in_window の結果を、日付ごとにグループ化した表（ページ分割）にする。"""
    items: list[tuple] = []
    for d, g in events.groupby("date", sort=True):
        items.append(("group", d, len(g)))
        items.extend(("row", row) for _, row in g.iterrows())
    pages = _paginate(items, rows_per_page) if items else [[]]

    cols = {
        "event": ("区分", 0.03, "center"),
        "country": ("国", 0.075, "left"),
        "indicator": ("指標", 0.20, "left"),
        "actual": ("実績", 0.70, "right"),
        "previous": ("前回", 0.84, "right"),
        "period": ("対象期間", 1.0, "right"),
    }

    figs = []
    for n, page in enumerate(pages, start=1):
        fig = plt.figure(figsize=FIGSIZE)
        page_no = f"｜{n}/{len(pages)} ページ" if len(pages) > 1 else ""
        _header(fig, title, subtitle + page_no, source)
        ax = fig.add_axes((0.02, 0.07, 0.96, 0.77))
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(rows_per_page + 1, 0)

        for label, x, ha in cols.values():
            ax.text(x, 0.5, label, ha=ha, va="center", fontsize=10, color=COLORS["text_muted"])
        ax.axhline(1, color=COLORS["text_muted"], linewidth=0.8)
        if not page:
            ax.text(0.5, 3, "該当する発表はありません", ha="center", color=COLORS["text_secondary"])

        for i, item in enumerate(page):
            yc = i + 1.5
            if item[0] in ("group", "continued"):
                _, d, count = item
                ax.add_patch(Rectangle((0, yc - 0.5), 1, 1, color=COLORS["band"], zorder=0))
                cont = " 続き" if item[0] == "continued" else ""
                ax.text(
                    0.005,
                    yc,
                    f"{_md(d)}（{WEEKDAYS[d.dayofweek]}）{cont}",
                    va="center",
                    fontsize=12.5,
                    weight="bold",
                )
                ax.text(
                    0.17, yc, f"{count}件", va="center", fontsize=11, color=COLORS["text_secondary"]
                )
                continue

            row = item[1]
            planned = row["event"] == "予定"
            ax.text(
                cols["event"][1],
                yc,
                row["event"],
                ha="center",
                va="center",
                fontsize=9.5,
                color=COLORS["badge_plan_text" if planned else "badge_actual_text"],
                bbox={
                    "boxstyle": "round,pad=0.3,rounding_size=0.6",
                    "fc": COLORS["badge_plan" if planned else "badge_actual"],
                    "ec": "none",
                },
            )
            cells = {
                "country": row["country"],
                "indicator": _truncate(str(row["indicator"]), 30),
                "actual": "" if planned else _fmt_indicator(row["actual"], row["unit"]),
                "previous": _fmt_indicator(row["previous"], row["unit"]),
                "period": _fmt_period(row["period"], row["frequency"]),
            }
            for key, text in cells.items():
                _, x, ha = cols[key]
                weight = "bold" if key == "actual" else "normal"
                ax.text(x, yc, text, ha=ha, va="center", fontsize=11.5, weight=weight)
            ax.axhline(yc + 0.5, color=COLORS["grid"], linewidth=0.6, zorder=0)
        figs.append(fig)
    return figs


# 法人格などの末尾だけ落とす（Group / Holding は社名の一部なので残す）
_NAME_SUFFIXES = re.compile(
    r"([ ,]+(Co\.?,? Ltd|Ltd|Limited|PJSC|SAB de CV|SA|S\.A\.|Corp|Corporation|Inc|Bhd|Berhad|PCL|"
    r"Tbk PT|Tbk|PLC|plc|AS|AG|NV|Co|Company)\.?|/The)$"
)


def short_name(name: str) -> str:
    """ツリーマップ用に社名の末尾（Ltd, PJSC, SA など）を落とす。"""
    prev = None
    while prev != name:
        prev, name = name, _NAME_SUFFIXES.sub("", name).strip()
    return name


def _return_cmap():
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "returns", ["#b8312f", COLORS["negative"], "#f0efec", COLORS["positive"], "#184f95"]
    )


def _ink_for(rgb) -> str:
    """セル塗りの明るさに応じて白 / 黒の文字色を選ぶ。"""
    r, g, b = rgb[:3]
    return COLORS["text"] if 0.299 * r + 0.587 * g + 0.114 * b > 0.6 else COLORS["surface"]


def _text_width(text: str, fontsize: float) -> float:
    """おおよその文字幅（pt）。全角は 1em、半角は 0.58em で見積もる。"""
    return sum(fontsize if ord(c) > 0x2E80 else fontsize * 0.58 for c in text)


def _fit_cell_label(
    label: str, value: str, w: float, h: float, max_fs: float = 13, min_fs: float = 6
) -> tuple[float, str | None]:
    """セル（w x h pt）に「社名 + リターン」が収まる最大の文字サイズと文字列。

    社名は1行、または単語の区切りで2〜3行に折り返した案を比べ、最も大きく表示できるものを使う。
    min_fs 未満にしかならないときは (0, None)。
    """
    words = label.split()
    candidates = [[label]]
    # 2行・3行に折り返す案（各行の長さがなるべく揃う区切りを選ぶ）
    for n_lines in (2, 3):
        if len(words) < n_lines:
            break
        splits = itertools.combinations(range(1, len(words)), n_lines - 1)
        best = min(
            splits,
            key=lambda cut: max(
                len(" ".join(words[a:b]))
                for a, b in zip((0, *cut), (*cut, len(words)), strict=True)
            ),
        )
        bounds = zip((0, *best), (*best, len(words)), strict=True)
        candidates.append([" ".join(words[a:b]) for a, b in bounds])

    best_fs, best_lines = 0.0, None
    for name_lines in candidates:
        lines = [*name_lines, value]
        width = max(_text_width(line, 1) for line in lines)
        fs = min(max_fs, (w - 4) / width, (h - 2) / (len(lines) * 1.3))
        if fs > best_fs:
            best_fs, best_lines = fs, lines
    if best_fs < min_fs or best_lines is None:
        return 0.0, None
    return best_fs, "\n".join(best_lines)


def plot_treemap(
    stocks: pd.DataFrame,
    groups: list[str],
    title: str,
    subtitle: str = "",
    size_col: str = "weight",
    color_col: str = "return",
    label_col: str = "label",
    clip: float = 0.05,
    source: str | None = SOURCE,
) -> Figure:
    """銘柄を groups の階層（例: ["country"], ["country", "sector"]）でまとめたツリーマップ。

    セルの面積 = size_col（weight）、色 = color_col（リターン、±clip で飽和）。
    各グループの見出しには weight 加重リターンと weight 合計を表示する。
    """
    import squarify
    from matplotlib.colors import Normalize

    data = stocks[stocks[size_col] > 0].copy()
    for g in groups:
        data[g] = data[g].fillna("その他")
    cmap, norm = _return_cmap(), Normalize(-clip, clip)

    fig = plt.figure(figsize=FIGSIZE)
    _header(fig, title, subtitle, source)
    rect = (0.02, 0.075, 0.96, 0.765)
    ax = fig.add_axes(rect)
    ax.axis("off")
    # 座標を pt 単位にして、文字が収まるかを判定しやすくする
    width_pt, height_pt = rect[2] * FIGSIZE[0] * 72, rect[3] * FIGSIZE[1] * 72
    ax.set_xlim(0, width_pt)
    ax.set_ylim(height_pt, 0)

    def weighted_return(df: pd.DataFrame) -> float:
        valid = df.dropna(subset=[color_col])
        w = valid[size_col].sum()
        return (valid[size_col] * valid[color_col]).sum() / w if w else float("nan")

    def squarify_rects(sizes: list[float], x, y, w, h) -> list[dict]:
        if w <= 0 or h <= 0:
            return [{"x": x, "y": y, "dx": 0, "dy": 0} for _ in sizes]
        return squarify.squarify(squarify.normalize_sizes(sizes, w, h), x, y, w, h)

    def draw_leaves(df: pd.DataFrame, x, y, w, h) -> None:
        df = df.sort_values(size_col, ascending=False)
        for (_, row), r in zip(
            df.iterrows(), squarify_rects(df[size_col].tolist(), x, y, w, h), strict=True
        ):
            v = row[color_col]
            fill = cmap(norm(v)) if pd.notna(v) else (0.84, 0.84, 0.82, 1)
            ax.add_patch(
                Rectangle(
                    (r["x"], r["y"]),
                    r["dx"],
                    r["dy"],
                    facecolor=fill,
                    edgecolor=COLORS["surface"],
                    linewidth=0.6,
                )
            )
            value = f"{v:+.1%}" if pd.notna(v) else "—"
            fs, text = _fit_cell_label(str(row[label_col]), value, r["dx"], r["dy"])
            if text:
                ax.text(
                    r["x"] + r["dx"] / 2,
                    r["y"] + r["dy"] / 2,
                    text,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    linespacing=1.15,
                    color=_ink_for(fill),
                )

    def draw_level(df: pd.DataFrame, level: int, x, y, w, h) -> None:
        if level == len(groups):
            draw_leaves(df, x, y, w, h)
            return
        col = groups[level]
        sizes = df.groupby(col)[size_col].sum().sort_values(ascending=False)
        top = level == 0
        header_h, pad = (16.0, 2.0) if top else (11.0, 1.0)
        for name, r in zip(sizes.index, squarify_rects(sizes.tolist(), x, y, w, h), strict=True):
            sub = df[df[col] == name]
            gx, gy, gw, gh = r["x"] + pad, r["y"] + pad, r["dx"] - 2 * pad, r["dy"] - 2 * pad
            ax.add_patch(
                Rectangle(
                    (r["x"], r["y"]),
                    r["dx"],
                    r["dy"],
                    facecolor=COLORS["surface"] if top else COLORS["band"],
                    edgecolor=COLORS["text_muted"] if top else COLORS["grid"],
                    linewidth=1.0 if top else 0.6,
                    zorder=0,
                )
            )
            # 見出しは収まるときだけ（入らない小さなグループは見出しなしでセルだけ描く）
            fs = 10.5 if top else 8
            ret = weighted_return(sub)
            # 長い順に試して、入る最初のもの: 名前+リターン+weight → 名前+リターン → 名前
            options = [f"{name}  {ret:+.1%}", str(name)]
            if top:
                options.insert(0, f"{name}  {ret:+.1%}（w {sub[size_col].sum():.1%}）")
            text = next((t for t in options if _text_width(t, fs) < gw - 4), None)
            if text and gh > header_h * 2:
                ax.text(
                    gx + 2,
                    gy + header_h / 2,
                    text,
                    va="center",
                    fontsize=fs,
                    weight="bold" if top else "normal",
                    color=COLORS["text"] if top else COLORS["text_secondary"],
                )
                gy, gh = gy + header_h, gh - header_h
            draw_level(sub, level + 1, gx, gy, gw, gh)

    draw_level(data, 0, 0, 0, width_pt, height_pt)

    # 右下に色の凡例（-clip ～ +clip）
    steps = np.linspace(-clip, clip, 9)
    lx, ly, sw, sh = 0.70, 0.022, 0.03, 0.022
    for i, v in enumerate(steps):
        fig.patches.append(
            Rectangle(
                (lx + i * sw, ly),
                sw,
                sh,
                transform=fig.transFigure,
                facecolor=cmap(norm(v)),
                edgecolor=COLORS["surface"],
                linewidth=0.5,
            )
        )
    for v, ha, xpos in [
        (-clip, "center", lx),
        (0, "center", lx + 4.5 * sw),
        (clip, "center", lx + 9 * sw),
    ]:
        fig.text(
            xpos,
            ly - 0.004,
            f"{v:+.0%}" if v else "0%",
            ha=ha,
            va="top",
            fontsize=9,
            color=COLORS["text_secondary"],
        )
    fig.text(
        lx - 0.008,
        ly + sh / 2,
        "1週間リターン",
        ha="right",
        va="center",
        fontsize=9.5,
        color=COLORS["text_secondary"],
    )
    return fig


def save_png(fig: Figure, path: Path, dpi: int = DPI) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor())
    return path
