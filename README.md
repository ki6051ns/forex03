# forex03 Data Layer 研究計画書 v1.1

## 0. 概要

- プロジェクト名: forex03 Data Layer
- 目的: 
  - FX (主に USDJPY) に対する MFT（Mid-Frequency Trading）戦略のための  
    **安定的かつ再現性のあるレートデータ取得・蓄積基盤**を構築する。
  - 将来のイベント駆動型バックテスト（経路依存）および  
    **クローズベース成行執行＋スプレッド/コスト評価**まで耐えうる  
    分足・秒足・ティックレベルのデータ品質を確保する。

- 本計画書の対象範囲:
  - インフラ: Python + IBKR (TWS/Gateway) 経由のデータ取得
  - データ:  
    - 1分足ヒストリカル  
    - 5秒足リアルタイム（RealTimeBars）  
    - 将来のティックデータ（bid/askベース）
  - 保存: ローカルストレージ上の Parquet ファイル
  - 運用: dev 環境での PoC（現状）、将来 stg / prod 分離を前提とした設計方針

---

## 1. 背景

- forex03 は **利食い・損切り・追いポジションを伴う経路依存ストラテジー**であり、  
  バックテストも path-dependent となる。
- 粒度の細かいデータ（分足・5秒足・ティック）を、
  **安定的に・欠損を最小限にして**取得することが前提条件。
- また、将来的には
  - **スプレッド・ミッド・約定コストを含めたシミュレーション**
  - **イベント週 / ホット・コールド週ごとのローテーション**
  を行うため、**スプレッドとボラ情報を含む Market Snapshot 的データ**が必要。

- すでに PoC として以下の機能を確認済み:
  - IBKR API 接続 (`ib_insync`)
  - USDJPY 1分足ヒストリカル取得（複数日分）
  - USDJPY 5秒足リアルタイムロガー
  - 上記を Parquet に保存・再ロードできることを確認

今後は「動くスクリプト」から一段進めて、
**再現性・拡張性・運用性・コスト評価対応**を満たすデータレイヤを設計する。

---

## 2. 研究のゴール（Data Layer 観点）

1. **安定取得**
   - USDJPY について、1分足・5秒足データを  
     長期に渡って途切れなく取得・蓄積できること。

2. **再現性**
   - 任意のイベント時点に対して、
     「その時点で観測可能だった」価格系列（1分 / 5秒 / 将来ティック）を
     **tz-naiveな統一時系列として再構成**できること。

3. **拡張性**
   - 通貨ペア追加（EURUSD, GBPUSD 等）
   - 足種追加（15秒足、イベント窓ティック等の custom aggregation）
   - データソース追加（将来: 他社API, CSVインポート 等）

4. **運用性**
   - 取得スクリプトが「落ちっぱなし」にならないよう、
     ログ・簡易アラート・再起動手順が整理されていること。
   - 将来 stg / prod 環境では、**自動起動＋自動リトライ**を前提に運用可能な設計になっていること。

5. **コスト評価対応**
   - 5秒足（および将来ティック）から
     - bid / ask / mid / spread
     を復元・集計できる構造とし、  
     **スプレッド・スリッページモデル**の入力として利用可能であること。

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

**1分足:**
- `time` (datetime, tz-naive, index)  
  - 取得直後は IBKR の tz-aware (US/Eastern) を受け取り、  
    Data Layer 内で tz_localize → tz_convert → tz-naive に正規化するポリシーを採用。
- `open`, `high`, `low`, `close`
- `volume`
- 取れる場合は `wap`, `barCount` などを拡張カラムとして保持

**5秒足（RealTimeBarsベース）:**
- `time` (datetime, tz-naive, index)
- `open`, `high`, `low`, `close`
- `volume`
- `wap`, `count`（取得可能な範囲で）
- **将来拡張用カラム（空であってもスキーマに含めておく想定）**
  - `bid`, `ask`, `mid`, `spread`

### 3.2 第二フェーズ（拡張案）

- 粒度:
  - ティックレベル（`reqMktData` ベースの自前リアルタイムログ）
  - 特にイベント前後の「イベント窓ティック」を重点的に取得する設計

- 通貨ペア:
  - EURUSD, GBPUSD, AUDJPY, EURJPY 等（forex03で有望なペア）

