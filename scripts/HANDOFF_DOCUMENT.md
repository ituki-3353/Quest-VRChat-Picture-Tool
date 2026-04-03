# 🤖 AI向け引き継ぎドキュメント - QuestVRCTool v2.0

このドキュメントは、別のAI/開発ツールに当プロジェクトを引き継ぐ際に使用してください。  
以下の内容をコピー＆ペーストして、別のAIに指示を出すことで、スムーズに開発を継続できます。

---

## プロジェクト概要

**プロジェクト名**: QuestVRCTool v2.0  
**目的**: Meta Quest内のVRChatスクリーンショットをADB経由でPCへ転送する自動化ツール  
**構成**: Python GUI（tkinter）× バッチファイル（ADB実処理）ハイブリッド型

### アーキテクチャ図

```
┌─────────────────────────────────────────┐
│      Python GUI (main.py)               │
│  - フォルダ選択ダイアログ                 │
│  - 設定の保存/読み込み                    │
│  - ボタン操作→バッチ実行                  │
└────────────┬────────────────────────────┘
             │ subprocess.Popen()
             │ 引数: [batch_path, mode, target_path]
             ↓
┌─────────────────────────────────────────┐
│   バッチファイル (quest_tool.bat)        │
│  - ADB コマンド実行                      │
│  - エラーハンドリング                     │
│  - 画面出力・パス管理                     │
└────────────┬────────────────────────────┘
             │ adb device / pull
             ↓
┌─────────────────────────────────────────┐
│     Quest デバイス 他 外部システム        │
└─────────────────────────────────────────┘
```

---

## ファイル仕様

### 1. `main.py` - Pythonフロントエンド

**役割**: ユーザーインタラクション、バッチファイル呼び出し、設定管理

**主な機能**:
- tkinter GUI（Windows標準・依存なし）
- フォルダ選択ダイアログ
- json形式の設定ファイル読み書き
- subprocess 経由でバッチを実行（新し いコマンドプロンプトウィンドウで）

**重要な構造**:
```python
def load_config():
    # config.json から保存先パスを読み込み

def save_config(config):
    # 変更を config.json に保存

def browse_folder():
    # filedialog で保存先を選択

def run_import():
    # subprocess.Popen([batch_path, "import", target_path], ...)

def run_config():
    # subprocess.Popen([batch_path, "config"], ...)

def run_test():
    # subprocess.Popen([batch_path, "test"], ...)
```

**実行方法**:
```bash
python main.py
```

---

### 2. `quest_tool.bat` - バッチファイル実行エンジン

**役割**: ADB コマンド実行、ファイル転送、エラーチェック

**呼び出し形式**:
```batch
quest_tool.bat <MODE> [TARGET_PATH]
```

**モード一覧**:

| モード | 説明 | 第2引数 | 用途 |
|--------|------|--------|------|
| `import` | VRC写真転送 | 保存先フォルダ | メイン処理 |
| `config` | 接続確認 | なし | デバッグ用 |
| `test` | ADB テスト | なし | 環境確認用 |

**各モードの処理フロー**:

#### `import` モード
1. ADBサーバー起動（adb start-server）
2. デバイスリスト確認（adb devices）
3. ターゲットフォルダ存在確認（なければ作成）
4. ファイル転送実行（adb pull）
5. 結果を画面表示（pause で保持）

#### `config` モード
1. ADB デバイス詳細リスト表示（adb devices -l）
2. 結果を画面表示（pause で保持）

#### `test` モード
1. ADB バージョン確認（adb version）
2. デバイスリスト表示（adb devices）
3. 結果を画面表示（pause で保持）

**エラーハンドリング**:
- errorlevel チェック（ADB失敗時の検出）
- ターゲットフォルダ作成失敗時の警告
- パス不正時の明示的なエラー表示

---

### 3. `config.json` - ユーザー設定ファイル

**役割**: 保存先フォルダパスの永続化

