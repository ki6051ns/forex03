import sys
from pathlib import Path

# src を import path に追加
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from ibkr_data.client import create_ib_connection
from ib_insync import Forex


def main():
    """IBKR接続テストとUSDJPYの現在レート取得"""
    ib = create_ib_connection()
    print("Connected to IBKR:", ib)

    # サーバ時刻
    server_time = ib.reqCurrentTime()
    print("Server time:", server_time)

    # USDJPY の現在レートを一発取得
    contract = Forex("USDJPY")
    ib.qualifyContracts(contract)
    print(f"Contract qualified: {contract}")
    
    ticker = ib.reqMktData(contract, "", False, False)
    ib.sleep(2)  # ちょっと待つ

    print("Ticker:", ticker)
    if ticker.bid and ticker.ask:
        mid = (ticker.bid + ticker.ask) / 2
        print(f"Bid: {ticker.bid}, Ask: {ticker.ask}, Mid: {mid}")
    else:
        print("No bid/ask data available yet")

    ib.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    main()

