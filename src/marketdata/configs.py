from pathlib import Path

import yaml
from pydantic import BaseModel, Field, TypeAdapter

from .paths import CONFIG_DIR


class Instrument(BaseModel):
    ticker: str = Field(..., description="RIC")
    alias: str | None = Field(None, description="表示名")
    field: str | None = Field(None, description="取得フィールド（省略時は呼び出し側の既定値）")
    unit: str | None = Field(None, description="単位（表示用）")
    tenor: str | None = Field(None, description="年限（代用年限を注記するときなど）")

    @property
    def name(self) -> str:
        return self.alias or self.ticker


# universe.yaml はトップレベルのキーがグループ名（countries, sectors, ...）
Universe = dict[str, list[Instrument]]


def load_universe(path: Path = CONFIG_DIR / "universe.yaml") -> Universe:
    with path.open("r", encoding="utf-8") as f:
        return TypeAdapter(Universe).validate_python(yaml.safe_load(f))


def alias_map(instruments: list[Instrument]) -> dict[str, str]:
    """ticker -> alias（alias が無ければ ticker のまま）"""
    return {i.ticker: i.alias or i.ticker for i in instruments}
