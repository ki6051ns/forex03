# forex03 Data Layer 研究計画書 v1.0

## 0. 概要

- プロジェクト名: forex03 Data Layer
- 目的: 
  - FX (主に USDJPY) に対する MFT（Mid-Frequency Trading）戦略のための
    安定的かつ再現性のあるデータ取得・蓄積基盤を構築する。
  - 将来のイベント駆動型バックテスト（経路依存）まで耐えうる
    分足・秒足・ティックレベルのデータ品質を確保する。

- 本計画書の対象範囲:
  - インフラ: Python + IBKR (TWS/Gateway) 経由のデータ取得
  - データ: 1分足 / 5秒足（リアルタイム） / 将来のティックデータ
  - 保存: ローカルストレージ上の Parquet ファイル
  - 運用: dev 環境での PoC、将来 stg / prod 分離を前提とした設計方針

---

## 1. 背景

- forex03 は、**利食い・損切りを伴う経路依存ストラテジー**であり、
  バックテストも経路依存（path-dependent）になる。
- 粒度の細かいデータ（分足・5秒足・ティック）を、
  **安定的に・欠損を最小限にして**取得することが前提条件。
- すでに PoC として以下の機能を確認済み:
  - IBKR API 接続 (`ib_insync`)
  - USDJPY 1分足ヒストリカル取得（約 1週間分）
  - USDJPY 5秒足リアルタイムロガー

今後は「動くスクリプト」から一段進めて、
**再現性・拡張性・運用性**を満たすデータレイヤを設計する。

---

## 2. 研究のゴール（Data Layer 観点）

1. **安定取得**
   - USDJPY について、1分足・5秒足データを
     長期に渡って途切れなく取得・蓄積できること。

2. **再現性**
   - 任意のイベント時点に対して、
     「その時点で観測可能だった」価格系列（1分 / 5秒 / ティック）を
     再構成できること。

3. **拡張性**
   - 通貨ペア追加（EURUSD, GBPUSD 等）
   - 足種追加（15秒足、custom aggregation 等）
   - データソース追加（将来: 他社API, CSVインポート 等）

4. **運用性**
   - 取得スクリプトが「落ちっぱなし」にならないよう、
     ログ・簡易アラート・再起動手順が整理されていること。

---

## 3. 対象データと粒度

### 3.1 第一フェーズ（MVP）

- 通貨ペア:
  - USDJPY（IDEALPRO）
- 粒度:
  - ヒストリカル: 1分足 (`reqHistoricalData`)
  - リアルタイム: 5秒足 (`reqRealTimeBars`)
- 保存形式:
  - Parquet（列指向・圧縮有り）
- データ構造（推奨カラム）:
  - `time` (datetime, tz-naive, index)
  - `open`, `high`, `low`, `close`
  - `volume`
  - `wap`, `barCount` or `count` (取れる範囲で)

### 3.2 第二フェーズ（拡張案）

- 粒度:
  - ティックレベル（`reqMktData` ベースの自前リアルタイムログ）
- 通貨ペア:
  - EURUSD, GBPUSD, AUDJPY, EURJPY 等
- 足種:
  - イベント周辺のみ高頻度で取る「イベント窓ティック」

---

## 4. システム構成（論理アーキテクチャ）

### 4.1 レイヤ分割

1. **L0 – Connector Layer**
   - IBKR API への接続・切断ラッパ (`ibkr_data.client.create_ib_connection`)
   - 設定管理 (`ibkr_data.config`)

2. **L1 – Data Fetcher**
   - ヒストリカル取得（1分足）
   - リアルタイム取得（5秒足・将来ティック）

3. **L2 – Storage Layer**
   - Parquet ファイルへの書き込み・読み込み
   - ディレクトリ構成:
     - `data/ibkr/fx/{symbol}/{freq}/`

