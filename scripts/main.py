import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import subprocess
import os
import json
import locale
import threading
import queue
import sys

# 文字コード設定
os.environ['PYTHONIOENCODING'] = 'utf-8'
locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')

def get_app_dir():
    """実行ファイルのあるディレクトリを返す（PyInstaller 実行時には exe のディレクトリ）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    """PyInstaller 実行時には _MEIPASS を使い、それ以外ではスクリプトフォルダを使う。"""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


APP_DIR = get_app_dir()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
DEFAULT_CONF_FILE = os.path.join(APP_DIR, "default_conf.json")
VERSION_CONF_FILE = get_resource_path("version_conf.json")
LOGO_FILE = get_resource_path("logo.png")
ICON_FILE = get_resource_path("icon.ico")

# デフォルト設定
DEFAULT_CONFIG = {
    "target_path": r"S:\VRChat-Picture",
    "rename_suffix": "_Quest",
    "temp_path": os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'QVPTool'),
    "adb_auto_start": True,
    "comment": "保存先フォルダパス、リネーム設定、一時フォルダーパスなど。GUIで変更可能。"
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

def load_version():
    """バージョン設定ファイルから読み込む"""
    if os.path.exists(VERSION_CONF_FILE):
        try:
            with open(VERSION_CONF_FILE, "r", encoding="utf-8") as f:
                version_data = json.load(f)
                return version_data.get("version", "1.0.0"), version_data.get("build_number", "unknown")
        except Exception as e:
            print(f"バージョン設定ファイルの読み込みエラー: {e}")
            return "1.0.0", "unknown"
    return "1.0.0", "unknown"


def load_logo():
    """タイトルロゴ画像を読み込む"""
    if os.path.exists(LOGO_FILE):
        try:
            logo = tk.PhotoImage(file=LOGO_FILE)
            max_width = 240
            max_height = 80
            width = logo.width()
            height = logo.height()
            if width > max_width or height > max_height:
                factor = max(1, min(width // max_width if width > max_width else 1,
                                    height // max_height if height > max_height else 1))
                return logo.subsample(factor, factor)
            return logo
        except Exception as e:
            print(f"ロゴ画像の読み込みに失敗しました: {e}")
    return None

def browse_folder():
    """フォルダ選択ダイアログを開く"""
    current_path = target_path_var.get()
    folder = filedialog.askdirectory(
        title="保存先フォルダを選択",
        initialdir=current_path if os.path.exists(current_path) else os.path.expanduser("~")
    )
    if folder:
        target_path_var.set(folder)
        save_settings()

def save_settings():
    """設定タブの入力値をconfig.jsonに保存"""
    config = {
        "target_path": target_path_var.get(),
        "rename_suffix": rename_suffix_var.get(),
        "temp_path": temp_path_var.get(),
        "adb_auto_start": adb_auto_start_var.get(),
        "comment": "保存先フォルダパス、リネーム設定、一時フォルダーパスなど。GUIで変更可能。"
    }
    if save_config(config):
        status_var.set("✓ 設定を保存しました")

def reset_settings():
    """設定をリセット"""
    if messagebox.askyesno("確認", "設定をデフォルト値にリセットしますか？"):
        target_path_var.set(DEFAULT_CONFIG["target_path"])
        rename_suffix_var.set(DEFAULT_CONFIG["rename_suffix"])
        temp_path_var.set(DEFAULT_CONFIG["temp_path"])
        adb_auto_start_var.set(DEFAULT_CONFIG["adb_auto_start"])
        save_settings()
        status_var.set("✓ 設定をリセットしました")

def load_default_settings():
    """デフォルト設定を読み込んでconfig.jsonとdefault_conf.jsonに保存"""
    if messagebox.askyesno("確認", "デフォルト値を読み込みますか？\nconfig.json と default_conf.json に保存されます。"):
        # デフォルト設定をGUIに反映
        target_path_var.set(DEFAULT_CONFIG["target_path"])
        rename_suffix_var.set(DEFAULT_CONFIG["rename_suffix"])
        temp_path_var.set(DEFAULT_CONFIG["temp_path"])
        adb_auto_start_var.set(DEFAULT_CONFIG["adb_auto_start"])
        
        # config.json に保存
        config = {
            "target_path": target_path_var.get(),
            "rename_suffix": rename_suffix_var.get(),
            "temp_path": temp_path_var.get(),
            "adb_auto_start": adb_auto_start_var.get(),
            "comment": "保存先フォルダパス、リネーム設定、一時フォルダーパスなど。GUIで変更可能。"
        }
        
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("エラー", f"config.json の保存に失敗しました: {e}")
            status_var.set("✗ config.json 保存失敗")
            return
        
        # default_conf.json に保存
        default_config = {
            "target_path": DEFAULT_CONFIG["target_path"],
            "rename_suffix": DEFAULT_CONFIG["rename_suffix"],
            "temp_path": DEFAULT_CONFIG["temp_path"],
            "adb_auto_start": DEFAULT_CONFIG["adb_auto_start"]
        }
        
        try:
            with open(DEFAULT_CONF_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("エラー", f"default_conf.json の保存に失敗しました: {e}")
            status_var.set("✗ default_conf.json 保存失敗")
            return
        
        status_var.set("✓ デフォルト設定を読み込みました")
        messagebox.showinfo("成功", "デフォルト設定を読み込みました。\nconfig.json と default_conf.json に保存されました。")


# グローバル queue と thread 管理
import_queue = queue.Queue()
import_thread = None

def _run_import_worker():
    """VRC写真をインポート（別スレッドで実行）"""
    
    target_path = target_path_var.get()
    rename_suffix = rename_suffix_var.get()

    if not target_path.strip():
        import_queue.put(("error", "保存先フォルダを指定してください。"))
        return

    try:
        import_queue.put(("log", "\n" + "="*50))
        import_queue.put(("log", "  VRChat Picture Import Tool"))
        import_queue.put(("log", "="*50))
        import_queue.put(("status", "[1/6] ADB環境確認中..."))

        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=10, encoding='utf-8')
            import_queue.put(("log", "✓ ADB コマンドを確認"))
        except (subprocess.CalledProcessError, FileNotFoundError):
            import_queue.put(("log", "✗ ADB コマンドが見つかりません"))
            import_queue.put(("error", "ADBコマンドが見つかりません。\nADBをインストールしてPATHに追加してください。"))
            return

        # ステップ2: ADBサーバー起動
        import_queue.put(("log", "[2/6] ADBサーバー起動中..."))
        import_queue.put(("status", "[2/6] ADBサーバー起動中..."))

        try:
            result = subprocess.run(["adb", "start-server"], capture_output=True, text=True, timeout=30, encoding='utf-8')
            if result.returncode == 0:
                import_queue.put(("log", "✓ ADB サーバー を起動"))
            else:
                import_queue.put(("log", f"⚠ ADBサーバー起動に警告: {result.stderr}"))
                import_queue.put(("warning", f"ADBサーバー起動に失敗しました:\n{result.stderr}"))
        except subprocess.TimeoutExpired:
            import_queue.put(("log", "✗ ADBサーバー起動がタイムアウト"))
            import_queue.put(("warning", "ADBサーバー起動がタイムアウトしました。"))

        # ステップ3: デバイス確認
        import_queue.put(("log", "[3/6] Quest デバイス確認中..."))
        import_queue.put(("status", "[3/6] Quest デバイス確認中..."))

        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10, encoding='utf-8')
        if "device" not in result.stdout or "unauthorized" in result.stdout:
            import_queue.put(("log", "✗ Quest が接続されていません"))
            import_queue.put(("error", "Questが正しく接続されていません。\n• USBケーブルを確認\n• USBデバッグモードを確認\n• 信頼設定を確認"))
            return
        import_queue.put(("log", "✓ Quest デバイス を確認"))
        import_queue.put(("log", result.stdout.strip()))

        # ステップ4: ターゲットディレクトリと一時フォルダを作成
        import_queue.put(("log", "[4/6] フォルダ準備中..."))
        import_queue.put(("status", "[4/6] フォルダ準備中..."))

        temp_path = temp_path_var.get()
        
        if not os.path.exists(target_path):
            try:
                os.makedirs(target_path)
                import_queue.put(("log", f"✓ 保存先フォルダ作成: {target_path}"))
            except Exception as e:
                import_queue.put(("log", f"✗ 保存先フォルダ作成失敗: {e}"))
                import_queue.put(("error", f"保存先フォルダの作成に失敗しました:\n{e}"))
                return
        else:
            import_queue.put(("log", f"✓ 保存先フォルダ確認: {target_path}"))
        
        if not os.path.exists(temp_path):
            try:
                os.makedirs(temp_path)
                import_queue.put(("log", f"✓ 一時フォルダ作成: {temp_path}"))
            except Exception as e:
                import_queue.put(("log", f"✗ 一時フォルダ作成失敗: {e}"))
                import_queue.put(("error", f"一時フォルダの作成に失敗しました:\n{e}"))
                return
        else:
            import_queue.put(("log", f"✓ 一時フォルダ確認: {temp_path}"))

        # ステップ5: ファイル転送（Quest → 一時フォルダへ直接ダウンロード）
        import_queue.put(("log", "[5/6] VRChat スクリーンショット転送中..."))
        import_queue.put(("log", "  ソース: /storage/emulated/0/Pictures/VRChat"))
        import_queue.put(("log", f"  一時フォルダ: {temp_path}"))
        import_queue.put(("log", "-" * 50))
        import_queue.put(("status", "[5/6] ファイル転送中 (数分かかる場合があります)..."))

        source_path = "/storage/emulated/0/Pictures/VRChat"
        temp_vrc_path = os.path.join(temp_path, "VRChat")
        
        # Popen でリアルタイム出力をストリーミング
        process = subprocess.Popen(
            ["adb", "pull", source_path, temp_vrc_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        try:
            # 同時に stdout と stderr を読む
            for line in process.stdout:
                line = line.rstrip('\n')
                import_queue.put(("log", line))
            
            # stderr も読む
            for line in process.stderr:
                line = line.rstrip('\n')
                import_queue.put(("log", f"  [ADB] {line}"))
            
            # プロセスの終了を待つ
            process.wait(timeout=300)
            
            if process.returncode != 0:
                import_queue.put(("log", "✗ ファイル転送失敗"))
                import_queue.put(("error", "ファイル転送に失敗しました。"))
                return
            import_queue.put(("log", "-" * 50))
            import_queue.put(("log", "✓ ファイル転送完了"))
            
        except subprocess.TimeoutExpired:
            process.kill()
            import_queue.put(("log", "✗ ファイル転送がタイムアウト"))
            import_queue.put(("error", "ファイル転送がタイムアウトしました。"))
            return

        # ステップ6: ファイルリネーム・移動処理
        import_queue.put(("log", "[6/6] ファイル処理中..."))
        import_queue.put(("log", "-" * 50))
        import_queue.put(("status", "[6/6] ファイル処理中 (リネーム・移動)..."))

        vrhcat_temp_dir = os.path.join(temp_path, "VRChat")
        vrhcat_final_dir = os.path.join(target_path, "VRChat_Processed")

        try:
            import shutil
            renamed_count = 0
            moved_count = 0

            if os.path.exists(vrhcat_temp_dir):
                import_queue.put(("log", f"📂 一時フォルダー: {vrhcat_temp_dir}"))

                # ステップ1: 一時フォルダー内でリネーム
                import_queue.put(("log", "\n[処理] ステップ 1/2: ファイルをリネーム中..."))
                
                for root_dir, dirs, files in os.walk(vrhcat_temp_dir):
                    for file in files:
                        filepath = os.path.join(root_dir, file)
                        filename, ext = os.path.splitext(file)

                        # 既にリネーム済みかチェック
                        if not filename.endswith(rename_suffix):
                            new_filename = filename + rename_suffix + ext
                            new_filepath = os.path.join(root_dir, new_filename)

                            try:
                                os.rename(filepath, new_filepath)
                                renamed_count += 1
                                if renamed_count % 10 == 0 or renamed_count <= 3:
                                    import_queue.put(("log", f"  ✓ リネーム: {file} → {new_filename}"))
                            except Exception as e:
                                import_queue.put(("log", f"  ✗ リネーム失敗: {file} - {e}"))

                import_queue.put(("log", f"✓ リネーム完了: {renamed_count}個のファイル"))

                # ステップ2: 最終フォルダーへ移動
                import_queue.put(("log", "\n[処理] ステップ 2/2: ファイルを最終フォルダーへ移動中..."))
                
                os.makedirs(vrhcat_final_dir, exist_ok=True)
                for root_dir, dirs, files in os.walk(vrhcat_temp_dir):
                    for file in files:
                        filepath = os.path.join(root_dir, file)
                        rel_path = os.path.relpath(filepath, vrhcat_temp_dir)
                        final_filepath = os.path.join(vrhcat_final_dir, rel_path)
                        os.makedirs(os.path.dirname(final_filepath), exist_ok=True)

                        try:
                            shutil.move(filepath, final_filepath)
                            moved_count += 1
                            if moved_count % 10 == 0 or moved_count <= 3:
                                import_queue.put(("log", f"  ✓ 移動: {rel_path}"))
                        except Exception as e:
                            import_queue.put(("log", f"  ✗ 移動失敗: {file} - {e}"))

                # 一時フォルダーをクリーンアップ
                import_queue.put(("log", "\n[処理] 一時フォルダーをクリーンアップ中..."))
                try:
                    shutil.rmtree(vrhcat_temp_dir)
                    import_queue.put(("log", "✓ 一時フォルダーを削除完了"))
                except Exception as e:
                    import_queue.put(("log", f"⚠ 一時フォルダーの削除に失敗しました: {e}"))

                import_queue.put(("log", "-" * 50))
                import_queue.put(("success", f"✓ インポート完了！\n\n処理結果:\n  • リネーム: {renamed_count}個\n  • 移動: {moved_count}個\n\n最終保存先:\n{vrhcat_final_dir}"))
            else:
                import_queue.put(("log", "⚠ 処理するファイルが見つかりませんでした。"))
                import_queue.put(("info", "処理するファイルが見つかりませんでした。"))

        except Exception as e:
            import_queue.put(("log", f"✗ ファイル処理エラー: {e}"))
            import_queue.put(("error", f"ファイル処理に失敗しました:\n{e}"))
            return

        import_queue.put(("log", "=" * 50))
        import_queue.put(("done", "completed"))

    except Exception as e:
        import_queue.put(("log", f"✗ 予期しないエラー: {e}"))
        import_queue.put(("error", f"予期しないエラーが発生しました:\n{e}"))


def run_import():
    """インポート実行（スレッド起動）"""
    global import_thread
    
    if import_thread and import_thread.is_alive():
        messagebox.showwarning("警告", "既に処理中です。完了するまでお待ちください。")
        return
    
    status_var.set("⏱ 実行中...")
    import_thread = threading.Thread(target=_run_import_worker, daemon=True)
    import_thread.start()


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
            test_results.append(f"temp_path: {config.get('temp_path', '未設定')}")
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

# ウィンドウアイコンを設定
if os.path.exists(ICON_FILE):
    try:
        root.iconbitmap(ICON_FILE)
    except Exception as e:
        print(f"ウィンドウアイコンの設定に失敗しました: {e}")

# バージョン情報の読み込み
version, build_number = load_version()
root.title(f"QVPTool / Quest VRChat Picture Tool v{version} (Build {build_number})")
root.geometry("700x750")
root.resizable(False, False)

# 設定の読み込み
config = load_config()
target_path_var = tk.StringVar(value=config.get("target_path", DEFAULT_CONFIG["target_path"]))
rename_suffix_var = tk.StringVar(value=config.get("rename_suffix", DEFAULT_CONFIG["rename_suffix"]))
temp_path_var = tk.StringVar(value=config.get("temp_path", DEFAULT_CONFIG["temp_path"]))
adb_auto_start_var = tk.BooleanVar(value=config.get("adb_auto_start", DEFAULT_CONFIG["adb_auto_start"]))
status_var = tk.StringVar(value="待機中...")

# === タイトル部分 ===
title_frame = ttk.Frame(root)
title_frame.pack(pady=10, padx=10, fill=tk.X)

logo_image = load_logo()
if logo_image is not None:
    logo_label = ttk.Label(title_frame, image=logo_image)
    logo_label.image = logo_image
    logo_label.pack(side=tk.LEFT)
    title_label = ttk.Label(
        title_frame,
        text="",
        font=("Arial", 18, "bold")
    )
    title_label.pack(side=tk.LEFT, padx=(10, 0))
else:
    title_label = ttk.Label(
        title_frame,
        text="Quest VRChat Picture Tool",
        font=("Arial", 18, "bold")
    )
    title_label.pack(side=tk.LEFT)

version_label = ttk.Label(
    title_frame,
    text=f"v{version}",
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
# スクロール可能なフレーム作成
settings_frame = ttk.Frame(notebook)
notebook.add(settings_frame, text="設定")

# Canvas とスクロールバーの作成
settings_canvas = tk.Canvas(settings_frame, highlightthickness=0)
settings_scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=settings_canvas.yview)
settings_scrollable_frame = ttk.Frame(settings_canvas)

settings_scrollable_frame.bind(
    "<Configure>",
    lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
)

settings_canvas.create_window((0, 0), window=settings_scrollable_frame, anchor="nw")
settings_canvas.configure(yscrollcommand=settings_scrollbar.set)

# Canvas とスクロールバーを配置
settings_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
settings_scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)

# マウスホイール対応
def _on_mousewheel_settings(event):
    settings_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

settings_canvas.bind_all("<MouseWheel>", _on_mousewheel_settings)

# settings_tab を settings_scrollable_frame に変更
settings_tab = settings_scrollable_frame

# 保存先フォルダ設定
path_frame = ttk.LabelFrame(settings_tab, text="📁 保存先フォルダ", padding=10)
path_frame.pack(pady=10, fill=tk.X, padx=10)

path_label = ttk.Label(path_frame, text="保存先:", font=("Arial", 10))
path_label.grid(row=0, column=0, sticky=tk.W, pady=5)

path_entry = ttk.Entry(path_frame, textvariable=target_path_var, width=45)
path_entry.grid(row=0, column=1, padx=5, pady=5)

browse_button = ttk.Button(path_frame, text="参照...", command=browse_folder, width=10)
browse_button.grid(row=0, column=2, padx=5, pady=5)

# ファイル名リネーム設定
rename_frame = ttk.LabelFrame(settings_tab, text="📝 ファイルリネーム", padding=10)
rename_frame.pack(pady=10, fill=tk.X, padx=10)

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

# 一時フォルダー設定
temp_frame = ttk.LabelFrame(settings_tab, text="📂 一時フォルダー", padding=10)
temp_frame.pack(pady=10, fill=tk.X, padx=10)

temp_label = ttk.Label(temp_frame, text="一時保存先:", font=("Arial", 10))
temp_label.grid(row=0, column=0, sticky=tk.W, pady=5)

temp_entry = ttk.Entry(temp_frame, textvariable=temp_path_var, width=45)
temp_entry.grid(row=0, column=1, padx=5, pady=5)

def browse_temp_folder():
    """一時フォルダー選択ダイアログを開く"""
    current_path = temp_path_var.get()
    folder = filedialog.askdirectory(
        title="一時フォルダーを選択",
        initialdir=current_path if os.path.exists(current_path) else os.path.expanduser("~")
    )
    if folder:
        temp_path_var.set(folder)
        save_settings()

temp_browse_button = ttk.Button(temp_frame, text="参照...", command=browse_temp_folder, width=10)
temp_browse_button.grid(row=0, column=2, padx=5, pady=5)

temp_info_label = ttk.Label(
    temp_frame,
    text="ファイルの転送後、一時的に保存されてからリネーム・移動されます",
    font=("Arial", 9),
    foreground="gray"
)
temp_info_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

# ADB設定
adb_frame = ttk.LabelFrame(settings_tab, text="⚙️ ADB設定", padding=10)
adb_frame.pack(pady=10, fill=tk.X, padx=10)

adb_check = ttk.Checkbutton(
    adb_frame,
    text="実行時にADBサーバーを自動起動",
    variable=adb_auto_start_var
)
adb_check.pack(anchor=tk.W, pady=5)

# ボタングループ
button_group = ttk.Frame(settings_tab)
button_group.pack(pady=20, fill=tk.X, padx=10)

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

default_button = ttk.Button(
    button_group,
    text="📥 デフォルト読み込み",
    command=load_default_settings,
    width=20
)
default_button.pack(side=tk.LEFT, padx=5)

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
help_content = rf"""【Quest VRChat Tool v{version} - 使用ガイド】

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 ツール概要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Meta Quest内のVRChatスクリーンショットをADB経由でPCへ転送し、
自動的にファイルをリネームするツールです。

