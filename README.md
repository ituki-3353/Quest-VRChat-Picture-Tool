# QuestVRCTool v2.0 - ドキュメント

## 現在開発中です。README通りの使用ではない可能性があります。ご了承ください。

## 概要
Meta Quest内のVRChatスクリーンショットを、ADB経由でPC（SMBサーバー等）へ転送するGUIツールです。

Python（tkinter）をフロントエンド、バッチファイル（quest_tool.bat）をバックエンドとして使用しています。

## ファイル構成

```
QuestVRC/
├── main.py              # GUI フロントエンド（Python）
├── quest_tool.bat       # 実処理ロジック（バッチファイル）
├── config.json          # ユーザー設定（保存先パス）
└── README.md            # このファイル
```

## 必要な環境

- **Python 3.7+**（tkinterは標準ライブラリに含まれる）
- **ADB（Android Debug Bridge）**
  - インストール方法: Android SDK Platform-Tools をインストール
  - PATH環境変数に追加必要

## 使用方法

### 1. 起動
```bash
python main.py
```

### 2. GUI操作

#### 📁 保存先フォルダ設定
1. デフォルトパス: `S:\VRChat-Picture\Pics`
2. 「参照...」ボタンでカスタム保存先を選択
3. 選択内容は自動的に `config.json` に保存

#### 1️⃣ Import VRC Pictures
- VRChatのスクリーンショットをQuest → PCへ転送
- ADBサーバー起動 → デバイス確認 → ファイル転送
- 指定された保存先フォルダに画像が保存される

#### 2️⃣ Check Connection
- Quest の接続状況を確認
- ADB接続が正常か確認する際に使用

#### 3️⃣ Test Mode
- ADBバージョン情報とデバイスリストを表示
- システムのセットアップ検証用

#### Exit
- アプリケーション終了

## バッチファイル仕様 (`quest_tool.bat`)

### 実行形式

```batch
quest_tool.bat <mode> [target_path]
```

### パラメータ

| モード | 説明 | 第2引数 |
|--------|------|--------|
| `import` | VRC写真をインポート | 保存先フォルダパス（オプション） |
| `config` | 接続状況を確認 | なし |
| `test` | テストモード実行 | なし |

### 例

```batch
# デフォルト保存先でインポート
quest_tool.bat import

# カスタム保存先でインポート
quest_tool.bat import "D:\MyPictures\VRChat"

# 接続確認
quest_tool.bat config

# テスト
quest_tool.bat test
```

## Python GUI仕様 (`main.py`)

### 主要機能

- **フォルダ選択ダイアログ**: tkinter の `filedialog.askdirectory()` を使用
- **設定の永続化**: `config.json` に保存先パスを自動保存
- **エラーハンドリング**: ADB未インストール、ファイルパス不正時のメッセージ表示
- **ステータス表示**: 実行状況をリアルタイムで表示

### コード構成

```python
load_config()           # 設定を JSON から読み込み
save_config(config)     # 設定を JSON に保存
browse_folder()         # フォルダ選択ダイアログ
run_import()           # インポート実行
run_config()           # 接続確認実行
run_test()             # テスト実行
```

## トラブルシューティング

### ❌ "ADBコマンドが見つかりません"
- **原因**: ADB がインストールされていない
- **対処**: Android SDK Platform-Tools をインストールし、PATH に追加

### ❌ "Questが接続されていません"
- **原因**: USBケーブルが未接続または認識されていない
- **対処**: 
  - USBケーブルを確認
  - Quest に「このコンピュータを信頼しますか？」と出た場合は「許可」をタップ
  - "2️⃣ Check Connection" で再度確認

### ❌ "ターゲットフォルダの作成に失敗しました"
- **原因**: 指定パスが無効または権限がない
- **対処**: 
  - パスが存在しているか確認
  - SMBサーバーへのマウントを確認
  - ドライブがオンラインか確認