- 足種:
  - イベント周辺のみ高頻度で取る「イベント窓ティック」
  - ティックからのカスタムバー（例: 2秒足, 10秒足）を Data Layer レベルで集計するかどうかは、上位ロジックの要求を見て判断。

---

## 4. システム構成（論理アーキテクチャ）

### 4.1 レイヤ分割（v1.1版）

1. **L0 – Connector Layer**
   - IBKR API への接続・切断ラッパ (`ibkr_data.client.create_ib_connection`)
   - 接続設定管理 (`ibkr_data.config`)
   - 将来: stg / prod で IB 接続先や clientId を切り替え可能にする。

2. **L1 – Data Fetcher**
   - ヒストリカル取得（1分足）
   - リアルタイム取得（5秒足）
   - 将来: ティック取得（bid/ask）ロガー
   - **タイムゾーン変換と tz-naive 正規化の責務を持つ**

3. **L2 – Storage Layer**
   - Parquet ファイルへの書き込み・読み込み
   - ディレクトリ構成（維持）:
     - `data/ibkr/fx/{symbol}/{freq}/`
       - 例: `data/ibkr/fx/USDJPY/min1/`
       - 例: `data/ibkr/fx/USDJPY/sec5/`
   - 将来: 古いデータのアーカイブ、S3 等へのオフロードも視野

4. **L3 – Data Quality / Repair**
   - 欠損検知（ギャップ検出、重複 index の検出）
   - 再取得（backfill）ロジック
   - 1分足と5秒足 aggregation の整合性チェック
   - 将来: 異常値・スパイク検出

5. **L4 – Consumer / 上位レイヤ**
   - forex03 feature builder / backtester / execution engine がここを利用。
   - Data Layer は「**OHLC + （将来）spread/mid**」を安定提供する責務。

---

## 5. 現状実装（2025-12-02 時点）

### 5.1 実装済み

- `scripts/test_connection.py`
  - IBKR 接続テスト
  - USDJPY の気配取得
  - 接続確認ログ出力（Server time, bid/ask/mid）

- `scripts/backfill_1min.py`
  - 1分足ヒストリカル取得
  - ステップバック方式で過去方向に backfill
  - pandas の tz 周りのエラー（US/Eastern → tz-naive）を解消済み
  - Parquet 保存 (例:  
    `data/ibkr/fx/USDJPY/min1/USDJPY_1min_2025-11-25_to_2025-12-01.parquet`)

- `scripts/rtsec_logger.py`
  - `reqRealTimeBars` による USDJPY 5秒足リアルタイム取得
  - RealTimeBarList / RealTimeBar オブジェクトの扱いを修正し、安定稼働を確認
  - バッファを一定件数ごとに flush
  - 日次ファイルとして Parquet 追記（例:  
    `data/ibkr/fx/USDJPY/sec5/USDJPY_sec5_2025-12-01.parquet`）

### 5.2 未実装・今後のテーマ

- データギャップの自動検出と backfill
- 5秒足ベースの **1分足再構成 (aggregation)** による品質検証
- 将来の bid/ask ロギング（ティック or 高頻度 snapshot）
- 通貨ペア/足種の設定ファイル化（config駆動）
- ログ・簡易モニタリング（例: エラー時 slack / メール通知）

---

## 6. 実験・検証計画

1. **安定動作検証**
   - 5秒足ロガーを数日連続稼働させ、
     - プロセス落ち
     - ネットワーク切断
     - TWS 再起動
     に対する挙動を観察し、  
     再起動手順・スクリプト改善・将来の自動リトライ方針を整理。

2. **ギャップ検証**
   - 1分足 backfill と 5秒足 aggregation から、
     同一期間の OHLC を比較して品質チェック。
   - ギャップや大きな乖離があれば、IB 再取得 or 例外処理パターンを検討。

3. **イベントテスト**
   - 主要指標発表時のウィンドウ（±30分）を抽出し、
     - ボラ分布
     - ローソク足パターン
     - （将来）スプレッドの挙動
     を確認し、forex03 のイベントロジック設計にフィードバック。

4. **スプレッド/コストモデルへの橋渡し**
   - 将来の bid/ask/tick ロガー導入時に備え、
     sec5・min1 Parquet に空の `bid`, `ask`, `mid`, `spread` カラムを設ける案を検討。
   - 実現した場合、**slippage モデルの3パターン（楽観/中間/悲観）**の入力として利用。