**初期値**:
```json
{
  "target_path": "S:\\VRChat-Picture\\Pics",
  "comment": "保存先フォルダパス。GUIで変更可能。"
}
```

**自動更新**: ユーザーが GUI 上でフォルダを選び直すと、Python が自動的に更新

---

## 実装済み機能

✅ GUI フロームワーク（tkinter）  
✅ 保存先フォルダ選択ダイアログ  
✅ 設定ファイル（JSON）の読み書き  
✅ バッチファイルへの引数渡し  
✅ エラーハンドリング（ADB未インストール等）  
✅ ステータス表示  
✅ 複数モード対応（import/config/test）  

---

## 次のステップ・拡張案

### 短期（推奨）
- [ ] **ロギング機能**: 実行履歴をファイルに保存
- [ ] **転送状況表示**: 進捗バー、ファイル数表示
- [ ] **複数デバイス対応**: ドロップダウンでデバイス選択
- [ ] **EXE化**: PyInstaller で単一ファイル化

### 中期
- [ ] **スケジュール実行**: 定期的な自動転送
- [ ] **UI改善**: ログウィンドウ、詳細設定パネル
- [ ] **バージョンチェック**: 起動時に古いバージョンを検出

### 長期
- [ ] **マルチアカウント対応**: 複数ユーザーの設定管理
- [ ] **クラウド同期**: OneDrive 統合等
- [ ] **プラグイン機構**: カスタム処理の追加機能

---

## 開発者向け指示テンプレート

以下のメッセージを、別のAI/ツールにそのままコピペできます：

> 「QuestVRCTool v2.0 を継続開発してください。
> 
> **前提**:
> - Python GUI（tkinter）とバッチファイルのハイブリッド構成
> - subprocess で引数付きバッチを実行する手法を使用
> - 保存先フォルダは GUI で選択可能、config.json に自動保存
> 
> **今回の要件**:
> [ここに具体的な要件を記述]
> 
> 実装時は、以下を参考にしてください:
> - [AI向け引き継ぎドキュメント]の「ファイル仕様」セクション
> - Git ブランチは `feature/XXX` で開発
> - PR 前に README.md も更新してください」

---

## トラブルシューティング（開発者向け）

| 問題 | 原因 | 対処 |
|------|------|------|
| subprocess 実行しません | batch_path が相対パス | `os.path.join(os.path.dirname(__file__), "quest_tool.bat")` を使用 |
| 引数が渡されていない | Popen 引数の形式が誤る | リスト形式で `[batch_path, arg1, arg2]` と指定 |
| config.json が読み込めない | エンコード問題 | `encoding="utf-8"` を明示指定 |
| ADB コマンド不明 | PATH が通ってない | ユーザーに Platform-Tools インストール指示 |
| 日本語ファイル名が文字化け | バッチ内のコード設定 | バッチ冒頭に `chcp 65001` を追加 |

---

## 技術スタック

| レイヤー | 使用技術 | 理由 |
|---------|---------|------|
| GUI | Python 3.7+ tkinter | 依存なし、Windows標準 |
| スクリプト | バッチファイル（.bat） | ADB実行, 既存資産活用 |
| IPC | subprocess.Popen | クロスプラットフォーム対応 |
| 設定保存 | JSON | 人間が読みやすい、標準フォーマット |

---

## 参考資料・リンク

- [tkinter 公式ドキュメント](https://docs.python.org/3/library/tkinter.html)
- [Android Debug Bridge (ADB) 公式](https://developer.android.com/tools/adb)
- [subprocess モジュール - 公式ドキュメント](https://docs.python.org/3/library/subprocess.html)
- [PyInstaller - EXE化ツール](https://pyinstaller.readthedocs.io/)

---

## ライセンス・使用条件

このツールは個人・組織内での使用を想定しています。  
商用利用、配布には要相談。

---

**最終更新**: 2026年4月3日  
**バージョン**: 2.0  
**ステータス**: 実装完了、テスト待ち
