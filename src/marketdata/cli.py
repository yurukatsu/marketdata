from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from .client import LSEGClient
from .configs import alias_map, load_universe
from .paths import CONFIG_DIR, RAW_DIR

app = typer.Typer()


@app.callback()
def main() -> None:
    """LSEG からマーケットデータを取得するツール。"""


@app.command()
def history(
    group: Annotated[
        str, typer.Argument(help="universe.yaml のグループ名（countries, sectors など）")
    ],
    field: Annotated[
        str, typer.Option("--field", "-f", help="取得フィールド")
    ] = "TR.PriceClose(Curn=USD)",
    start: Annotated[str, typer.Option(help="開始日 (YYYY-MM-DD)。省略時は1年前")] = "",
    end: Annotated[str, typer.Option(help="終了日 (YYYY-MM-DD)。省略時は今日")] = "",
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="ユニバース設定ファイル", exists=True, dir_okay=False),
    ] = CONFIG_DIR / "universe.yaml",
    output_path: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="CSV出力先。省略時は data/raw/<group>.csv"),
    ] = None,
) -> None:
    """ユニバースの時系列を取得して CSV に出力します。"""
    universe = load_universe(config_path)
    if group not in universe:
        raise typer.BadParameter(f"{group} は {config_path} にありません: {list(universe)}")
    instruments = universe[group]

    end = end or date.today().isoformat()
    start = start or (date.fromisoformat(end) - timedelta(days=365)).isoformat()

    with LSEGClient() as client:
        df = client.get_history(
            universe=[i.ticker for i in instruments],
            fields=[field],
            start=start,
            end=end,
        )
    df = df.rename(columns=alias_map(instruments))
    df.index.name = "date"

    output_path = output_path or RAW_DIR / f"{group}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    typer.echo(f"Saved: {output_path} ({len(df)} rows)")


@app.command("weekly-report")
def weekly_report(
    base_date: Annotated[
        str, typer.Option("--date", "-d", help="基準日 (YYYY-MM-DD)。省略時は今日")
    ] = "",
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="レポート設定ファイル", exists=True, dir_okay=False),
    ] = CONFIG_DIR / "weekly_report.yaml",
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="出力先ディレクトリ。省略時は outputs/weekly/<基準日>"),
    ] = None,
) -> None:
    """週次レポートの図表（PNG）と CSV を出力します。"""
    import matplotlib

    matplotlib.use("Agg")  # 画面のない環境（EC2 など）でも描画できるように

    from .reports.weekly import WeeklyReport, WeeklyReportConfig

    report = WeeklyReport(
        base_date=pd.Timestamp(base_date or date.today()),
        config=WeeklyReportConfig.load(config_path),
        output_dir=output_dir,
        log=lambda msg: typer.echo(f"- {msg}"),
    )
    outputs = report.run()
    typer.echo(f"Saved {len(outputs)} files to {report.output_dir}")


if __name__ == "__main__":
    app()
