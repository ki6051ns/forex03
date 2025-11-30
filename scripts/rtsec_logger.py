"""
リアルタイムで5秒足データをログするスクリプト
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# src を import path に追加
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from ibkr_data.client import create_ib_connection
from ibkr_data.config import data_config
from ib_insync import Forex


class RealTimeBarLogger:
    """リアルタイム5秒足データをログするクラス"""
    
    def __init__(self, symbol: str = "USDJPY"):
        self.symbol = symbol
        self.ib = None
        self.contract = None
        self.bars = []
        self.save_dir = data_config.base_dir / "ibkr" / "fx" / symbol / "sec5"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.last_save_time = datetime.now()
        self.save_interval = 60  # 60秒ごとに保存
        
    def on_bar_update(self, bars, has_new_bar):
        """5秒足更新時のコールバック"""
        if has_new_bar and bars:
            bar = bars[-1]  # 最新のバー
            timestamp = bar.date
            
            bar_data = {
                'date': timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            
            self.bars.append(bar_data)
            print(f"[{timestamp.strftime('%H:%M:%S')}] {self.symbol}: O={bar.open:.3f}, H={bar.high:.3f}, L={bar.low:.3f}, C={bar.close:.3f}, V={bar.volume}")
            
            # 定期的に保存（時間間隔またはバッファサイズで）
            now = datetime.now()
            if (now - self.last_save_time).total_seconds() >= self.save_interval or len(self.bars) >= 100:
                self.save_bars()
    
    def save_bars(self):
        """バーデータをParquet形式で保存（自動結合・重複除去）"""
        if not self.bars:
            return
        
        df = pd.DataFrame(self.bars)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{self.symbol}_sec5_{date_str}.parquet"
        filepath = self.save_dir / filename
        
        # 既存ファイルがあれば読み込んで結合
        if filepath.exists():
            try:
                existing_df = pd.read_parquet(filepath)
                df = pd.concat([existing_df, df], ignore_index=True)
                # 重複除去（同じdateの場合は新しい方を保持）
                df = df.drop_duplicates(subset=['date'], keep='last')
                df = df.sort_values('date')
            except Exception as e:
                print(f"Warning: Could not read existing file {filepath}: {e}")
        
        # Parquet形式で保存
        df.to_parquet(filepath, index=False)
        print(f"Saved {len(self.bars)} new bars (total {len(df)} bars) to {filepath}")
        self.bars = []
        self.last_save_time = datetime.now()
    
    def start(self):
        """ロギングを開始"""
        self.ib = create_ib_connection()
        print(f"Connected to IBKR. Starting real-time 5-second bar logging for {self.symbol}")
        
        self.contract = Forex(self.symbol)
        self.ib.qualifyContracts(self.contract)
        print(f"Contract qualified: {self.contract}")
        
        # リアルタイム5秒足を購読
        bars = self.ib.reqRealTimeBars(
            self.contract,
            barSize=5,
            whatToShow='MIDPOINT',
            useRTH=False
        )
        
        # バー更新イベントにコールバックを登録
        bars.updateEvent += self.on_bar_update
        
        print("Logging started. Press Ctrl+C to stop...")
        
        try:
            # メインループ
            while True:
                self.ib.sleep(1)
                # 定期的に保存（念のため）
                now = datetime.now()
                if (now - self.last_save_time).total_seconds() >= self.save_interval:
                    if self.bars:
                        self.save_bars()
        except KeyboardInterrupt:
            print("\nStopping logger...")
        finally:
            # 残りのバーを保存
            if self.bars:
                self.save_bars()
            self.ib.disconnect()
            print("Disconnected.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time 5-second bar logger for FX data from IBKR")
    parser.add_argument("--symbol", default="USDJPY", help="Currency pair (default: USDJPY)")
    
    args = parser.parse_args()
    
    logger = RealTimeBarLogger(args.symbol)
    logger.start()


if __name__ == "__main__":
    main()

