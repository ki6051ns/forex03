import sys

from pathlib import Path

from datetime import datetime



import pandas as pd

from ib_insync import Forex



# src を import path に追加

ROOT = Path(__file__).resolve().parents[1]

sys.path.append(str(ROOT / "src"))



from ibkr_data.client import create_ib_connection

from ibkr_data.config import data_config





def main() -> None:

    ib = create_ib_connection()

    print("Connected to IBKR for real-time 5-sec logger.")



    contract = Forex("USDJPY")



    bars_buffer = []



    def on_bar_update(bars, has_new_bar):

        """

        ib_insync のバージョンによって updateEvent の第1引数は

        RealTimeBarList になる。この場合、bars[-1] が最新バー。



        RealTimeBar のフィールド名は open_ / high / low / close / volume / wap / count。

        """

        if not has_new_bar:

            return



        # 最新バーを取得（RealTimeBarList → RealTimeBar）

        bar = bars[-1]



        dt = bar.time

        if isinstance(dt, datetime) and dt.tzinfo is not None:

            dt = dt.replace(tzinfo=None)



        bars_buffer.append(

            {

                "time": dt,

                "open": bar.open_,   # 注意: open_ であること

                "high": bar.high,

                "low": bar.low,

                "close": bar.close,

                "volume": bar.volume,

                "wap": bar.wap,

                "count": bar.count,

            }

        )



    # 5秒足リアルタイムバー購読

    rt_bar = ib.reqRealTimeBars(

        contract,

        5,           # barSize (seconds)

        "MIDPOINT",  # whatToShow

        False,       # useRTH

        []           # realTimeBarsOptions

    )

    rt_bar.updateEvent += on_bar_update



    out_dir = data_config.base_dir / "ibkr" / "fx" / "USDJPY" / "sec5"

    out_dir.mkdir(parents=True, exist_ok=True)



    def flush_to_disk():

        nonlocal bars_buffer

        if not bars_buffer:

            return



        df = pd.DataFrame(bars_buffer)

        bars_buffer = []



        if df.empty:

            return



        df["time"] = pd.to_datetime(df["time"])

        df.set_index("time", inplace=True)



        today = datetime.utcnow().strftime("%Y-%m-%d")

        out_file = out_dir / f"USDJPY_sec5_{today}.parquet"



        if out_file.exists():

            old = pd.read_parquet(out_file)

            df = (

                pd.concat([old, df])

                .sort_index()

                .drop_duplicates()

            )



        df.to_parquet(out_file)

        print(f"Flushed {df.shape[0]} rows to {out_file}")



    try:

        print("Starting event loop. Press Ctrl+C to stop.")

        while True:

            ib.sleep(10)  # 10秒ごとに flush

            flush_to_disk()

    except KeyboardInterrupt:

        print("KeyboardInterrupt received. Flushing remaining data...")

        flush_to_disk()

    finally:

        ib.disconnect()

        print("Disconnected from IBKR.")





if __name__ == "__main__":

    main()
