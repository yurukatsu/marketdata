import os

import lseg.data as ld
import pandas as pd
from dotenv import load_dotenv

from .configs import Instrument
from .paths import PROJECT_ROOT

pd.set_option("future.no_silent_downcasting", True)


class LSEGClient:
    """lseg-data の Platform セッションを保持するクライアント。

    最初の呼び出しでセッションを開き、close() まで使い回す。
    スクリプトでは with 文で使う:

        with LSEGClient() as client:
            df = client.get_history(...)
    """

    def __init__(self):
        load_dotenv(PROJECT_ROOT / ".env")
        self.definition = ld.session.platform.Definition(
            app_key=os.environ["LSEG_APP_KEY"],
            grant=ld.session.platform.GrantPassword(
                username=os.environ["LSEG_USERNAME"],
                password=os.environ["LSEG_PASSWORD"],
            ),
            signon_control=True,
        )
        self._session = None

    def open(self) -> "LSEGClient":
        if self._session is None:
            self._session = self.definition.get_session()
            self._session.open()
            ld.session.set_default(self._session)
        return self

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "LSEGClient":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def get_history(
        self,
        universe: list[str],
        fields: list[str],
        start: str,
        end: str,
        interval: str = "1D",
    ) -> pd.DataFrame:
        self.open()
        return ld.get_history(
            universe=universe,
            fields=fields,
            start=start,
            end=end,
            interval=interval,
        )

    def get_history_chunked(
        self,
        universe: list[str],
        field: str,
        start: str,
        end: str,
        chunk_size: int = 50,
    ) -> pd.DataFrame:
        """多数の RIC を chunk_size ずつに分けて取得する（列=RIC）。"""
        frames = []
        for i in range(0, len(universe), chunk_size):
            chunk = universe[i : i + chunk_size]
            df = self.get_history(universe=chunk, fields=[field], start=start, end=end)
            if len(chunk) == 1:
                df.columns = chunk
            frames.append(df)
        out = pd.concat(frames, axis=1)
        out.index = pd.to_datetime(out.index)
        out.columns.name = None
        return out.sort_index().astype(float)

    def get_instrument_history(
        self,
        instruments: list[Instrument],
        start: str,
        end: str,
        default_field: str = "TR.PriceClose",
        interval: str = "1D",
    ) -> pd.DataFrame:
        """universe.yaml のグループの時系列を取得する。列=alias（yaml の並び順）。

        銘柄ごとに field が指定されていればそれを使い、同じフィールドの銘柄はまとめて取得する。
        """
        by_field: dict[str, list[Instrument]] = {}
        for i in instruments:
            by_field.setdefault(i.field or default_field, []).append(i)

        frames = []
        for field, group in by_field.items():
            df = self.get_history(
                universe=[i.ticker for i in group],
                fields=[field],
                start=start,
                end=end,
                interval=interval,
            )
            # 1銘柄だと列名がフィールド名になるので、ticker で付け直す
            if len(group) == 1:
                df.columns = [group[0].ticker]
            frames.append(df.rename(columns={i.ticker: i.name for i in group}))

        out = pd.concat(frames, axis=1)
        out.index = pd.to_datetime(out.index)
        return out.sort_index()[[i.name for i in instruments]]

    def get_data(
        self,
        universe: list[str],
        fields: list[str],
        parameters: dict | None = None,
    ) -> pd.DataFrame:
        self.open()
        return ld.get_data(universe=universe, fields=fields, parameters=parameters)

    def convert_symbols(
        self,
        symbols: list[str],
        from_symbol_type: str = "SEDOL",
        to_symbol_types: list[str] | None = None,
    ) -> pd.DataFrame:
        self.open()
        return ld.convert_symbols(
            symbols=symbols,
            from_symbol_type=from_symbol_type,
            to_symbol_types=to_symbol_types or ["RIC"],
        )
