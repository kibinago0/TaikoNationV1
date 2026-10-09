# TaikoNation Web UI タスク計画

## 概要
TaikoNationの学習済みモデル（osu!taiko譜面自動生成AI）をブラウザから直感的に操作できるモダンなWeb UIシステムを構築する。
Windows環境でダブルクリック一発で起動できる `.bat` 起動ファイルも用意する。

## タスク一覧
- [ ] ドキュメント群の作成 (`task.md`, `implementation_plan.md`, `walkthrough.md`)
- [ ] チェックポイント変換スクリプト (`convert_weights.py`) の作成と PyTorch モデル重み抽出
- [ ] 音楽特徴量抽出・譜面生成パイプラインモジュール (`engine.py`) の作成
  - 23msスライディングウィンドウによるメルスペクトログラム特徴量抽出
  - 1D-CNN + LSTM による推論とクラス確率サンプリング
  - `.osu` および `.osz` (zipアーカイブ) の生成
- [ ] FastAPI バックエンドサーバー (`server.py`) の作成
  - 楽曲アップロードエンドポイント (`/api/generate`)
  - 既存データセット楽曲の生成エンドポイント (`/api/preset-generate`)
  - 生成済み `.osu` / `.osz` のダウンロードエンドポイント
- [ ] プレミアムモダンWeb UI (`web/index.html`, `web/app.js`, `web/style.css`)
  - ダークモード、サイバーパンク/和風太鼓グラデーション
  - 音源ドラッグ＆ドロップ、BPM/メタデータ設定
  - 生成プログレス表示、譜面情報サマリー、ワンクリックダウンロード
  - 太鼓レーンプレビュー（再生機能）
- [ ] ワンクリック起動用バッチファイル (`start_web_ui.bat`) の作成
- [ ] 動作確認・テストの実施
