# forex03-data

Data ingestion & logging system for FX (USDJPY) using IBKR API. Includes 1min historical backfill and real-time 5-second bars/tick logging for MFT-grade FX strategies.

## Overview

This repository provides tools to collect and store FX market data from Interactive Brokers (IBKR) API. It supports:

- Historical 1-minute bar data backfilling
- Real-time 5-second bar logging
- Real-time tick data logging
- Data storage in Parquet format for efficient analysis

## Directory Structure

```
forex03-data/
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ .env
│
├─ src/
│   └─ ibkr_data/
│       ├─ __init__.py
│       ├─ config.py          # Configuration management
│       └─ client.py           # IBKR connection wrapper
│
├─ scripts/
│   ├─ test_connection.py      # Test IBKR connection
│   ├─ backfill_1min.py        # Historical 1min data backfill
│   └─ rtsec_logger.py         # Real-time 5sec bars logger
│
└─ data/
    └─ ibkr/
        └─ fx/
            └─ USDJPY/
                ├─ min1/       # 1-minute bars
                ├─ sec5/       # 5-second bars
                └─ tick/       # Tick data
```

## Setup Instructions

### 1. Create Virtual Environment

```bash
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure IBKR Connection

Create or edit `.env` file:

```env
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
DATA_DIR=data
```

**Note:** 
- `IB_PORT=7497` for TWS (paper trading: 7497, live: 7496)
- `IB_PORT=4001` for IB Gateway (paper trading: 4002, live: 4001)

### 4. Enable IBKR API

Before running scripts, ensure:

1. **TWS (Trader Workstation):**
   - Configure → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Set Socket port (default: 7497 for paper, 7496 for live)
   - Add trusted IP: 127.0.0.1

2. **IB Gateway:**
   - Login and enable API access
   - Default port: 4001 (live) or 4002 (paper)

## How to Run

### Test Connection

First, verify your IBKR connection:

```bash
python scripts/test_connection.py
```

This will:
- Connect to IBKR
- Display server time
- Fetch USDJPY current bid/ask/mid prices
- Disconnect cleanly

### Backfill Historical Data

Fetch historical 1-minute bars:

```bash
# Default: 30 days of USDJPY data
python scripts/backfill_1min.py

# Custom: 60 days for EURUSD
python scripts/backfill_1min.py --symbol EURUSD --days 60
```

### Real-time Data Logging

Start real-time 5-second bar logging:

```bash
# Default: USDJPY
python scripts/rtsec_logger.py

# Custom currency pair
python scripts/rtsec_logger.py --symbol EURUSD
```

Press `Ctrl+C` to stop logging.

## Notes about IBKR TWS/Gateway API Settings

- **API must be enabled** in TWS/Gateway settings
- **Port numbers** must match between `.env` and TWS/Gateway configuration
- **Client ID** must be unique for each connection (default: 1)
- **Market data subscription** may be required for real-time data
- **Paper trading** uses different ports than live trading
- Ensure TWS/Gateway is running before executing scripts

## Data Format

All data is stored in **Parquet format** for efficient storage and fast analysis:

- **1-minute bars**: OHLCV data with timestamps
- **5-second bars**: Real-time aggregated bars
- **Tick data**: Individual price updates with bid/ask/mid

Files are organized by date and automatically deduplicated on save.

