"""
過去の1分足データをバックフィルするスクリプト
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# src を import path に追加
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from ibkr_data.client import create_ib_connection
from ibkr_data.config import data_config
from ib_insync import Forex, util


def save_bar_data(symbol: str, bars: list, timeframe: str = "1min"):
    """
    バーデータをParquet形式で保存
    
    Args:
        symbol: 通貨ペア（例: "USDJPY"）
        bars: ib_insyncのBarオブジェクトのリスト
        timeframe: 時間足（例: "1min", "5sec"）
    """
    if not bars:
        print(f"No bars to save for {symbol}")
        return
    
    # データディレクトリのパス構築
    save_dir = data_config.base_dir / "ibkr" / "fx" / symbol / timeframe
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # ib_insyncのBarオブジェクトをDataFrameに変換
    df = util.df(bars)
    
    if df.empty:
        print(f"Empty DataFrame for {symbol}")
        return
    
    # ファイル名: {symbol}_{timeframe}_{start_date}_{end_date}.parquet
    start_date = df['date'].min().strftime('%Y%m%d')
    end_date = df['date'].max().strftime('%Y%m%d')
    filename = f"{symbol}_{timeframe}_{start_date}_{end_date}.parquet"
    filepath = save_dir / filename
    
    # Parquet形式で保存
    df.to_parquet(filepath, index=False)
    print(f"Saved {len(df)} bars to {filepath}")


def backfill_1min(symbol: str = "USDJPY", days: int = 30):
    """
    指定された日数分の1分足データを取得して保存
    
    Args:
        symbol: 通貨ペア（例: "USDJPY"）
        days: 取得する日数
    """
    ib = create_ib_connection()
    print(f"Connected to IBKR. Fetching {days} days of 1min data for {symbol}")
    
    try:
        contract = Forex(symbol)
        ib.qualifyContracts(contract)
        print(f"Contract qualified: {contract}")
        
        # 取得期間の計算
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        print(f"Fetching bars from {start_time} to {end_time}")
        
        # 1分足データを取得
        # IBKRの制限: 最大1年分のデータを一度に取得可能
        bars = ib.reqHistoricalData(
            contract,
            endDateTime=end_time,
            durationStr=f"{days} D",
            barSizeSetting="1 min",
            whatToShow="MIDPOINT",
            useRTH=False,
            formatDate=1
        )
        
        if bars:
            print(f"Retrieved {len(bars)} bars")
            save_bar_data(symbol, bars, "1min")
        else:
            print("No bars retrieved")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ib.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill 1-minute FX data from IBKR")
    parser.add_argument("--symbol", default="USDJPY", help="Currency pair (default: USDJPY)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to fetch (default: 30)")
    
    args = parser.parse_args()
    backfill_1min(args.symbol, args.days)