【重要】コンソールウィンドウとの同時表示
本ツールは別々のコンソールウィンドウに処理ログを表示します。
GUIと同時にコンソール出力を確認できます。

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
     → VRChatスクリーンショットを転送・リネーム
     → コンソール に進捗を表示

  2️⃣ Check Connection
     → Questの接続状況を確認

  3️⃣ Test Mode
     → ADB、デバイス、設定を確認

  Exit → アプリケーション終了

【設定】タブ
  💾 設定を保存
     → すべての設定を config.json に保存

  🔄 リセット
     → デフォルト設定に戻す（確認あり）

  📥 デフォルト読み込み
     → デフォルト値を読み込む
     → config.json と default_conf.json に保存
"""

help_text.insert(1.0, help_content)
help_text.config(state=tk.DISABLED)

# === ステータスバー ===
status_frame = ttk.Frame(root, relief=tk.SUNKEN, borderwidth=1)
status_frame.pack(side=tk.BOTTOM, fill=tk.X)

status_label = ttk.Label(status_frame, textvariable=status_var, font=("Arial", 9))
status_label.pack(side=tk.LEFT, padx=5, pady=2)


# Queue からのメッセージを処理
def process_queue():
    """Queue からメッセージを読んで処理"""
    try:
        while True:
            msg_type, *msg_data = import_queue.get_nowait()
            
            if msg_type == "log":
                # ログをコンソールに出力
                print(msg_data[0])
                
            elif msg_type == "status":
                # ステータスバーを更新
                status_var.set(f"⏱ {msg_data[0]}")
                
            elif msg_type == "error":
                # エラーダイアログを表示
                messagebox.showerror("エラー", msg_data[0])
                status_var.set(f"✗ エラー")
                
            elif msg_type == "warning":
                # 警告ダイアログを表示
                messagebox.showwarning("警告", msg_data[0])
                
            elif msg_type == "info":
                # 情報ダイアログ
                messagebox.showinfo("情報", msg_data[0])
                
            elif msg_type == "success":
                # 成功メッセージ
                import_queue.put(("log", msg_data[0]))  # ログにも記録
                messagebox.showinfo("成功", msg_data[0])
                status_var.set(f"✓ 完了")
                
            elif msg_type == "done":
                # 処理完了
                status_var.set("✓ 完了")
                
    except queue.Empty:
        pass
    
    # 定期的にチェック
    root.after(100, process_queue)


# Queue 処理開始
root.after(100, process_queue)

# ウィンドウ表示
root.mainloop()
