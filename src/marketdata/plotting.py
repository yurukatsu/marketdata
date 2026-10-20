import numpy as np
import pandas as pd
import plotly.graph_objects as go


def plot_period_returns(
    df: pd.DataFrame,
    start: str,
    end: str,
    title: str = "期間リターン",
    xaxis_title: str = "",
) -> tuple[pd.DataFrame, go.Figure]:
    """列ごとに start〜end の単純リターンを計算し、昇順の棒グラフにする。"""
    data = df.copy()
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    period_df = data.loc[pd.Timestamp(start) : pd.Timestamp(end)]

    if period_df.empty:
        raise ValueError(f"{start} から {end} のデータがありません。")

    # 列ごとに最初と最後の有効値を取得
    start_values = period_df.apply(lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan)
    end_values = period_df.apply(lambda x: x.dropna().iloc[-1] if not x.dropna().empty else np.nan)

    # 単純リターン
    returns = (
        end_values.div(start_values)
        .sub(1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .sort_values(ascending=True)
    )

    return_df = returns.rename("return").reset_index()
    return_df.columns = ["name", "return"]

    # プラスとマイナスで色分け
    colors = ["#EF553B" if value < 0 else "#00CC96" for value in return_df["return"]]

    fig = go.Figure(
        go.Bar(
            x=return_df["name"],
            y=return_df["return"],
            marker_color=colors,
            text=return_df["return"],
            texttemplate="%{text:.2%}",
            textposition="outside",
            customdata=np.column_stack(
                [
                    start_values.loc[return_df["name"]],
                    end_values.loc[return_df["name"]],
                ]
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "リターン: %{y:.2%}<br>"
                "期初値: %{customdata[0]:,.2f}<br>"
                "期末値: %{customdata[1]:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"{title}（{start} ～ {end}）",
        xaxis_title=xaxis_title,
        yaxis_title="リターン",
        yaxis_tickformat=".1%",
        template="plotly_white",
        height=600,
        bargap=0.2,
    )

    # 昇順を明示
    fig.update_xaxes(
        categoryorder="array",
        categoryarray=return_df["name"].tolist(),
        tickangle=-45,
    )

    # ゼロラインを強調
    fig.update_yaxes(
        zeroline=True,
        zerolinewidth=1.5,
        zerolinecolor="black",
    )

    return return_df, fig
