from ib_insync import IB
from .config import ib_config


def create_ib_connection() -> IB:
    """
    IBKR への接続を確立して IB インスタンスを返す。
    TWS / Gateway 側で API 有効化されていることが前提。
    
    Returns:
        IB: 接続済みのIBインスタンス
        
    Raises:
        RuntimeError: 接続に失敗した場合
    """
    ib = IB()
    ib.connect(
        ib_config.host,
        ib_config.port,
        clientId=ib_config.client_id,
    )
    if not ib.isConnected():
        raise RuntimeError(
            f"Failed to connect to IBKR at {ib_config.host}:{ib_config.port}. "
            "Check TWS/Gateway and API settings."
        )
    return ib

