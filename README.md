# marketdata

LSEG Data Library (`lseg-data`) からマーケットデータを取得し、可視化・分析するためのプロジェクト。

## セットアップ

```bash
uv sync
cp .env.example .env   # LSEG_APP_KEY / LSEG_USERNAME / LSEG_PASSWORD を記入
```

## ディレクトリ構成

```
configs/universe.yaml   取得対象のユニバース（countries, sectors など）
data/                   取得データ・社内データ（git 管理外）
  raw/                  LSEG から取得した生データ
  reference/            ベンチマーク構成銘柄などの入力データ
notebooks/              分析・可視化用ノートブック
src/marketdata/
  client.py             LSEGClient（セッション管理つきの lseg-data ラッパー）
  configs.py            universe.yaml の読み込み
  plotting.py           可視化関数
  paths.py              プロジェクト内のパス定義
  cli.py                定期実行用の CLI
```

## 使い方

### ノートブック

`notebooks/` を開き、カーネルにプロジェクトの `.venv` を選択する。

```python
from marketdata import LSEGClient, load_universe

client = LSEGClient()  # 最初の呼び出しでセッションを開き、使い回す
df = client.get_history(universe=[".HSI"], fields=["TR.PriceClose"], start="2026-01-01", end="2026-10-01")
client.close()
```

### CLI

定期実行したい処理は CLI に移す。

```bash
# universe.yaml の countries を取得して data/raw/countries.csv に保存
uv run marketdata history countries --start 2025-10-01 --end 2026-10-01
uv run marketdata history sectors -f "TR.PriceClose(Curn=USD)"
```
