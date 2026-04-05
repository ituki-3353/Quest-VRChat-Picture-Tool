# QuestVRCTool

## 概要
QuestVRCTool は、Meta Quest 内の VRChat スクリーンショットを ADB 経由で PC に転送し、リネームして保存する Windows 向けツールです。

- GUI 版フロントエンド: `scripts/main.py`
- Quest 側操作: `quest_tool.bat`
- 設定保存: `config.json`, `default_conf.json`, `version_conf.json`
- アイコン: `scripts/icon.ico`
- タイトルロゴ: `scripts/logo.png`

このリポジトリは Git で配布・管理することを想定しています。

## 目次

- [必要要件](#必要要件)
- [リポジトリ構成](#リポジトリ構成)
- [ソースから起動](#ソースから起動)
- [実行ファイルのビルド](#実行ファイルのビルド)
- [使い方](#使い方)
- [設定ファイル](#設定ファイル)
- [トラブルシューティング](#トラブルシューティング)
- [ライセンス](#ライセンス)

## 必要要件

- Windows 10 / Windows 11
- Python 3.11 以上
- `tkinter`（標準ライブラリ）
- ADB（Android Debug Bridge）
  - Android SDK Platform-Tools をインストール
  - `adb` が `PATH` に通っていること
- PyInstaller（実行ファイルを作成する場合）

### 推奨インストール

```powershell
python -m pip install pyinstaller
```

## リポジトリ構成

```
QuestVRC/
├── .gitignore
├── LICENSE
├── README.md
├── QuestVRCTool.exe         # 既存ビルドがある場合
├── QuestVRCTool.spec
├── dist/                    # PyInstaller 出力フォルダ
├── build/                   # PyInstaller ビルドフォルダ
├── main.spec                # ルートの PyInstaller spec
└── scripts/
    ├── main.py              # メイン GUI アプリ
    ├── quest_tool.bat       # ADB/Quest 処理バッチ
    ├── config.json          # 実行時に読み書きされる設定ファイル
    ├── default_conf.json    # デフォルト設定保存用
    ├── version_conf.json    # バージョン番号・ビルド番号
    ├── icon.ico             # ウィンドウ／EXE アイコン
    ├── logo.png             # タイトルロゴ
    └── main.spec            # scripts 用 PyInstaller spec
```

## ソースから起動

1. リポジトリをクローン／展開
2. PowerShell でリポジトリルートに移動
3. 次のコマンドを実行

```powershell
python scripts/main.py
```

> `scripts/main.py` は、実行中のファイルのある場所に `config.json` を保存します。
> - ソース実行時: `scripts\config.json`
> - EXE 実行時: 実行ファイルと同じフォルダ内

## 実行ファイルのビルド

Git で配布する場合、ソースを配布するか、または PyInstaller でバイナリを作成します。

```powershell
cd C:\Users\ituki\Desktop\QuestVRC
python -m PyInstaller --onefile --windowed --name QuestVRCTool --icon=scripts/icon.ico --add-data "scripts/config.json;." --add-data "scripts/default_conf.json;." --add-data "scripts/version_conf.json;." --add-data "scripts/logo.png;." scripts/main.py
```

ビルドが成功すると、`dist\QuestVRCTool.exe` が作成されます。

## 使い方

1. `QuestVRCTool.exe` または `python scripts/main.py` で起動
2. GUI で保存先フォルダを設定
3. `Import VRC Pictures` を実行して Quest から画像を取り込む
4. `Check Connection` で接続状況を確認
5. `Test Mode` で ADB 接続・デバイス状態を検証

### 画面の主な操作

- `保存先フォルダ`: スクリーンショットを保存するフォルダを指定
- `ADB auto start`: ADB を自動起動するかどうか
- `Load Default Settings`: デフォルト設定を `config.json` と `default_conf.json` に書き出す

## 設定ファイル

- `config.json`: 実行時に読み書きされる現在設定
- `default_conf.json`: デフォルト値のバックアップ
- `version_conf.json`: アプリ版数とビルド番号

### version_conf.json の例

```json
{
  "version": "0.3.0 beta",
  "build_number": "202504050201728-beta"
}
```

## トラブルシューティング

### ADB が見つからない

- `adb` がインストールされていない、または PATH に含まれていない場合、GUI 内でエラーが表示されます。
- `Android SDK Platform-Tools` をインストールし、`adb` をコマンドラインで実行できるようにしてください。

### Quest が認識されない

- USB ケーブルを確認
- Quest の USB デバッグを許可する
- `Check Connection` を実行してデバイス一覧を確認

### 保存先フォルダに書き込めない

- マウント先や SMB 共有がオンラインであることを確認
- フォルダパスのアクセス権限を確認

## Git で配布するための注意

- ソースを配布する場合は、`scripts/` 以下を含めることで動作します。
- バイナリ配布の場合は `dist/QuestVRCTool.exe` を配布先に添付してください。
- `build/` や `dist/` は通常コミットしないため、必要に応じて `.gitignore` に追加してください。

## ライセンス

本プロジェクトは `LICENSE` に記載されたライセンスのもとで配布されます。