5. **拡張検討**
   - 他通貨ペアで同じ構成が再利用できるか検証。
   - ディレクトリ構造・config の汎用性検証。

---

## 7. マイルストーン（Data Layer 部分）

- **M1: 1分足 / 5秒足の安定取得 (✅ 達成)**
  - IBKR 接続 ～ Parquet 保存までのエラー解消済み
- M2: ギャップ検出 & 自動 backfill（min1 / sec5）
- M3: 5秒足 → 1分足 aggregation 検証ユーティリティ
- M4: イベントウィンドウ抽出モジュール（forex03共通モジュール）
- M5: 通貨ペア追加・config駆動化
- M6: stg/prod 環境向け構成案（別マシン or サーバ運用）、自動起動/監視

---

# forex03 Data Layer 要件定義書 v1.1

## 1. 目的

forex03 戦略のバックテスト・ペーパートレード・将来の実弾運用に必要な  
FX レートデータ（主に USDJPY）の取得・保管・提供を行う **データレイヤの要件**を定義する。

v1.1 では、既に動作確認済みの

- 1分足ヒストリカル
- 5秒足リアルタイムロギング

に加え、**将来のスプレッド・コスト評価を見据えた拡張性**を要件に含める。

---

## 2. 対象スコープ

- 対象:
  - IBKR 経由の FX レートデータ (まずは USDJPY)
  - 1分足ヒストリカル
  - 5秒足リアルタイム
  - （将来）ティックベースの bid/ask ロギング

- 対象外（今バージョンでは検討のみ）:
  - 他社 API
  - 自動売買実行ロジック（Execution Engine）
  - 口座管理 / リスク管理

---

## 3. 機能要件 (FR)

### FR-1: 1分足ヒストリカル取得

- FR-1-1  
  指定期間 `[start_date, end_date]` の 1分足データを取得できること。

- FR-1-2  
  API 制限に応じて複数回に分割して取得し、整合性のある DataFrame として統合できること。

- FR-1-3  
  取得結果は  
  `data/ibkr/fx/USDJPY/min1/` 配下の Parquet として保存されること。

- FR-1-4  
  `time` カラムは tz-naive な `datetime64[ns]` とし、index に設定すること。  
  取得時に tz-aware（US/Eastern）であっても、Data Layer 内で tz-naive に正規化すること。

- FR-1-5（任意）  
  IBKR が提供する場合は `wap`, `barCount` 等の付加情報も保持可能とする。

---

### FR-2: 5秒足リアルタイムロギング

- FR-2-1  
  稼働中は USDJPY の 5秒足を連続的に取得し、メモリバッファに保持すること。

- FR-2-2  
  一定件数または一定時間ごと（例: 10秒）にバッファを Parquet に flush し、  
  **日次ファイルとして追記**すること。

- FR-2-3  
  Parquet ファイルは  
  `data/ibkr/fx/USDJPY/sec5/` 配下に保存されること。

- FR-2-4  
  アプリケーション終了時（KeyboardInterrupt 等）には、残データを flush してから切断すること。

- FR-2-5（拡張性要件）  
  5秒足 DataFrame は将来的に `bid`, `ask`, `mid`, `spread` カラムを追加できる設計とすること。  
  v1.1 時点では値が存在しなくてもよい（NaN 許容）。

---

### FR-3: データリロード

- FR-3-1  
  保存済みの Parquet ファイルから DataFrame を再構築できるヘルパー関数を提供すること。

- FR-3-2  
  1分足 / 5秒足データのロードは、  
  上位モジュール（feature builder / backtester / execution engine）が  
  **シンプルな API で呼び出せる**こと。

  例:
  - `load_min1("USDJPY", start, end) -> DataFrame`
  - `load_sec5("USDJPY", date) -> DataFrame`

---

### FR-4: ギャップ検出（v1.1〜 v1.2 で実装予定）

- FR-4-1  
  指定期間の 1分足 / 5秒足に対して、期待される時刻列と実データの index を比較し、  
  欠損・重複を検出できること。

- FR-4-2  
  検出結果をログまたはレポートとして出力すること  
  （例: 欠損区間リスト、重複タイムスタンプリスト）。

