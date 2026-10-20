from pathlib import Path

import yaml
from pydantic import BaseModel, Field, TypeAdapter

from .paths import CONFIG_DIR


class Instrument(BaseModel):
    ticker: str = Field(..., description="RIC")
    alias: str | None = Field(None, description="表示名")


# universe.yaml はトップレベルのキーがグループ名（countries, sectors, ...）
Universe = dict[str, list[Instrument]]


def load_universe(path: Path = CONFIG_DIR / "universe.yaml") -> Universe:
    with path.open("r", encoding="utf-8") as f:
        return TypeAdapter(Universe).validate_python(yaml.safe_load(f))


def alias_map(instruments: list[Instrument]) -> dict[str, str]:
    """ticker -> alias（alias が無ければ ticker のまま）"""
    return {i.ticker: i.alias or i.ticker for i in instruments}
