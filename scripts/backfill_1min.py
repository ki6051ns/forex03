import sys

from pathlib import Path

from datetime import datetime, timedelta



import pandas as pd

from ib_insync import Forex



# src を import path に追加

ROOT = Path(__file__).resolve().parents[1]

sys.path.append(str(ROOT / "src"))



from ibkr_data.client import create_ib_connection

from ibkr_data.config import data_config





# ===== 設定値（必要に応じて書き換え） =====

# 例: 2025-11-25 から 2025-12-01 まで

START_DATE = "2025-11-25"

END_DATE = "2025-12-01"



CONTRACT = Forex("USDJPY")

BAR_SIZE = "1 min"

WHAT_TO_SHOW = "MIDPOINT"  # TRADES / BID / ASK も検討可

DURATION_STR = "1 D"       # 一度に取る期間（IBKR 制限に応じて調整）

# ==============================





def fetch_1min_chunk(ib, end_dt: datetime, duration_str: str) -> pd.DataFrame:

    """

    end_dt を終点として過去方向に duration_str の 1分足を取得する。

    取得できなければ空 DataFrame を返す。

    """



    # IBKR には tz を意識させないために文字列で渡す

    end_str = end_dt.strftime("%Y%m%d %H:%M:%S")



    bars = ib.reqHistoricalData(

        contract=CONTRACT,

        endDateTime=end_str,

        durationStr=duration_str,

        barSizeSetting=BAR_SIZE,

        whatToShow=WHAT_TO_SHOW,

        useRTH=False,

        formatDate=1,

    )



    if not bars:

        return pd.DataFrame()



    # ---- ここで自前で DataFrame を構築（tz は全部剥がす） ----

    records = []

    for bar in bars:

        dt = bar.date

        # bar.date が tz付き datetime なら tzinfo を外す

        if isinstance(dt, datetime) and dt.tzinfo is not None:

            dt = dt.replace(tzinfo=None)



        records.append(

            {

                "time": dt,

                "open": bar.open,

                "high": bar.high,

                "low": bar.low,

                "close": bar.close,

                "volume": bar.volume,

                "barCount": getattr(bar, "barCount", None),

                "WAP": getattr(bar, "wap", None),

            }

        )



    df = pd.DataFrame.from_records(records)

    df.set_index("time", inplace=True)

    # -----------------------------------------------------------



    return df





def backfill_1min(start_date: str, end_date: str) -> pd.DataFrame:

    """

    start_date〜end_date の 1分足を過去方向に遡って取得し、一つの DataFrame にまとめる。

    """

    ib = create_ib_connection()

    print("Connected to IBKR for backfill.")



    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    end_dt = datetime.strptime(end_date, "%Y-%m-%d")



    cur_end = end_dt

    all_chunks = []



    while cur_end > start_dt:

        print(f"Requesting 1min bars up to {cur_end} ...")

        df_chunk = fetch_1min_chunk(ib, cur_end, DURATION_STR)



        if df_chunk.empty:

            print("No more data returned. Stopping.")

            break



        oldest = df_chunk.index.min()

        newest = df_chunk.index.max()

        print(f"  Got {df_chunk.shape[0]} rows: {oldest} -> {newest}")



        all_chunks.append(df_chunk)



        # oldest が tz-aware の場合は tz を剥がして naive に揃える

        if getattr(oldest, "tzinfo", None) is not None:

            oldest_naive = oldest.replace(tzinfo=None)

        else:

            oldest_naive = oldest



        # 次のリクエストは、取得できた最古時刻の 1分前まで遡る

        cur_end = oldest_naive - timedelta(minutes=1)



        # API レート制限対策で少し待機

        ib.sleep(0.5)



        if cur_end <= start_dt:

            print("Reached start_date boundary.")

            break



    ib.disconnect()

    print("Disconnected from IBKR.")



    if not all_chunks:

        print("No data collected.")

        return pd.DataFrame()



    full_df = pd.concat(all_chunks).sort_index().drop_duplicates()



    # 指定期間でトリミング

    mask = (full_df.index >= start_dt) & (full_df.index <= end_dt)

    full_df = full_df.loc[mask]



    print(f"Final merged rows: {full_df.shape[0]}")

    return full_df





def save_1min_to_parquet(df: pd.DataFrame, start_date: str, end_date: str) -> Path:

    """

    取得した 1分足データを Parquet で保存する。

    """

    if df.empty:

        raise ValueError("DataFrame is empty, nothing to save.")



    out_dir = data_config.base_dir / "ibkr" / "fx" / "USDJPY" / "min1"

    out_dir.mkdir(parents=True, exist_ok=True)



    filename = f"USDJPY_1min_{start_date}_to_{end_date}.parquet"

    out_path = out_dir / filename



    df.to_parquet(out_path)

    print(f"Saved 1min data to: {out_path}")

    return out_path





def main() -> None:

    df = backfill_1min(START_DATE, END_DATE)

    if df.empty:

        print("No data fetched. Exiting.")

        return

    save_1min_to_parquet(df, START_DATE, END_DATE)





if __name__ == "__main__":

    main()