- FR-4-3（将来）  
  検出したギャップに対して、IBKR からの再取得（backfill）を自動で試行すること。

---

### FR-5: 1分足と5秒足の整合性チェック（将来）

- FR-5-1  
  5秒足から 1分足を aggregation し、既存 1分足ヒストリカルと比較するユーティリティを提供すること。

- FR-5-2  
  一致度をメトリクスとして出力し、データ品質評価に利用できること。

---

## 4. 非機能要件 (NFR)

### NFR-1: 安定性

- NFR-1-1  
  5秒足ロガーは 1日程度連続稼働してもメモリリーク等で落ちないこと  
  （当面は手動での停止を前提とする）。

- NFR-1-2  
  異常終了時も、既に flush 済みのデータは Parquet として利用可能であること。

---

### NFR-2: 再現性

- NFR-2-1  
  1分足の backfill と 5秒足の aggregation から、同一期間の OHLC が概ね一致すること。

- NFR-2-2  
  時刻の扱いはすべて **tz-naive（統一方針）** とし、  
  他タイムゾーンへの変換は別レイヤ（consumer側）で行うこと。

---

### NFR-3: 拡張性

- NFR-3-1  
  通貨ペア追加は設定を追加するだけで対応可能な構造とすること  
  （例: `config.yaml` / `symbols.json` 等）。

- NFR-3-2  
  足種追加（例: 15秒足、カスタムイベント足）は、  
  既存ストレージ構造 `data/ibkr/fx/{symbol}/{freq}/` を踏襲すること。

- NFR-3-3  
  将来の bid/ask/tick ロギングに対して、  
  5秒足 / 1分足スキーマが自然に拡張できるように設計すること。

---

### NFR-4: ログ・監査

- NFR-4-1  
  主要イベント（接続開始・切断・エラー・ファイル保存）はログ出力すること。

- NFR-4-2  
  ログは当面コンソール出力＋簡易ファイルログ（任意）とし、  
  将来の監視ツール導入を考慮したフォーマット（時間・レベル・メッセージ）とする。

---

## 5. 運用要件

- OU-1  
  当面は dev 環境（開発用 PC 上）で手動起動：
  - 1分足 backfill: 手動実行
  - 5秒足ロガー: 手動起動 → 手動停止

- OU-2  
  将来、stg/prod 環境ではスケジューラ（Windows タスクスケジューラ / systemd timer 等）での自動起動を検討する。

- OU-3  
  IBKR TWS/Gateway の再起動時に備え、接続リトライロジックまたは手動再起動手順を整備する。

- OU-4（将来）  
  stg/prod 環境では、**死活監視と通知（メール・Slack 等）**を導入し、  
  ロガー停止・エラーを早期に検知できるようにする。

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

- （将来）`loader` モジュール
  - `load_min1(symbol, start, end) -> DataFrame`
  - `load_sec5(symbol, start, end) -> DataFrame`

---

## 7. リスクと制約

- R-1: IBKR API 制限
  - コール頻度・取得可能期間に制約があるため、
    backfill 時は durationStr / sleep を調整する必要がある。

- R-2: TWS / Gateway 停止
  - dev 手動運用の間は、停止時にデータギャップが発生する。
  - ギャップ検出・backfill でカバーする方針とする。

- R-3: ローカルディスク容量
  - 秒足・ティックを長期間ためると容量圧迫の可能性がある。
  - 将来、古いデータのアーカイブ（圧縮 or オフロード）を検討する。

- R-4: タイムゾーン
  - IBKR のタイムゾーン（US/Eastern）とローカル（Asia/Tokyo）の違いに起因するバグリスクがある。  
    → Data Layer で tz-naive 統一し、以降のレイヤでのみ TZ を扱う方針でリスク低減。

---

## 8. 今後の拡張に向けた前提

- 将来的に forex03 以外のストラテジー（forex01, future01 等）も
  同じ Data Layer を共有する可能性があるため、
  モジュール名・ディレクトリ構造は汎用性を意識する。
- 将来の Currenex / Saxo 等 FIX ベースのデータソースに移行 / 追加する際も、  
  **Data Layer のインターフェースを維持したまま差し替え可能な設計**を志向する。
