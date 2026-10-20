import os

import lseg.data as ld
import pandas as pd
from dotenv import load_dotenv

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
