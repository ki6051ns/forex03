from pathlib import Path

from dataclasses import dataclass

from dotenv import load_dotenv

import os

# .env を読み込む（存在しなくてもOK）

load_dotenv()

@dataclass

class IBConfig:

    """IBKR 接続設定"""

    host: str = os.getenv("IB_HOST", "127.0.0.1")

    port: int = int(os.getenv("IB_PORT", "7497"))

    client_id: int = int(os.getenv("IB_CLIENT_ID", "1"))

@dataclass

class DataConfig:

    """データ保存用のベースディレクトリ設定"""

    base_dir: Path = Path(os.getenv("DATA_DIR", "data")).resolve()

ib_config = IBConfig()

data_config = DataConfig()
