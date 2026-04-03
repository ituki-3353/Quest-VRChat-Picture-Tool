import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import subprocess
import os
import json
import locale

# 文字コード設定
os.environ['PYTHONIOENCODING'] = 'utf-8'
locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')

# 設定ファイルパス
CONFIG_FILE = "config.json"

# デフォルト設定
DEFAULT_CONFIG = {
    "target_path": r"S:\VRChat-Picture",
    "rename_suffix": "_Quest",
    "adb_auto_start": True,
    "comment": "保存先フォルダパス、リネーム設定など。GUIで変更可能。"
}

def load_config():
    """設定ファイルから読み込む"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # デフォルト値とマージ
                merged = {**DEFAULT_CONFIG, **config}
                return merged
        except Exception as e:
            messagebox.showerror("エラー", f"設定ファイルの読み込みに失敗しました: {e}")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    """設定ファイルに保存"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("エラー", f"設定ファイルの保存に失敗しました: {e}")
        return False

def browse_folder():
    """フォルダ選択ダイアログを開く"""
    current_path = target_path_var.get()
    folder = filedialog.askdirectory(
        title="保存先フォルダを選択",
        initialdir=current_path if os.path.exists(current_path) else os.path.expanduser("~")
    )
    if folder:
        target_path_var.set(folder)
        # 自動保存
        save_settings()

def save_settings():
    """設定タブの入力値をconfig.jsonに保存"""
    config = {
        "target_path": target_path_var.get(),
        "rename_suffix": rename_suffix_var.get(),
        "adb_auto_start": adb_auto_start_var.get(),
        "comment": "保存先フォルダパス、リネーム設定など。GUIで変更可能。"
    }
    if save_config(config):
        status_var.set("✓ 設定を保存しました")

def reset_settings():
    """設定をリセット"""
    if messagebox.askyesno("確認", "設定をデフォルト値にリセットしますか？"):
        target_path_var.set(DEFAULT_CONFIG["target_path"])
        rename_suffix_var.set(DEFAULT_CONFIG["rename_suffix"])
        adb_auto_start_var.set(DEFAULT_CONFIG["adb_auto_start"])
        save_settings()
        status_var.set("✓ 設定をリセットしました")


def run_import():
    """VRC写真をインポート（Python実装）"""
    target_path = target_path_var.get()
    rename_suffix = rename_suffix_var.get()

    if not target_path.strip():
        messagebox.showwarning("警告", "保存先フォルダを指定してください。")
        return

    try:
        status_var.set("▶ 実行中: インポートタスク...")

        # ADBコマンドの存在確認
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=10, encoding='utf-8')
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror("エラー", "ADBコマンドが見つかりません。\nADBをインストールしてPATHに追加してください。")
            status_var.set("✗ ADBが見つかりません")
            return

        # ADBサーバー起動
        status_var.set("▶ ADBサーバー起動中...")
        try:
            result = subprocess.run(["adb", "start-server"], capture_output=True, text=True, timeout=30, encoding='utf-8')
            if result.returncode != 0:
                messagebox.showwarning("警告", f"ADBサーバー起動に失敗しました:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            messagebox.showwarning("警告", "ADBサーバー起動がタイムアウトしました。")

        # デバイス確認
        status_var.set("▶ デバイス確認中...")
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10, encoding='utf-8')
        if "device" not in result.stdout or "unauthorized" in result.stdout:
            messagebox.showerror("エラー", "Questが正しく接続されていません。\n• USBケーブルを確認\n• USBデバッグモードを確認\n• 信頼設定を確認")
            status_var.set("✗ Questが接続されていません")
            return

        # ターゲットディレクトリ作成
        if not os.path.exists(target_path):
            try:
                os.makedirs(target_path)
            except Exception as e:
                messagebox.showerror("エラー", f"保存先フォルダの作成に失敗しました:\n{e}")
                status_var.set("✗ フォルダ作成失敗")
                return

        # ファイル転送
        status_var.set("▶ VRChatスクリーンショットを転送中...")
        source_path = "/storage/emulated/0/Pictures/VRChat"
        result = subprocess.run(["adb", "pull", source_path, target_path],
                              capture_output=True, text=True, timeout=300, encoding='utf-8')

        if result.returncode != 0:
            messagebox.showerror("エラー", f"ファイル転送に失敗しました:\n{result.stderr}")
            status_var.set("✗ 転送失敗")
            return

        # ファイルリネーム処理
        status_var.set("▶ ファイルをリネーム中...")
        vrchat_dir = os.path.join(target_path, "VRChat")
        if os.path.exists(vrchat_dir):
            renamed_count = 0
            for root, dirs, files in os.walk(vrchat_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    filename, ext = os.path.splitext(file)

                    # 既にリネーム済みかチェック
                    if not filename.endswith(rename_suffix):
                        new_filename = filename + rename_suffix + ext
                        new_filepath = os.path.join(root, new_filename)

                        try:
                            os.rename(filepath, new_filepath)
                            renamed_count += 1
                        except Exception as e:
                            print(f"リネーム失敗: {filepath} -> {e}")

            status_var.set(f"✓ 完了: {renamed_count}個のファイルをリネーム")
        else:
            status_var.set("✓ 完了: 新しいファイルなし")

        messagebox.showinfo("成功", f"VRChat写真のインポートが完了しました！\n保存先: {target_path}")

    except Exception as e:
        messagebox.showerror("エラー", f"予期しないエラーが発生しました:\n{e}")
        status_var.set("✗ エラーが発生しました")

def run_config():
    """接続状況を確認（Python実装）"""
    try:
        status_var.set("▶ 接続状況を確認中...")

        # ADBコマンドの存在確認
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=10, encoding='utf-8')
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror("エラー", "ADBコマンドが見つかりません。\nADBをインストールしてPATHに追加してください。")
            status_var.set("✗ ADBが見つかりません")
            return

        # デバイス詳細リスト表示
        result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=10, encoding='utf-8')

        if result.returncode == 0:
            device_info = result.stdout.strip()
            if device_info and "device" in device_info:
                messagebox.showinfo("接続状況", f"接続されたデバイス:\n\n{device_info}")
                status_var.set("✓ デバイス接続確認完了")
            else:
                messagebox.showwarning("接続状況", "接続されたデバイスが見つかりません。\n\nQuestが正しく接続されているか確認してください。")
                status_var.set("⚠ デバイス未接続")
        else:
            messagebox.showerror("エラー", f"ADBコマンド実行エラー:\n{result.stderr}")
            status_var.set("✗ ADBエラー")

    except subprocess.TimeoutExpired:
        messagebox.showerror("エラー", "ADBコマンドがタイムアウトしました。")
        status_var.set("✗ タイムアウト")
    except Exception as e:
        messagebox.showerror("エラー", f"予期しないエラーが発生しました:\n{e}")
        status_var.set("✗ エラーが発生しました")

