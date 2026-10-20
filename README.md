# marketdata

LSEG Data Library (`lseg-data`) からマーケットデータを取得し、可視化・分析するためのプロジェクト。
処理はスクリプト（CLI）で実行し、結果（PNG / CSV）は `outputs/` に出力する（git 管理外）。

## セットアップ

```bash
uv sync
cp .env.example .env   # LSEG_APP_KEY / LSEG_USERNAME / LSEG_PASSWORD を記入
```

Chrome などのブラウザは不要（図は matplotlib で描画し、日本語フォントはパッケージに同梱）。EC2 などのヘッドレス環境でもそのまま動く。

## 週次レポート

毎週水曜に実行する想定。

```bash
uv run marketdata weekly-report                  # 基準日 = 今日
uv run marketdata weekly-report --date 2026-10-21
```

- カレンダー系（決算・経済指標）は **基準日以降**、価格系（リターン・利回り・コモディティ・ツリーマップ）は **前日までの最新値** を使う。
  例: 10/21（水）実行 → カレンダーは 10/21〜10/27、リターンは 10/13 → 10/20
- 期間・フィルター（weight / cap）・取得フィールドなどは `configs/weekly_report.yaml` で設定する。
- 出力先は `outputs/weekly/<基準日>/`。PNG は 2560x1440（16:9）でそのまま PowerPoint に貼れる。

| ファイル | 内容 |
|---|---|
| `01_country_returns.png` | 各国株式インデックスのリターン |
| `02_sector_returns.png` | MSCI EM セクター別リターン（MSCI EM を強調） |
| `03_earnings_counts.png` | BM 構成銘柄の次回決算発表予定件数（基準日〜決算シーズン終わり） |
| `04_earnings_calendar_NN.png` | 基準日から1週間の決算発表銘柄（日付 → weight 順、国・セクターつき） |
| `05_earnings_top_by_date.png` | 日付ごとの weight 上位銘柄 |
| `06_us_yield_curve.png` | 米国債イールドカーブ（最新 vs 1週前）と変化幅 |
| `07_commodities.png` | WTI原油・金（左右2軸、直近3ヶ月、直近1週間を強調） |
| `08_em_rates.png` | 新興国 国債利回り（2年・10年・タームスプレッドの水準と変化） |
| `09_econ_calendar_NN.png` | 主要経済指標の発表予定・結果（基準日から1週間） |
| `10_treemap_*.png` | BM 構成銘柄の1週間リターン ツリーマップ（国別・セクター別・国×セクター） |

各図には対応する CSV も出力する。

## その他の CLI

```bash
# universe.yaml のグループの時系列を取得して data/raw/<group>.csv に保存
uv run marketdata history countries --start 2025-10-01 --end 2026-10-01
uv run marketdata history sectors -f "TR.PriceClose(Curn=USD)"
```

## 設定ファイル・データ

```
configs/
  universe.yaml          取得対象（各国指数・MSCI EM セクター・米国債・各国国債・コモディティ）
  econ_indicators.yaml   経済指標カレンダーの対象指標（国ごと）
  weekly_report.yaml     週次レポートのパラメータ
data/                    入力データ・取得データ（git 管理外）
  reference/bm.csv       ベンチマーク構成銘柄（sedol, isin, name, cap, weight）
```

## コード構成

```
src/marketdata/
  client.py          LSEGClient（セッション管理つきの lseg-data ラッパー）
  configs.py         universe.yaml などの読み込み
  earnings.py        決算発表日の取得・集計
  economics.py       経済指標の発表カレンダー
  rates.py           国債利回りの集計
  labels.py          国名・GICS セクターの日本語表示名
  plotting.py        図表（matplotlib）
  reports/weekly.py  週次レポート本体
  cli.py             CLI（marketdata コマンド）
  fonts/             Noto Sans JP（SIL OFL）
```

`notebooks/weekly_report_sample.ipynb` はライブラリの使い方のサンプル（実行結果は保存しない）。
実行して試すときは出力を消してからコミットする。

ちょっとした分析でライブラリとして使う場合:

```python
from marketdata import LSEGClient

with LSEGClient() as client:
    df = client.get_history(universe=[".HSI"], fields=["TR.PriceClose"], start="2026-01-01", end="2026-10-01")
```
