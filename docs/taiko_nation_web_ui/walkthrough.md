# TaikoNation Web UI ウォークスルー & 操作ガイド

## 概要
TaikoNation（osu!taiko譜面自動生成AI）をローカル環境で手軽に操作できるWeb UIシステムを構築しました。
Windows上でダブルクリックするだけでサーバーが起動し、ブラウザで楽曲（MP3, WAV, OGG, FLAC等）をアップロードするだけで、osu!でそのまま遊べる `.osz` / `.osu` 譜面が瞬時に自動生成されます。

---

## 1. 起動方法 (Windows)

プロジェクトルートの [`start_web_ui.bat`](file:///c:/Users/user/TaikoNationV1/start_web_ui.bat) をダブルクリックするだけで起動できます。

- 実行するとローカルサーバー（FastAPI）が立ち上がり、既定のブラウザで自動的に `http://127.0.0.1:8000` が開きます。
- 終了したい場合は、起動したコマンドプロンプト画面で `Ctrl + C` を押すかウィンドウを閉じてください。

---

## 2. 画面構成と主な機能

### ① 楽曲の選択・アップロード
- **ファイルアップロード**: お好きな音楽ファイル（MP3, WAV, OGG, FLAC等）をドラッグ＆ドロップまたはファイル選択ダイアログからアップロードできます。ファイル名からタイトル・アーティスト名が自動推測されます。
- **プリセット楽曲**: リポジトリ付属の100曲近いデータセットから楽曲を選択し、音源のアップロードなしで即座にAI推論・譜面生成をテストできます。

### ② 生成パラメータ設定
- **難易度名 (Version)**: 鬼 (Oni)、おに裏 (Inner Oni)、むずかしい (Muzukashii)、ふつう (Futsuu) などから選択可能。
- **ノーツ密度 (Note Density)**: 0.5x ～ 2.0x の範囲でスライダー調整可能。
- **サンプリング温度 (Creativity)**: 0.2 ～ 1.5 の範囲で調整可能（低めだと堅実なリズム、高めだと多彩なパターン）。

### ③ AI推論と譜面プレビュー
- **リアルタイム生成進捗**: メルスペクトログラム特徴量抽出 → CNN + LSTM 推論 → osu!形式パッケージングの進行状況がアニメーション表示されます。
- **譜面サマリー**: 総ノーツ数、ドン（赤）、カツ（青）、楽曲の長さを集計表示。
- **太鼓レーンプレビュー**: Web Audio APIと連動し、音源の再生に合わせて生成されたドン・カツ・大音符が右から左へ流れるインタラクティブなアニメーションで確認できます。

### ④ ワンクリックダウンロード
- **.osz 形式パッケージ**: 楽曲音源 (`audio.mp3`) と譜面データ (`chart.osu`) がひとまとめにZIP圧縮されたosu!用パッケージ。ダウンロードしたファイルをosu!の画面にドラッグ＆ドロップするだけで即座にプレイ可能です。
- **.osu 形式**: 譜面テキスト単体のファイル（エディタでの編集や分析向け）。

---

## 3. 作成・変更したファイル

| ファイルパス | 内容・役割 |
|---|---|
| [`convert_weights.py`](file:///c:/Users/user/TaikoNationV1/convert_weights.py) | 既存のTensorFlow 1.x チェックポイントから全レイヤーの重みを抽出し、PyTorch形式 (`output/model/taiko_nation_pytorch.pt`) へ完全移植するコンバータ |
| [`engine.py`](file:///c:/Users/user/TaikoNationV1/engine.py) | Librosa音声解析（23msウィンドウ）、PyTorch推論、osu!taiko (Mode 1) フォーマット生成、osz圧縮を担うコアモジュール |
| [`server.py`](file:///c:/Users/user/TaikoNationV1/server.py) | FastAPIによるREST APIバックエンド。ファイル受信、推論実行、ファイルダウンロード、静的Webサイト配信を提供 |
| [`web/index.html`](file:///c:/Users/user/TaikoNationV1/web/index.html) | 洗練された和風サイバーパンク/ダークテーマのUIレイアウト |
| [`web/style.css`](file:///c:/Users/user/TaikoNationV1/web/style.css) | レスポンシブデザイン、グラスモフィズム、ネオンシャドウ、アニメーションスタイル |
| [`web/app.js`](file:///c:/Users/user/TaikoNationV1/web/app.js) | ドラッグ＆ドロップ、API連携、HTML5 Canvasによる太鼓レーンプレビュー描画 |
| [`start_web_ui.bat`](file:///c:/Users/user/TaikoNationV1/start_web_ui.bat) | Python環境を自動検出し、ブラウザを開いてサーバーを起動するワンクリックバッチ |
| [`docs/taiko_nation_web_ui/task.md`](file:///c:/Users/user/TaikoNationV1/docs/taiko_nation_web_ui/task.md) | タスク管理記録 |
| [`docs/taiko_nation_web_ui/implementation_plan.md`](file:///c:/Users/user/TaikoNationV1/docs/taiko_nation_web_ui/implementation_plan.md) | 実装手順書 |
| [`docs/taiko_nation_web_ui/walkthrough.md`](file:///c:/Users/user/TaikoNationV1/docs/taiko_nation_web_ui/walkthrough.md) | 変更概要および操作ガイド（本ファイル） |

---

## 4. 動作検証結果
- **モデル重み抽出**: 既存の `output/model/model.tfl` より CNN・LSTM・全結合層の全パラメータを正常抽出完了。
- **推論テスト**: プリセット曲およびランダム波形での推論を検証。1曲（約4分）あたり数秒で1,700ノーツ以上の譜面を正確に生成可能であることを確認。
- **APIおよびWeb UI配信**: `http://127.0.0.1:8000` でサーバー起動および `.osz` / `.osu` ダウンロード機能が正常動作することを確認済み。