4. **L3 – Data Quality / Repair**
   - 欠損検知（ギャップ検出, duplicated index の検出）
   - 再取得（backfill）ロジック

5. **L4 – Consumer / 上位レイヤ**
   - forex03 feature builder / backtester がここを利用。

---

## 5. 現状実装（2025-12-01 時点）

### 5.1 実装済み

- `scripts/test_connection.py`
  - IBKR 接続テスト
  - USDJPY の気配取得

- `scripts/backfill_1min.py`
  - 1分足ヒストリカル取得
  - ステップバック方式で過去方向に backfill
  - Parquet 保存 (例: `USDJPY_1min_2025-11-25_to_2025-12-01.parquet`)

- `scripts/rtsec_logger.py`
  - `reqRealTimeBars` による USDJPY 5秒足リアルタイム取得
  - 10秒ごとなどにバッファを flush
  - 日次ファイルとして Parquet 追記（例: `USDJPY_sec5_2025-12-01.parquet`）

### 5.2 未実装・今後のテーマ

- データギャップの自動検出と backfill
- 異常値・スパイク検出（将来）
- 通貨ペア/足種の設定ファイル化
- ログ・簡易モニタリング

---

## 6. 実験・検証計画

1. **安定動作検証**
   - 5秒足ロガーを数日連続稼働させ、
     - プロセス落ち
     - ネットワーク切断
     - TWS 再起動
     に対する挙動を観察し、再起動手順・スクリプト改善。

2. **ギャップ検証**
   - 1分足 backfill と 5秒足 aggregation から、
     同一期間の OHLC を比較して品質チェック。

3. **イベントテスト**
   - 主要指標発表時のウィンドウ（±30分）を抽出し、
     - 盛り上がり方
     - ボラ分布
     - スプレッド（将来、bid/ask を取る場合）  
     を確認。

4. **拡張検討**
   - 他通貨ペアで同じ構成が再利用できるか検証。

---

## 7. マイルストーン（Data Layer 部分）

- M1: 1分足 / 5秒足の安定取得 (✅ 達成)
- M2: ギャップ検出 & 自動 backfill
- M3: イベントウィンドウ抽出モジュール（forex03共通モジュール）
- M4: 通貨ペア追加・config駆動化
- M5: stg/prod 環境向け構成案（別マシン or サーバ運用）

===

# forex03 Data Layer 要件定義書 v1.0

## 1. 目的

forex03 戦略のバックテスト・ペーパートレード・将来の実弾運用に必要な
FX レートデータ（主に USDJPY）の取得・保管・提供を行うデータレイヤの要件を定義する。

---

## 2. 対象スコープ

- 対象:
  - IBKR 経由の FX レートデータ (USDJPY)
  - 1分足ヒストリカル
  - 5秒足リアルタイム
- 対象外（今バージョンでは検討のみ）:
  - 他社 API
  - 自動売買実行ロジック
  - 口座管理 / リスク管理

---

## 3. 機能要件 (FR)

### FR-1: 1分足ヒストリカル取得

- FR-1-1
  - 指定期間 `[start_date, end_date]` の 1分足データを取得できること。
- FR-1-2
  - API 制限に応じて複数回に分割して取得し、整合性のある DataFrame として統合できること。
- FR-1-3
  - 取得結果は `data/ibkr/fx/USDJPY/min1/` 配下の Parquet として保存されること。
- FR-1-4
  - `time` カラムは tz-naive な `datetime64[ns]` とし、index に設定すること。

### FR-2: 5秒足リアルタイムロギング

- FR-2-1
  - 稼働中は USDJPY の 5秒足を連続的に取得し、メモリバッファに保持すること。
- FR-2-2
  - 指定間隔ごと（例: 10秒）にバッファを Parquet に flush し、日次ファイルに追記すること。
- FR-2-3
  - Parquet ファイルは `data/ibkr/fx/USDJPY/sec5/` 配下に保存されること。
