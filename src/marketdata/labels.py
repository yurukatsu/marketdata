"""LSEG の英語ラベル -> 日本語表示名。対応がないものは英語のまま使う。"""

import pandas as pd

# TR.HeadquartersCountry の値
COUNTRY_JA = {
    "Brazil": "ブラジル",
    "Canada": "カナダ",
    "Chile": "チリ",
    "China": "中国",
    "Colombia": "コロンビア",
    "Czech Republic": "チェコ",
    "Egypt": "エジプト",
    "Greece": "ギリシャ",
    "Hong Kong": "香港",
    "Hungary": "ハンガリー",
    "India": "インド",
    "Indonesia": "インドネシア",
    "Korea; Republic (S. Korea)": "韓国",
    "Kuwait": "クウェート",
    "Luxembourg": "ルクセンブルク",
    "Malaysia": "マレーシア",
    "Mexico": "メキシコ",
    "Netherlands": "オランダ",
    "Peru": "ペルー",
    "Philippines": "フィリピン",
    "Poland": "ポーランド",
    "Qatar": "カタール",
    "Saudi Arabia": "サウジアラビア",
    "Singapore": "シンガポール",
    "South Africa": "南アフリカ",
    "Switzerland": "スイス",
    "Taiwan": "台湾",
    "Thailand": "タイ",
    "Turkey": "トルコ",
    "United Arab Emirates": "UAE",
    "United Kingdom": "英国",
    "United States of America": "米国",
}

# TR.GICSSector の値
GICS_SECTOR_JA = {
    "Energy": "エネルギー",
    "Materials": "素材",
    "Industrials": "資本財・サービス",
    "Consumer Discretionary": "一般消費財・サービス",
    "Consumer Staples": "生活必需品",
    "Health Care": "ヘルスケア",
    "Financials": "金融",
    "Information Technology": "情報技術",
    "Communication Services": "コミュニケーション・サービス",
    "Utilities": "公益事業",
    "Real Estate": "不動産",
}


def to_ja(values: pd.Series, mapping: dict[str, str]) -> pd.Series:
    return values.map(mapping).fillna(values)