def run_test():
    """テストモード（Python実装）"""
    try:
        status_var.set("▶ テスト実行中...")

        test_results = []
        test_results.append("========================================\n   テストモード\n========================================")

        # ADBバージョン確認
        test_results.append("\n[テスト] ADB バージョン確認")
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=10, encoding='utf-8')
            if result.returncode == 0:
                test_results.append(result.stdout.strip())
            else:
                test_results.append(f"ADBバージョン取得失敗: {result.stderr}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            test_results.append("ADBコマンドが見つかりません。ADBをインストールしてください。")

        # デバイスリスト
        test_results.append("\n[テスト] デバイス リスト")
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10, encoding='utf-8')
            test_results.append(result.stdout.strip() or "デバイスが見つかりません")
        except subprocess.TimeoutExpired:
            test_results.append("ADBデバイス確認がタイムアウトしました")

        # 設定ファイル内容
        test_results.append("\n[テスト] 設定ファイル内容 (config.json)")
        test_results.append("----------------------------------------")
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_content = f.read()
                test_results.append(config_content)
            except Exception as e:
                test_results.append(f"設定ファイル読み込みエラー: {e}")
        else:
            test_results.append("config.json ファイルが見つかりません。")
        test_results.append("----------------------------------------")

        # ターゲットパスの確認
        test_results.append("\n[テスト] ターゲットパスの確認")
        test_results.append("")
        test_results.append("[GUI設定] config.json から読み込んだ値:")
        try:
            config = load_config()
            test_results.append(f"target_path: {config.get('target_path', '未設定')}")
            test_results.append(f"rename_suffix: {config.get('rename_suffix', '未設定')}")
            test_results.append(f"adb_auto_start: {config.get('adb_auto_start', '未設定')}")
        except Exception as e:
            test_results.append(f"（設定読み込みエラー: {e}）")
        test_results.append("")
        test_results.append("[実行時引数] コマンドラインから渡された値:")
        test_results.append("ターゲットパス（第2引数）: 指定されていません")

        test_results.append("\n========================================\nテストモードが終了しました。")

        # 結果をメッセージボックスで表示
        result_text = "\n".join(test_results)
        messagebox.showinfo("テスト結果", result_text)
        status_var.set("✓ テスト完了")

    except Exception as e:
        messagebox.showerror("エラー", f"テスト実行中にエラーが発生しました:\n{e}")
        status_var.set("✗ テストエラー")

# メインウィンドウ
root = tk.Tk()
root.title("QuestVRCTool v2.0")
root.geometry("600x550")
root.resizable(False, False)