- FR-2-4
  - アプリケーション終了時（KeyboardInterrupt 等）には、残データを flush してから切断すること。

### FR-3: データリロード

- FR-3-1
  - 保存済みの Parquet ファイルから DataFrame を再構築できるヘルパー関数を提供すること。
- FR-3-2
  - 1分足 / 5秒足データのロードは、
    上位モジュール（feature builder / backtester）から簡単に呼び出せる API であること。

### FR-4: ギャップ検出（v1.1 以降）

- FR-4-1
  - 指定期間の 1分足 / 5秒足に対して、期待される時刻列と実データの index を比較し、
    欠損・重複を検出できること。
- FR-4-2
  - 検出結果をログまたはレポートとして出力すること。

---

## 4. 非機能要件 (NFR)

### NFR-1: 安定性

- NFR-1-1
  - 5秒足ロガーは 1日程度連続稼働してもメモリリーク等で落ちないこと（手動での停止を前提とする）。
- NFR-1-2
  - 異常終了時も、既に flush 済みのデータは Parquet として利用可能であること。

### NFR-2: 再現性

- NFR-2-1
  - 1分足の backfill と 5秒足の aggregation から、同一期間の OHLC が概ね一致すること。
- NFR-2-2
  - 時刻の扱いはすべて tz-naive に統一し、将来のタイムゾーン変換は
    別レイヤで行うこと。

### NFR-3: 拡張性

- NFR-3-1
  - 通貨ペア追加は設定を追加するだけで対応可能な構造とすること
    （例: `config.yaml` / `symbols.json` 等）。
- NFR-3-2
  - 足種追加（例: 15秒足、カスタムイベント足）は、
    既存ストレージ構造 `data/ibkr/fx/{symbol}/{freq}/` を踏襲すること。

### NFR-4: ログ・監査

- NFR-4-1
  - 主要イベント（接続開始・切断・エラー・ファイル保存）はログ出力すること。
- NFR-4-2
  - ログは当面コンソール出力＋簡易ファイルログ（任意）とし、
    将来の監視ツール導入を考慮したフォーマットにすること。

---

## 5. 運用要件

- OU-1
  - 当面は dev 環境（開発用 PC 上）で手動起動：
    - 1分足 backfill: 手動実行
    - 5秒足ロガー: 手動起動 → 手動停止
- OU-2
  - 将来、stg/prod 環境ではスケジューラ（例: Windows タスクスケジューラ / systemd timer など）での自動起動を検討する。
- OU-3
  - IBKR TWS/Gateway の再起動時に備え、接続リトライロジックまたは手動再起動手順を整備する。

---

## 6. インターフェース要件

- `ibkr_data.client.create_ib_connection()`
  - IB インスタンスを返す。
- `scripts/backfill_1min.py`（将来はモジュール化）
  - `backfill_1min(start_date, end_date) -> DataFrame`
  - `save_1min_to_parquet(df, start_date, end_date) -> Path`
- `scripts/rtsec_logger.py`
  - コマンドラインツールとして利用。
  - 将来は `realtime_logger.py` として複数通貨ペア対応を検討。

---

## 7. リスクと制約

- R-1: IBKR API 制限
  - コール頻度・取得可能期間に制約があるため、
    backfill 時は durationStr / sleep を調整する必要がある。
- R-2: TWS / Gateway 停止
  - 手動運用の間は、停止時にデータギャップが発生する。
  - ギャップ検出・backfill でカバーする方針とする。
- R-3: ローカルディスク容量
  - 秒足・ティックを長期間ためると容量圧迫の可能性がある。
  - 将来、古いデータのアーカイブ（圧縮 or オフロード）を検討する。

---

## 8. 今後の拡張に向けた前提

- 将来的に forex03 以外のストラテジー（forex01, future01 等）も
  同じ Data Layer を共有する可能性があるため、
  モジュール名・ディレクトリ構造は汎用性を意識する。
