import sys

from pathlib import Path

# src を import path に追加

ROOT = Path(__file__).resolve().parents[1]

sys.path.append(str(ROOT / "src"))

from ibkr_data.client import create_ib_connection

from ib_insync import Forex

def main() -> None:

    """IBKR 接続テストと USDJPY の現在レート取得"""

    ib = create_ib_connection()

    print("Connected to IBKR:", ib)

    # サーバ時刻

    server_time = ib.reqCurrentTime()

    print("Server time:", server_time)

    # USDJPY の気配

    contract = Forex("USDJPY")

    ticker = ib.reqMktData(contract, "", False, False)

    # データが返ってくるまで少し待つ

    ib.sleep(2)

    print("Ticker object:", ticker)

    bid, ask = ticker.bid, ticker.ask

    if bid is not None and ask is not None:

        mid = (bid + ask) / 2

        print(f"Bid: {bid}, Ask: {ask}, Mid: {mid}")

    else:

        print("No bid/ask data available yet (try increasing sleep time).")

    ib.disconnect()

    print("Disconnected.")

if __name__ == "__main__":

    main()