# 設定の読み込み
config = load_config()
target_path_var = tk.StringVar(value=config.get("target_path", DEFAULT_CONFIG["target_path"]))
rename_suffix_var = tk.StringVar(value=config.get("rename_suffix", DEFAULT_CONFIG["rename_suffix"]))
adb_auto_start_var = tk.BooleanVar(value=config.get("adb_auto_start", DEFAULT_CONFIG["adb_auto_start"]))
status_var = tk.StringVar(value="待機中...")

# === タイトル部分 ===
title_frame = ttk.Frame(root)
title_frame.pack(pady=10, padx=10, fill=tk.X)

title_label = ttk.Label(
    title_frame,
    text="Quest VRChat Tool",
    font=("Arial", 18, "bold")
)
title_label.pack(side=tk.LEFT)

version_label = ttk.Label(
    title_frame,
    text="v2.0",
    font=("Arial", 10),
    foreground="gray"
)
version_label.pack(side=tk.LEFT, padx=5)

# === 警告メッセージ ===
warning_label = ttk.Label(
    root,
    text="⚠ 注意: ADBサーバーが必要です / USB デバッグモードを有効にしてください",
    font=("Arial", 9),
    foreground="red"
)
warning_label.pack(pady=5, padx=10)

# === タブウィジェット ===
notebook = ttk.Notebook(root)
notebook.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

# ============== タブ1: 実行 ==============
run_tab = ttk.Frame(notebook, padding=15)
notebook.add(run_tab, text="実行")

# ボタン領域
buttons_frame = ttk.Frame(run_tab)
buttons_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

# インポートボタン
import_button = ttk.Button(
    buttons_frame,
    text="1️⃣  Import VRC Pictures",
    command=run_import,
    width=40
)
import_button.pack(pady=8, ipady=10)

# 設定確認ボタン
config_button = ttk.Button(
    buttons_frame,
    text="2️⃣  Check Connection",
    command=run_config,
    width=40
)
config_button.pack(pady=8, ipady=10)

# テストボタン
test_button = ttk.Button(
    buttons_frame,
    text="3️⃣  Test Mode",
    command=run_test,
    width=40
)
test_button.pack(pady=8, ipady=10)

# 終了ボタン
exit_button = ttk.Button(
    buttons_frame,
    text="Exit",
    command=root.destroy,
    width=40
)
exit_button.pack(pady=8, ipady=10)

# ============== タブ2: 設定 ==============
settings_tab = ttk.Frame(notebook, padding=15)
notebook.add(settings_tab, text="設定")

# 保存先フォルダ設定
path_frame = ttk.LabelFrame(settings_tab, text="📁 保存先フォルダ", padding=10)
path_frame.pack(pady=10, fill=tk.X)

path_label = ttk.Label(path_frame, text="保存先:", font=("Arial", 10))
path_label.grid(row=0, column=0, sticky=tk.W, pady=5)

path_entry = ttk.Entry(path_frame, textvariable=target_path_var, width=45)
path_entry.grid(row=0, column=1, padx=5, pady=5)

browse_button = ttk.Button(path_frame, text="参照...", command=browse_folder, width=10)
browse_button.grid(row=0, column=2, padx=5, pady=5)

# ファイル名リネーム設定
rename_frame = ttk.LabelFrame(settings_tab, text="📝 ファイルリネーム", padding=10)
rename_frame.pack(pady=10, fill=tk.X)

rename_label = ttk.Label(rename_frame, text="リネーム末尾:", font=("Arial", 10))
rename_label.grid(row=0, column=0, sticky=tk.W, pady=5)

rename_entry = ttk.Entry(rename_frame, textvariable=rename_suffix_var, width=20)
rename_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

rename_ex_label = ttk.Label(
    rename_frame,
    text="例) photo.png → photo_Quest.png",
    font=("Arial", 9),
    foreground="gray"
)
rename_ex_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

# ADB設定
adb_frame = ttk.LabelFrame(settings_tab, text="⚙️ ADB設定", padding=10)
adb_frame.pack(pady=10, fill=tk.X)

adb_check = ttk.Checkbutton(
    adb_frame,
    text="実行時にADBサーバーを自動起動",
    variable=adb_auto_start_var
)
adb_check.pack(anchor=tk.W, pady=5)

# ボタングループ
button_group = ttk.Frame(settings_tab)
button_group.pack(pady=20, fill=tk.X)

save_button = ttk.Button(
    button_group,
    text="💾 設定を保存",
    command=save_settings,
    width=20
)
save_button.pack(side=tk.LEFT, padx=5)

reset_button = ttk.Button(
    button_group,
    text="🔄 リセット",
    command=reset_settings,
    width=20
)
reset_button.pack(side=tk.LEFT, padx=5)

