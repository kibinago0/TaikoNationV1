# 実装計画書: TaikoNation Web UI

## 1. 目的とスコープ
ローカルのTaikoNation（osu!taiko譜面自動生成システム）をWebブラウザから操作可能にし、任意の音楽ファイル（MP3/WAV/OGG等）をアップロードするだけで、osu!で即座に遊べる `.osz` / `.osu` パッケージを生成・ダウンロードできるWebアプリケーションを構築する。

## 2. システム構成
- **推論エンジン**: `engine.py`
  - `output/model/model.tfl` より重みを抽出し、PyTorchモデルとして即時ロード
  - `librosa` / `ffmpeg` による音声読み込みとメル特徴量算出（23ms刻み、80バンド、DDC規格準拠）
  - モデル推論によるノーツ判定（ドン、カツ、大ドン、大カツ、連打）
  - osu!taiko (Mode: 1) の `.osu` ファイルフォーマットへの整形
  - 楽曲音源と `.osu` をまとめた `.osz` (ZIP) パッケージング
- **バックエンド API**: `server.py` (FastAPI / Uvicorn)
  - `/api/generate`: 音楽ファイルアップロード & 譜面生成
  - `/api/presets`: リポジトリ内のサンプル楽曲リスト
  - `/api/download/{task_id}/{file_type}`: 生成ファイルの配信
  - `/api/preview/{task_id}`: 生成ノーツデータ配信（ブラウザでのプレビュー用）
  - 静的ファイル配信 (`/` -> `web/index.html`)
- **フロントエンド UI**: `web/` (HTML / CSS / JavaScript)
  - 高品位なダークテーマ & 和風モダン太鼓ネオンUI
  - 音声ドラッグ＆ドロップ、タイトル・アーティスト・BPM等のメタデータ設定
  - プログレスバー & リアルタイムステータス表示
  - 太鼓レーンプレビュー（Web Audio API連動で音源に合わせて流れるノーツ表示）
  - `.osz` / `.osu` ワンクリックダウンロード
- **ワンクリック起動**: `start_web_ui.bat`
  - Python環境の自動検出
  - サーバーの起動と既定のWebブラウザの自動オープン

## 3. 実装手順
1. `convert_weights.py` によるモデル重みの安全な抽出と `.pt` 保存
2. `engine.py` の実装（特徴量抽出、モデル推論、osu/osz生成）
3. `server.py` の実装（FastAPIエンドポイント、静的ファイルホスティング）
4. `web/` ディレクトリ配下にモダンなUIを構築 (`index.html`, `style.css`, `app.js`)
5. `start_web_ui.bat` の作成
6. バックエンドテストおよびブラウザ表示確認
7. `walkthrough.md` の作成