# ============== タブ3: 説明 ==============
help_tab = ttk.Frame(notebook, padding=15)
notebook.add(help_tab, text="説明")

# スクロール可能なテキスト領域
help_text_frame = ttk.Frame(help_tab)
help_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# スクロールバー付きテキスト
scrollbar = ttk.Scrollbar(help_text_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

help_text = tk.Text(
    help_text_frame,
    wrap=tk.WORD,
    yscrollcommand=scrollbar.set,
    font=("Courier New", 9),
    height=20
)
help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=help_text.yview)

# テキスト内容
help_content = """【Quest VRChat Tool v2.0 - 使用ガイド】

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 ツール概要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Meta Quest内のVRChatスクリーンショットをADB経由でPCへ転送し、
自動的にファイルをリネームするツールです。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 必要な環境
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Meta Quest（VRChat対応機種）
✓ Android Debug Bridge（ADB）をインストール
✓ Questの「開発者モード」を有効化
✓ 「USB デバッグモード」を有効化
✓ Quest と PC を USB ケーブルで接続

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 各タブの役割
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【実行】タブ
  1️⃣ Import VRC Pictures
     → VRChatスクリーンショットを保存先フォルダへ転送
     → 自動的にファイルをリネーム

  2️⃣ Check Connection
     → Quest の接続状況を確認
     → ADB デバイスリストを表示

  3️⃣ Test Mode
     → ADB バージョン確認
     → 接続デバイス確認
     → config.json 設定内容確認

  Exit
     → アプリケーションを終了

【設定】タブ
  📁 保存先フォルダ
     → ファイルを保存するフォルダを指定
     → 「参照...」で GUI から選択可能

  📝 ファイルリネーム
     → ファイル末尾に追加する文字列を設定
     → デフォルト: "_Quest"
     → 例) photo.png → photo_Quest.png

  ⚙️ ADB設定
     → チェック時、実行時に ADB サーバーを自動起動

  💾 設定を保存
     → すべての設定を config.json に保存

  🔄 リセット
     → デフォルト設定に戻す（確認あり）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❓ よくある質問
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: "ADBコマンドが見つかりません" エラーが出ます
A: Android SDK Platform-Tools をインストールし、PATH に
   追加してください。Windows なら環境変数を確認してください。

Q: "Questが接続されていません" と表示されます
A: • USB ケーブルで接続しているか確認
   • 「このコンピュータを信頼しますか?」を許可した
   • 「Check Connection」で接続状況を確認

Q: ファイルがリネームされません
A: 「設定」タブで「リネーム末尾」を確認してください。
   空白になっていないか確認してください。

Q: 保存先フォルダが見つかりません
A: • パスが存在しているか確認
   • SMB サーバーの場合、マウントされているか確認
   • パスに日本語が含まれる場合、別のパスを試す

Q: Quest側のパス設定はどこですか？
A: VRChatのカメラで撮影した写真に関してはVRChatで全端末固定のため、設定は不要です。

Q: ADBサーバーを自動起動するにはどうすればいいですか？
A: 「設定」タブの「ADB設定」で「実行時にADBサーバーを自動起動」にチェックを入れてください。
   これにより、インポートや接続確認の際にADBサーバーが自動的に起動します。

Q: ADBとはなんですか？
A: ADB（Android Debug Bridge）は、AndroidデバイスとPCを接続してコマンドを送るためのツールです。
   QuestとPC間の通信に使用されます。これによってQuest内のファイルをPCに転送したり、接続状況を確認したりできます。
   本ツール（QVTool）を使用してQuestの破損は絶対にいたしません。

Q: 設定がわからんぞジョジョ！
A: ほぼそのままの状態で使用できます。設定等を弄る必要はありませんが、必要に応じて保存先フォルダやリネーム設定を変更してください。
    Test Modeで接続確認を行うこともできます。何か問題がある場合はTest Modeで診断してください。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 ファイル構成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
main.py         ← GUIアプリケーション（ADB処理含む）
config.json     ← ユーザー設定を保存

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 初回実行時は「Test Mode」で接続確認をしてください
• 定期的に設定をバックアップしてください
• ログはGUIのステータスバーに表示されます
• 何か問題がある場合は「Test Mode」で診断できます

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
バージョン: v2.0 (Pure Python)
最終更新: 2026年4月3日
"""

help_text.insert("1.0", help_content)
help_text.config(state=tk.DISABLED)  # 読み取り専用
status_frame = ttk.Frame(root)
status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

status_label = ttk.Label(
    status_frame,
    textvariable=status_var,
    font=("Arial", 10),
    foreground="blue"
)
status_label.pack(side=tk.LEFT)

# メインループ
root.mainloop()
