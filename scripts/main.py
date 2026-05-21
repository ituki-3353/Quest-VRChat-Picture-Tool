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
import re
import urllib.parse
import sqlite3
import hashlib
from datetime import datetime

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
HELP_FILE = get_resource_path("help_manual.md")
STRINGS_FILE = get_resource_path("strings_jp.json")
LOGO_FILE = get_resource_path("logo.png")
ICON_FILE = get_resource_path("icon.ico")

def load_strings():
    """外部ファイルからUI文字列を読み込む"""
    if os.path.exists(STRINGS_FILE):
        try:
            with open(STRINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"文字列ファイルの読み込みエラー: {e}")
    return {}

# 文字列リソースのロード
STR = load_strings()

# アイコンキャッシュ (ガベージコレクション防止用)
icons_cache = {}

def get_icon(name, size=16):
    """icons 配下から指定サイズのアイコンを取得し PhotoImage を返す"""
    key = f"{name}-{size}"
    if key not in icons_cache:
        icon_path = get_resource_path(os.path.join("icons", f"{name}-{size}.png"))
        if os.path.exists(icon_path):
            try:
                icons_cache[key] = tk.PhotoImage(file=icon_path)
            except Exception:
                return None
    return icons_cache.get(key)

# デフォルト設定
DEFAULT_CONFIG = {
    "target_path": r"S:\VRChat-Picture",
    "rename_suffix": "_Quest",
    "photo_naming_template": "{date}_{time}_{world}_{instance}",
    "db_naming_template": "vrchat_logs_{date}_{time}",
    "photo_db_path": "",
    "local_log_path": "",
    "import_logs_with_photos": True,
    "temp_path": os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'QVPTool'),
    "adb_auto_start": True,
    "log_target_path": r"S:\VRChat-Logs",
    "log_source_path": "/storage/emulated/0/Documents/Logs",
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


def sanitize_filename(value, max_length=120):
    """ファイル名に使える文字列に整形する"""
    value = str(value or "").strip()
    if not value:
        return "Unknown"

    replacements = {
        '/': '／',
        '\\': '＼',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '”',
        '<': '＜',
        '>': '＞',
        '|': '｜',
    }
    value = ''.join(replacements.get(ch, ch) for ch in value)
    value = re.sub(r'\s+', '_', value)
    value = re.sub(r'[_\-]{2,}', '_', value)
    value = value.strip('_')
    if len(value) > max_length:
        return value[:max_length-3] + '...'
    return value or "Unknown"


def build_vrchat_world_url(world_name, instance):
    """ワールド詳細ページまたは検索ページURLを生成する"""
    world_id = None
    if instance:
        parts = instance.split(':', 1)
        maybe_id = parts[0].strip()
        if re.match(r'wrld_[0-9A-Za-z]+', maybe_id):
            world_id = maybe_id
        elif re.match(r'wrld_[0-9A-Za-z]+', instance):
            world_id = instance
    if not world_id and world_name:
        match = re.search(r'(wrld_[0-9A-Za-z]+)', world_name)
        if match:
            world_id = match.group(1)

    if world_id:
        encoded_instance = urllib.parse.quote(instance or '', safe='')
        return f"https://vrchat.com/home/launch?worldId={world_id}&instance={encoded_instance}"
    if world_name:
        encoded_world = urllib.parse.quote(world_name, safe='')
        return f"https://vrchat.com/home/search?query={encoded_world}"
    return ""


def extract_screenshot_timestamp(filename):
    """スクリーンショットファイル名から日付と時間を抽出する"""
    match = re.search(
        r'(?P<year>\d{4})[-_]?'
        r'(?P<month>\d{2})[-_]?'
        r'(?P<day>\d{2})[-_ ]?'
        r'(?P<hour>\d{2})[-_:]'
        r'(?P<minute>\d{2})[-_:]'
        r'(?P<second>\d{2})',
        filename,
    )
    if match:
        return f"{match.group('year')}{match.group('month')}{match.group('day')}", f"{match.group('hour')}{match.group('minute')}{match.group('second')}"
    return None, None


def parse_vrchat_log_photo_locations(log_root):
    """ログファイルから写真ファイル名と撮影場所を対応付ける"""
    locations = {}
    if not log_root or not os.path.exists(log_root):
        return locations

    world_patterns = [
        re.compile(r'Entering Room: (?P<world>.+?) \((?P<instance>[^)]+)\)', re.I),
        re.compile(r'Joined world "(?P<world>[^"]+)" \((?P<instance>[^)]+)\)', re.I),
        re.compile(r'Loaded world "(?P<world>[^"]+)" \((?P<instance>[^)]+)\)', re.I),
        re.compile(r'Joining instance (?P<world>[^()]+?) \((?P<instance>[^)]+)\)', re.I),
        re.compile(r'Joined world (?P<world>[^()]+?) \((?P<instance>[^)]+)\)', re.I),
    ]
    screenshot_pattern = re.compile(
        r'Captured screenshot at: .*?[\\/](?P<filename>[^\\/:*?"<>|\r\n]+\.png)',
        re.I,
    )
    generic_png_pattern = re.compile(r'(?P<filename>[^\\/:*?"<>|\r\n]+\.png)', re.I)

    current_world = None
    current_instance = None

    for root_dir, dirs, files in os.walk(log_root):
        for file in files:
            if not file.lower().endswith('.txt'):
                continue
            log_path = os.path.join(root_dir, file)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        for pattern in world_patterns:
                            match = pattern.search(line)
                            if match:
                                current_world = match.group('world').strip()
                                current_instance = match.group('instance').strip()
                                break

                        if 'captured screenshot at' in line.lower():
                            match = screenshot_pattern.search(line)
                            if match:
                                filename = match.group('filename').strip()
                            else:
                                continue
                        elif '.png' in line.lower():
                            match = generic_png_pattern.search(line)
                            if match:
                                filename = match.group('filename').strip()
                            else:
                                continue
                        else:
                            continue

                        base_name = os.path.splitext(filename)[0]
                        if not base_name or base_name in locations:
                            continue

                        locations[base_name] = {
                            'world_name': sanitize_filename(current_world or 'Unknown'),
                            'instance_id': sanitize_filename(current_instance or 'Unknown'),
                        }
            except Exception:
                continue

    return locations


def find_photo_location(filename, photo_locations, rename_suffix):
    """元のスクリーンショット名がマッピングにあるか確認する"""
    if filename in photo_locations:
        return photo_locations[filename]
    if rename_suffix and filename.endswith(rename_suffix):
        original = filename[:-len(rename_suffix)]
        if original in photo_locations:
            return photo_locations[original]
    return None


def build_safe_photo_filename(date_part, time_part, world_name, instance_id, ext):
    """撮影情報から安全なファイル名を作成する"""
    world_part = sanitize_filename(world_name or 'Unknown', max_length=120)
    instance_part = sanitize_filename(instance_id or 'Unknown', max_length=60)
    base = f"{date_part}_{time_part}_{world_part}_{instance_part}"
    allowed = 250 - len(ext)
    if len(base) > allowed:
        prefix = f"{date_part}_{time_part}_"
        suffix = f"_{instance_part}"
        remaining = allowed - len(prefix) - len(suffix) - 3
        if remaining < 10:
            remaining = max(10, allowed - len(prefix) - len(suffix) - 3)
        world_part = (world_part[:remaining] + '...') if len(world_part) > remaining else world_part
        base = f"{prefix}{world_part}{suffix}"
    return f"{base}{ext}"


def write_photo_index_file(destination_path, index_rows):
    """加工した写真の目次ファイルを書き出す"""
    if not os.path.exists(destination_path):
        os.makedirs(destination_path, exist_ok=True)

    index_path = os.path.join(destination_path, 'photo_index.txt')
    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('file_name,world_name,instance_url\n')
            for row in index_rows:
                f.write(f"{row['file_name']},{row['world_name']},{row['instance_url']}\n")
        return index_path
    except Exception:
        return None


def ensure_unique_filepath(filepath):
    base, ext = os.path.splitext(filepath)
    counter = 1
    while os.path.exists(filepath):
        filepath = f"{base}_{counter}{ext}"
        counter += 1
    return filepath


def format_template_string(template, data):
    """テンプレートから安全なファイル名文字列を構築する"""
    try:
        formatted = template.format(
            date=data.get('date', 'unknown'),
            time=data.get('time', 'unknown'),
            world=data.get('world', 'Unknown'),
            instance=data.get('instance', 'Unknown'),
            original=data.get('original', 'Unknown'),
            ext=data.get('ext', ''),
        )
    except Exception:
        formatted = template

    return sanitize_filename(formatted, max_length=255)


def build_db_path(base_dir, template, data):
    filename_base = format_template_string(template, data)
    if not filename_base.lower().endswith('.db'):
        filename_base += '.db'
    db_path = os.path.join(base_dir, filename_base)
    return ensure_unique_filepath(db_path)


def create_or_update_log_db(db_path, log_directory):
    """ログファイルを SQLite DB にインポート・追記する"""
    if not os.path.exists(log_directory):
        return False

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS imported_logs ("
                "id INTEGER PRIMARY KEY, "
                "log_name TEXT, "
                "log_path TEXT UNIQUE, "
                "imported_at TEXT, "
                "content TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS photo_locations ("
                "id INTEGER PRIMARY KEY, "
                "screenshot_name TEXT UNIQUE, "
                "world_name TEXT, "
                "instance_id TEXT, "
                "log_path TEXT, "
                "imported_at TEXT"
                ")"
            )

            for root_dir, dirs, files in os.walk(log_directory):
                for file in files:
                    if not file.lower().endswith('.txt'):
                        continue
                    log_path = os.path.join(root_dir, file)
                    try:
                        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        imported_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        conn.execute(
                            "INSERT OR IGNORE INTO imported_logs (log_name, log_path, imported_at, content) VALUES (?, ?, ?, ?)",
                            (file, os.path.relpath(log_path, log_directory), imported_at, content),
                        )
                    except Exception:
                        continue

            # ログファイルからスクリーンショットの位置情報を抽出してDB化
            try:
                locations = parse_vrchat_log_photo_locations(log_directory)
                for screenshot_name, data in locations.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO photo_locations (screenshot_name, world_name, instance_id, log_path, imported_at) VALUES (?, ?, ?, ?, ?)",
                        (screenshot_name, data.get('world_name', 'Unknown'), data.get('instance_id', 'Unknown'), '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    )
            except Exception:
                pass
        return True
    finally:
        conn.close()


def find_latest_log_db(folder_path):
    if not folder_path or not os.path.isdir(folder_path):
        return None
    db_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith('.db')
    ]
    if not db_files:
        return None
    return max(db_files, key=os.path.getmtime)


def load_photo_locations_from_db(db_path):
    locations = {}
    if not db_path or not os.path.exists(db_path):
        return locations
    try:
        conn = sqlite3.connect(db_path)
        with conn:
            rows = conn.execute(
                "SELECT screenshot_name, world_name, instance_id FROM photo_locations"
            ).fetchall()
            for screenshot_name, world_name, instance_id in rows:
                key = os.path.splitext(screenshot_name)[0]
                locations[key] = {
                    'world_name': world_name or 'Unknown',
                    'instance_id': instance_id or 'Unknown',
                }
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return locations


def load_logo():
    """タイトルロゴ画像を読み込む"""
    if os.path.exists(LOGO_FILE):
        try:
            logo = tk.PhotoImage(file=LOGO_FILE)
            max_width = 550
            max_height = 100
            width = logo.width()
            height = logo.height()
            if width > max_width or height > max_height:
                factor = max(1, min(width // max_width, height // max_height))
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

def browse_log_folder():
    """ログ保存先フォルダ選択ダイアログを開く"""
    current_path = log_target_path_var.get()
    folder = filedialog.askdirectory(
        title="ログ保存先フォルダを選択",
        initialdir=current_path if os.path.exists(current_path) else os.path.expanduser("~")
    )
    if folder:
        log_target_path_var.set(folder)
        save_settings()


def browse_local_log_folder():
    """Windows上のログフォルダを選択する"""
    current_path = local_log_path_var.get()
    folder = filedialog.askdirectory(
        title="Windowsログフォルダを選択",
        initialdir=current_path if os.path.exists(current_path) else os.path.expanduser("~")
    )
    if folder:
        local_log_path_var.set(folder)
        save_settings()


def browse_photo_db_file():
    """写真インポート用DBファイルを選択する"""
    current_path = photo_db_path_var.get()
    initial_dir = os.path.dirname(current_path) if current_path and os.path.exists(os.path.dirname(current_path)) else os.path.expanduser("~")
    filename = filedialog.askopenfilename(
        title="DBファイルを選択",
        initialdir=initial_dir,
        filetypes=[("SQLite DB", "*.db"), ("すべてのファイル", "*.*")],
    )
    if filename:
        photo_db_path_var.set(filename)
        photo_db_content_var.set("DB内容: 選択済み - 確認ボタンを押してください")
        save_settings()


def inspect_photo_db_content():
    """選択されたDBの内容を確認する"""
    db_path = photo_db_path_var.get().strip()
    if not db_path or not os.path.exists(db_path):
        messagebox.showwarning("DB内容確認", "有効なDBファイルを選択してください。")
        return

    try:
        conn = sqlite3.connect(db_path)
        with conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            photo_count = 0
            log_count = 0
            sample_rows = []

            if "photo_locations" in tables:
                photo_count = conn.execute("SELECT COUNT(*) FROM photo_locations").fetchone()[0]
                sample_rows = [row[0] for row in conn.execute("SELECT screenshot_name FROM photo_locations LIMIT 5").fetchall()]
            if "imported_logs" in tables:
                log_count = conn.execute("SELECT COUNT(*) FROM imported_logs").fetchone()[0]

        sample_text = "" if not sample_rows else "\n例: " + ", ".join(sample_rows)
        summary = f"DB内容: {os.path.basename(db_path)} | photo_locations: {photo_count}件 | imported_logs: {log_count}件{sample_text}"
        photo_db_content_var.set(summary)
        messagebox.showinfo("DB内容確認", summary)
    except Exception as e:
        messagebox.showerror("DB内容確認", f"DBを読み込めませんでした:\n{e}")


def save_settings():
    """設定タブの入力値をconfig.jsonに保存"""
    config = {
        "target_path": target_path_var.get(),
        "rename_suffix": rename_suffix_var.get(),
        "photo_naming_template": photo_naming_template_var.get(),
        "db_naming_template": db_naming_template_var.get(),
        "photo_db_path": photo_db_path_var.get(),
        "local_log_path": local_log_path_var.get(),
        "import_logs_with_photos": import_logs_with_photos_var.get(),
        "temp_path": temp_path_var.get(),
        "adb_auto_start": adb_auto_start_var.get(),
        "log_target_path": log_target_path_var.get(),
        "log_source_path": log_source_path_var.get(),
        "comment": "保存先フォルダパス、リネーム設定、一時フォルダーパスなど。GUIで変更可能。"
    }
    if save_config(config):
        status_var.set("✓ 設定を保存しました")

def reset_settings():
    """設定をリセット"""
    if messagebox.askyesno("確認", "設定をデフォルト値にリセットしますか？"):
        target_path_var.set(DEFAULT_CONFIG["target_path"])
        rename_suffix_var.set(DEFAULT_CONFIG["rename_suffix"])
        photo_naming_template_var.set(DEFAULT_CONFIG["photo_naming_template"])
        db_naming_template_var.set(DEFAULT_CONFIG["db_naming_template"])
        import_logs_with_photos_var.set(DEFAULT_CONFIG["import_logs_with_photos"])
        temp_path_var.set(DEFAULT_CONFIG["temp_path"])
        adb_auto_start_var.set(DEFAULT_CONFIG["adb_auto_start"])
        photo_db_path_var.set(DEFAULT_CONFIG["photo_db_path"])
        local_log_path_var.set(DEFAULT_CONFIG["local_log_path"])
        log_target_path_var.set(DEFAULT_CONFIG["log_target_path"])
        log_source_path_var.set(DEFAULT_CONFIG["log_source_path"])
        save_settings()
        status_var.set("✓ 設定をリセットしました")

def load_default_settings():
    """デフォルト設定を読み込んでconfig.jsonとdefault_conf.jsonに保存"""
    if messagebox.askyesno("確認", "デフォルト値を読み込みますか？\nconfig.json と default_conf.json に保存されます。"):
        # デフォルト設定をGUIに反映
        target_path_var.set(DEFAULT_CONFIG["target_path"])
        rename_suffix_var.set(DEFAULT_CONFIG["rename_suffix"])
        photo_naming_template_var.set(DEFAULT_CONFIG["photo_naming_template"])
        db_naming_template_var.set(DEFAULT_CONFIG["db_naming_template"])
        import_logs_with_photos_var.set(DEFAULT_CONFIG["import_logs_with_photos"])
        temp_path_var.set(DEFAULT_CONFIG["temp_path"])
        adb_auto_start_var.set(DEFAULT_CONFIG["adb_auto_start"])
        photo_db_path_var.set(DEFAULT_CONFIG["photo_db_path"])
        log_target_path_var.set(DEFAULT_CONFIG["log_target_path"])
        log_source_path_var.set(DEFAULT_CONFIG["log_source_path"])
        
        # config.json に保存
        config = {
            "target_path": target_path_var.get(),
            "rename_suffix": rename_suffix_var.get(),
            "photo_naming_template": photo_naming_template_var.get(),
            "db_naming_template": db_naming_template_var.get(),
            "photo_db_path": photo_db_path_var.get(),
            "local_log_path": local_log_path_var.get(),
            "import_logs_with_photos": import_logs_with_photos_var.get(),
            "temp_path": temp_path_var.get(),
            "adb_auto_start": adb_auto_start_var.get(),
            "log_target_path": log_target_path_var.get(),
            "log_source_path": log_source_path_var.get(),
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
            "photo_naming_template": DEFAULT_CONFIG["photo_naming_template"],
            "db_naming_template": DEFAULT_CONFIG["db_naming_template"],
            "photo_db_path": DEFAULT_CONFIG["photo_db_path"],
            "local_log_path": DEFAULT_CONFIG["local_log_path"],
            "import_logs_with_photos": DEFAULT_CONFIG["import_logs_with_photos"],
            "temp_path": DEFAULT_CONFIG["temp_path"],
            "adb_auto_start": DEFAULT_CONFIG["adb_auto_start"],
            "log_target_path": DEFAULT_CONFIG["log_target_path"],
            "log_source_path": DEFAULT_CONFIG["log_source_path"]
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
        import_queue.put(("log", "  VRChat 写真インポートツール"))
        import_queue.put(("log", "="*50))
        import_queue.put(("status", "[1/6] ADB環境を確認中..."))

        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=10, encoding='utf-8')
            import_queue.put(("log", "✓ ADB コマンドを確認"))
        except (subprocess.CalledProcessError, FileNotFoundError):
            import_queue.put(("log", "✗ ADB コマンドが見つかりません"))
            import_queue.put(("error", "ADBコマンドが見つかりません。\nADBをインストールしてPATHに追加してください。"))
            return

        # ステップ2: ADBサーバー起動
        import_queue.put(("log", "[2/6] ADBサーバーを起動中..."))
        import_queue.put(("status", "[2/6] ADBサーバーを起動中..."))

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
        import_queue.put(("log", "[3/6] Quest デバイスを確認中..."))
        import_queue.put(("status", "[3/6] Quest デバイスを確認中..."))

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

            # DB形式のログがあれば優先利用する
            photo_locations = {}
            selected_db = photo_db_path_var.get().strip()
            if selected_db and os.path.exists(selected_db):
                import_queue.put(("log", f"✓ 選択DBをロード中: {selected_db}"))
                photo_locations = load_photo_locations_from_db(selected_db)
                if photo_locations:
                    import_queue.put(("log", f"✓ DBから位置情報を取得しました: {len(photo_locations)}件"))
                else:
                    import_queue.put(("warning", "選択DBから位置情報が読み取れませんでした。ログ解析にフォールバックします。"))

            if not photo_locations and local_log_path_var.get().strip():
                local_log_path = local_log_path_var.get().strip()
                if os.path.exists(local_log_path):
                    import_queue.put(("log", f"✓ Windowsログを参照中: {local_log_path}"))
                    photo_locations = parse_vrchat_log_photo_locations(local_log_path)
                    if photo_locations:
                        import_queue.put(("log", f"✓ Windowsログから写真の撮影場所を取得しました: {len(photo_locations)}件"))
                    else:
                        import_queue.put(("warning", "Windowsログから位置情報が取得できませんでした。既存ログを解析します。"))

            if not photo_locations and import_logs_with_photos_var.get():
                db_path = find_latest_log_db(log_target_path_var.get())
                if db_path:
                    import_queue.put(("log", f"✓ 最新DBを検出しました: {db_path}"))
                    photo_locations = load_photo_locations_from_db(db_path)
                    if photo_locations:
                        import_queue.put(("log", f"✓ 最新DBから位置情報を取得しました: {len(photo_locations)}件"))
                    else:
                        import_queue.put(("warning", "最新DBから位置情報の取得に失敗しました。ログファイルを解析します。"))

            if not photo_locations and import_logs_with_photos_var.get():
                photo_locations = parse_vrchat_log_photo_locations(log_target_path_var.get())
                if photo_locations:
                    import_queue.put(("log", f"✓ ログから写真の撮影場所を取得しました: {len(photo_locations)}件"))
                else:
                    import_queue.put(("log", "⚠ ログから写真の撮影場所を取得できませんでした。既存のリネーム方式を使用します。"))
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
            photo_index_rows = []

            if os.path.exists(vrhcat_temp_dir):
                import_queue.put(("log", f"📂 一時フォルダー: {vrhcat_temp_dir}"))

                # ステップ1: 一時フォルダー内でリネーム
                import_queue.put(("log", "\n[処理] ステップ 1/2: ファイルをリネーム中..."))
                for root_dir, dirs, files in os.walk(vrhcat_temp_dir):
                    for file in files:
                        filepath = os.path.join(root_dir, file)
                        filename, ext = os.path.splitext(file)
                        new_filename = None
                        final_filename = file
                        world_name = 'Unknown'
                        instance_id = 'Unknown'
                        instance_url = ''

                        if ext.lower() == ".png":
                            photo_location = find_photo_location(filename, photo_locations, rename_suffix)
                            if photo_location:
                                world_name = photo_location['world_name']
                                instance_id = photo_location['instance_id']
                                date_part, time_part = extract_screenshot_timestamp(filename)
                                if date_part and time_part:
                                    new_filename = build_safe_photo_filename(date_part, time_part, world_name, instance_id, ext)
                                else:
                                    safe_world = sanitize_filename(world_name, max_length=100)
                                    safe_instance = sanitize_filename(instance_id, max_length=60)
                                    new_filename = f"{safe_world}_{safe_instance}{ext}"
                            elif not filename.endswith(rename_suffix):
                                new_filename = filename + rename_suffix + ext

                            instance_url = build_vrchat_world_url(world_name if world_name != 'Unknown' else None, instance_id if instance_id != 'Unknown' else None)

                        if new_filename:
                            new_filepath = os.path.join(root_dir, new_filename)
                            if os.path.exists(new_filepath):
                                new_filepath = ensure_unique_filepath(new_filepath)
                            try:
                                os.rename(filepath, new_filepath)
                                final_filename = os.path.basename(new_filepath)
                                renamed_count += 1
                                if renamed_count % 10 == 0 or renamed_count <= 3:
                                    import_queue.put(("log", f"  ✓ リネーム: {file} → {final_filename}"))
                            except Exception as e:
                                import_queue.put(("log", f"  ✗ リネーム失敗: {file} - {e}"))

                        if ext.lower() == ".png":
                            rel_dir = os.path.relpath(root_dir, vrhcat_temp_dir)
                            if rel_dir == '.' or rel_dir == os.curdir:
                                rel_path = final_filename
                            else:
                                rel_path = os.path.normpath(os.path.join(rel_dir, final_filename))
                            photo_index_rows.append({
                                'file_name': rel_path.replace(os.sep, '/'),
                                'world_name': world_name,
                                'instance_url': instance_url,
                            })

                import_queue.put(("log", f"✓ リネーム完了: {renamed_count}個のファイル"))

                index_path = write_photo_index_file(vrhcat_final_dir, photo_index_rows)
                if index_path:
                    import_queue.put(("log", f"✓ 思い出のインデックスを生成しました: {index_path}"))
                else:
                    import_queue.put(("log", "⚠ 思い出のインデックスの生成に失敗しました。"))

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

                if photo_index_rows:
                    world_names = [row['world_name'] for row in photo_index_rows if row['world_name'] != 'Unknown']
                    world_summary = ', '.join(sorted(set(world_names))) if world_names else 'Unknown'
                    preview_path = None
                    first_row_path = photo_index_rows[0]['file_name'].replace('/', os.sep)
                    candidate_preview = os.path.join(vrhcat_final_dir, first_row_path)
                    if os.path.exists(candidate_preview):
                        preview_path = candidate_preview
                    import_queue.put((
                        "preview",
                        f"インポート完了！\n\n保存した写真: {moved_count}枚\n代表ワールド: {world_summary}\n保存先: {vrhcat_final_dir}",
                        preview_path,
                    ))
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


def _run_log_import_worker():
    """VRChat ログファイルをインポート・マージ（別スレッド）"""
    target_path = log_target_path_var.get()
    source_path = log_source_path_var.get()
    temp_path = os.path.join(temp_path_var.get(), "Logs_Temp")

    if not target_path.strip():
        import_queue.put(("error", "ログ保存先フォルダを指定してください。"))
        return

    try:
        import_queue.put(("log", "\n" + "="*50))
        import_queue.put(("log", "  VRChat ログインポートツール"))
        import_queue.put(("log", "="*50))
        import_queue.put(("status", "ADB環境を確認中..."))

        # ADB 基本チェック (共通処理の簡略化版)
        try:
            subprocess.run(["adb", "start-server"], capture_output=True, check=True, timeout=20, encoding='utf-8')
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, encoding='utf-8')
            if "device" not in result.stdout or "unauthorized" in result.stdout:
                import_queue.put(("error", "Questが接続されていません。"))
                return
        except Exception as e:
            import_queue.put(("error", f"ADBエラー: {e}"))
            return

        # フォルダ準備
        os.makedirs(target_path, exist_ok=True)
        if os.path.exists(temp_path):
            import shutil
            shutil.rmtree(temp_path)
        os.makedirs(temp_path, exist_ok=True)

        # ステップ1: ファイル転送
        import_queue.put(("log", f"[1/2] ログ転送中...\n ソース: {source_path}"))
        import_queue.put(("status", "ログ転送中..."))
        
        process = subprocess.Popen(
            ["adb", "pull", source_path, temp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
        )
        process.wait(timeout=120)

        if process.returncode != 0:
            # フォルダが空、もしくはパスが存在しない場合のハンドリング
            import_queue.put(("log", "⚠ 転送に失敗したか、ファイルが見つかりません。"))
            import_queue.put(("info", "Quest側にログファイルが見つかりませんでした。"))
            return

        # ステップ2: マージ処理
        import_queue.put(("log", "[2/2] ログマージ処理中..."))
        import_queue.put(("status", "マージ処理中..."))
        
        # pullした結果、temp_path の中に 'Logs' というサブフォルダができる場合があるため調整
        pulled_logs_dir = temp_path
        if os.path.exists(os.path.join(temp_path, "Logs")):
            pulled_logs_dir = os.path.join(temp_path, "Logs")

        merged_count = 0
        new_count = 0
        
        for file in os.listdir(pulled_logs_dir):
            if not file.endswith(".txt"): continue
            
            src_file = os.path.join(pulled_logs_dir, file)
            dst_file = os.path.join(target_path, file)

            if os.path.exists(dst_file):
                # マージ処理（追記）
                try:
                    with open(src_file, "rb") as f_src:
                        new_data = f_src.read()
                    
                    with open(dst_file, "ab") as f_dst:
                        # 既存ファイルとの境界を分かりやすくするためのヘッダー（任意）
                        f_dst.write(b"\n--- QUEST_IMPORT_MERGE_DATA ---\n")
                        f_dst.write(new_data)
                    merged_count += 1
                except Exception as e:
                    import_queue.put(("log", f" ✗ マージ失敗: {file} ({e})"))
            else:
                # 新規コピー
                try:
                    import shutil
                    shutil.copy2(src_file, dst_file)
                    new_count += 1
                except Exception as e:
                    import_queue.put(("log", f" ✗ コピー失敗: {file} ({e})"))

        # クリーンアップ
        try:
            import shutil
            shutil.rmtree(temp_path)
        except: pass

        import_queue.put(("log", f"✓ 完了: 新規 {new_count}件, マージ {merged_count}件"))
        import_queue.put(("success", f"ログのインポートが完了しました！\n\n・新規追加: {new_count}件\n・マージ(追記): {merged_count}件"))
        import_queue.put(("done", "completed"))

    except Exception as e:
        import_queue.put(("log", f"✗ エラー: {e}"))
        import_queue.put(("error", f"ログ処理中にエラーが発生しました:\n{e}"))

def run_log_import():
    """ログインポート実行（スレッド起動）"""
    global import_thread
    if import_thread and import_thread.is_alive():
        messagebox.showwarning("警告", "既に処理中です。完了するまでお待ちください。")
        return
    status_var.set("⏱ ログ取得中...")
    import_thread = threading.Thread(target=_run_log_import_worker, daemon=True)
    import_thread.start()


def _run_db_import_worker():
    """VRChat ログを SQLite DB 形式でインポート（別スレッド）"""
    target_path = log_target_path_var.get()
    source_path = log_source_path_var.get()
    temp_path = os.path.join(temp_path_var.get(), "Logs_DB_Temp")

    if not target_path.strip():
        import_queue.put(("error", "ログ保存先フォルダを指定してください。"))
        return

    try:
        import_queue.put(("log", "\n" + "="*50))
        import_queue.put(("log", "  VRChat ログDBインポートツール"))
        import_queue.put(("log", "="*50))
        import_queue.put(("status", "ADB環境を確認中..."))

        try:
            subprocess.run(["adb", "start-server"], capture_output=True, check=True, timeout=20, encoding='utf-8')
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, encoding='utf-8')
            if "device" not in result.stdout or "unauthorized" in result.stdout:
                import_queue.put(("error", "Questが接続されていません。"))
                return
        except Exception as e:
            import_queue.put(("error", f"ADBエラー: {e}"))
            return

        os.makedirs(target_path, exist_ok=True)
        if os.path.exists(temp_path):
            import shutil
            shutil.rmtree(temp_path)
        os.makedirs(temp_path, exist_ok=True)

        import_queue.put(("log", f"[1/2] ログ転送中...\n ソース: {source_path}"))
        import_queue.put(("status", "ログ転送中..."))

        process = subprocess.Popen(
            ["adb", "pull", source_path, temp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
        )
        process.wait(timeout=120)

        if process.returncode != 0:
            import_queue.put(("log", "⚠ 転送に失敗したか、ファイルが見つかりません。"))
            import_queue.put(("info", "Quest側にログファイルが見つかりませんでした。"))
            return

        import_queue.put(("log", "[2/2] DB形式へ変換中..."))
        import_queue.put(("status", "DB形式に変換中..."))

        pulled_logs_dir = temp_path
        if os.path.exists(os.path.join(temp_path, "Logs")):
            pulled_logs_dir = os.path.join(temp_path, "Logs")

        now = datetime.now()
        db_path = build_db_path(target_path, db_naming_template_var.get(), {
            'date': now.strftime('%Y%m%d'),
            'time': now.strftime('%H%M%S'),
        })

        if create_or_update_log_db(db_path, pulled_logs_dir):
            import_queue.put(("log", f"✓ DBを作成しました: {db_path}"))
            import_queue.put(("success", f"DBインポートが完了しました。\n保存先: {db_path}"))
        else:
            import_queue.put(("error", "DBの作成に失敗しました。"))
            return

        try:
            import shutil
            shutil.rmtree(temp_path)
        except Exception:
            pass

        import_queue.put(("done", "completed"))

    except Exception as e:
        import_queue.put(("log", f"✗ エラー: {e}"))
        import_queue.put(("error", f"ログDB処理中にエラーが発生しました:\n{e}"))


def run_db_import():
    """DB形式ログインポート実行（スレッド起動）"""
    global import_thread
    if import_thread and import_thread.is_alive():
        messagebox.showwarning("警告", "既に処理中です。完了するまでお待ちください。")
        return
    status_var.set("⏱ DBインポート中...")
    import_thread = threading.Thread(target=_run_db_import_worker, daemon=True)
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

        # ログウィンドウを表示して初期メッセージを出力
        log_win.show()
        log_win.log("\n" + "="*50)
        log_win.log("   システム診断テスト実行")
        log_win.log("="*50)

        # ADBバージョン確認
        log_win.log("\n[テスト] ADB バージョン確認")
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=10, encoding='utf-8')
            if result.returncode == 0:
                log_win.log(result.stdout.strip())
            else:
                log_win.log(f"ADBバージョン取得失敗: {result.stderr}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            log_win.log("ADBコマンドが見つかりません。ADBをインストールしてください。")

        # デバイスリスト
        log_win.log("\n[テスト] デバイス リスト")
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10, encoding='utf-8')
            log_win.log(result.stdout.strip() or "デバイスが見つかりません")
        except subprocess.TimeoutExpired:
            log_win.log("ADBデバイス確認がタイムアウトしました")

        # 設定ファイル内容
        log_win.log("\n[テスト] 設定ファイル内容 (config.json)")
        log_win.log("----------------------------------------")
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_content = f.read()
                log_win.log(config_content)
            except Exception as e:
                log_win.log(f"設定ファイル読み込みエラー: {e}")
        else:
            log_win.log("config.json ファイルが見つかりません。")
        log_win.log("----------------------------------------")

        # ターゲットパスの確認
        log_win.log("\n[テスト] ターゲットパスの確認")
        log_win.log("")
        log_win.log("[GUI設定] config.json から読み込んだ値:")
        try:
            config = load_config()
            log_win.log(f"target_path: {config.get('target_path', '未設定')}")
            log_win.log(f"rename_suffix: {config.get('rename_suffix', '未設定')}")
            log_win.log(f"temp_path: {config.get('temp_path', '未設定')}")
            log_win.log(f"adb_auto_start: {config.get('adb_auto_start', '未設定')}")
        except Exception as e:
            log_win.log(f"（設定読み込みエラー: {e}）")
        log_win.log("")
        log_win.log("[実行時引数] コマンドラインから渡された値:")
        log_win.log("ターゲットパス（第2引数）: 指定されていません")

        log_win.log("\n" + "="*50)
        log_win.log("診断テストが終了しました。")
        log_win.log("="*50)

        # ポップアップ通知
        messagebox.showinfo("テスト完了", "診断テストが完了しました。詳細はログウィンドウを確認してください。")
        status_var.set("✓ テスト完了")

    except Exception as e:
        messagebox.showerror("エラー", f"テスト実行中にエラーが発生しました:\n{e}")
        status_var.set("✗ テストエラー")

class LogWindow:
    """ImgBurn風の外部ログウィンドウクラス"""
    def __init__(self, master):
        self.top = tk.Toplevel(master)
        self.top.title("QVPTool - ログ")
        self.top.geometry("600x350")
        # ウィンドウを閉じても破棄せず非表示にするだけにする
        self.top.protocol("WM_DELETE_WINDOW", self.hide)
        
        # コマンド入力エリア (先にBottomでパックして領域を確保)
        self.cmd_frame = ttk.Frame(self.top, padding=(5, 2))
        self.cmd_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.cmd_entry = ttk.Entry(self.cmd_frame)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cmd_entry.bind("<Return>", self.handle_command)

        # コンテンツフレーム（ログ表示用 - 残りの中央領域をすべて占有）
        self.content_frame = ttk.Frame(self.top)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # テキストエリアとスクロールバー
        self.text = tk.Text(self.content_frame, state='disabled', wrap='word', font=("Courier New", 9))
        self.scroll = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scroll.set)
        
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # スタートメッセージの表示
        v, b = load_version()
        self.log("================================================================")
        self.log(f" QVPTool - Quest VRChat 写真管理ツール v{v}")
        self.log(f" ビルド番号: {b}")
        self.log("================================================================")
        self.log("--- ログウィンドウを初期化しました ---")
        self.log("※ '/help' と入力すると利用可能なコマンドを表示します。")

    def log(self, message):
        """ログを追記して自動スクロール"""
        self.text.config(state='normal')
        self.text.insert(tk.END, message + "\n")
        self.text.see(tk.END)
        self.text.config(state='disabled')

    def handle_command(self, event):
        """コマンド入力の処理"""
        raw_text = self.cmd_entry.get().strip()
        if not raw_text:
            return
            
        self.cmd_entry.delete(0, tk.END)
        self.log(f"\n# {raw_text}")
        
        parts = raw_text.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd == "/help":
            self.log("利用可能なコマンド:")
            self.log("  /help            - このヘルプを表示")
            self.log("  /clear           - ログをクリア")
            self.log("  /config          - 現在の設定値を一覧表示")
            self.log("  /set <key> <val> - 設定を変更 (pics_path, logs_path, suffix)")
            self.log("  /adb <args...>   - ADBコマンドを直接実行")
            
        elif cmd == "/clear":
            self.text.config(state='normal')
            self.text.delete(1.0, tk.END)
            self.text.config(state='disabled')
            self.log("--- ログをクリアしました ---")
            
        elif cmd == "/config":
            self.log("現在の設定:")
            self.log(f"  Pictures Path : {target_path_var.get()}")
            self.log(f"  Logs Path     : {log_target_path_var.get()}")
            self.log(f"  Suffix        : {rename_suffix_var.get()}")
            self.log(f"  Temp Path     : {temp_path_var.get()}")
            self.log(f"  ADB AutoStart : {adb_auto_start_var.get()}")
            
        elif cmd == "/set":
            if len(args) < 2:
                self.log("エラー: /set <key> <value> の形式で入力してください。")
                return
            key = args[0].lower()
            val = " ".join(args[1:])
            
            if key == "pics_path":
                target_path_var.set(val)
                self.log(f"✓ Pictures Path を変更: {val}")
            elif key == "logs_path":
                log_target_path_var.set(val)
                self.log(f"✓ Logs Path を変更: {val}")
            elif key == "suffix":
                rename_suffix_var.set(val)
                self.log(f"✓ Suffix を変更: {val}")
            else:
                self.log(f"エラー: 不明なキー '{key}'")
                return
            save_settings() # 変更を反映・保存
            
        elif cmd == "/adb":
            if not args:
                self.log("エラー: ADBコマンドを指定してください。例: /adb devices")
                return
            threading.Thread(target=self._run_adb_cmd, args=(args,), daemon=True).start()
            
        else:
            self.log(f"エラー: 未知のコマンド '{cmd}' です。")

    def _run_adb_cmd(self, args):
        """ADBコマンドを実行して結果をログに送る"""
        try:
            import_queue.put(("log", f"[ADB] 実行中: adb {' '.join(args)}"))
            res = subprocess.run(["adb"] + args, capture_output=True, text=True, encoding='utf-8', timeout=15)
            if res.stdout: import_queue.put(("log", res.stdout.strip()))
            if res.stderr: import_queue.put(("log", f"Error: {res.stderr.strip()}"))
        except Exception as e:
            import_queue.put(("log", f"ADB実行エラー: {e}"))
        
    def show(self):
        """メインウィンドウの右側に配置して表示"""
        # メインウィンドウの最新の配置情報を確定させる
        self.top.master.update_idletasks()
        
        # メインウィンドウの現在の座標(x, y)と横幅(w)を取得
        main_x = self.top.master.winfo_x()
        main_y = self.top.master.winfo_y()
        main_w = self.top.master.winfo_width()
        
        # メインウィンドウの右側に10ピクセルの隙間を空けて配置 (サイズは600x350を維持)
        self.top.geometry(f"600x350+{main_x + main_w + 10}+{main_y}")
        
        self.top.deiconify()

    def hide(self):
        self.top.withdraw()


def show_import_preview(summary_text, preview_path=None):
    """インポート完了後にサマリーと代表写真を表示する"""
    preview_win = tk.Toplevel(root)
    preview_win.title("完了レポート")
    preview_win.geometry("640x520")
    preview_win.resizable(True, True)

    frame = ttk.Frame(preview_win, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="インポート完了レポート", font=("Arial", 14, "bold")).pack(anchor=tk.W)
    ttk.Label(frame, text=summary_text, justify=tk.LEFT, wraplength=600).pack(anchor=tk.W, pady=(8, 10))

    if preview_path and os.path.exists(preview_path):
        try:
            preview_image = tk.PhotoImage(file=preview_path)
            width = preview_image.width()
            height = preview_image.height()
            if width > 600 or height > 340:
                factor = max(1, max(width // 600, height // 340))
                preview_image = preview_image.subsample(factor, factor)
            preview_label = ttk.Label(frame, image=preview_image)
            preview_label.image = preview_image
            preview_label.pack(pady=(0, 8))
        except Exception as e:
            ttk.Label(frame, text=f"プレビュー画像の表示に失敗しました: {e}", foreground="red").pack(anchor=tk.W, pady=(0, 8))
    else:
        ttk.Label(frame, text="プレビュー画像は利用できませんでした。", foreground="gray").pack(anchor=tk.W, pady=(0, 8))

    if preview_path:
        ttk.Label(frame, text=f"代表画像: {os.path.basename(preview_path)}", font=("Arial", 9, "italic"), foreground="gray").pack(anchor=tk.W)
    ttk.Button(frame, text="閉じる", command=preview_win.destroy).pack(pady=(10, 0))


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
root.title(f"{STR.get('app_title', 'Quest VRChat Photo Tool')} v{version}")
root.geometry("600x550")
root.resizable(True, True)

# 設定の読み込み
config = load_config()
target_path_var = tk.StringVar(value=config.get("target_path", DEFAULT_CONFIG["target_path"]))
rename_suffix_var = tk.StringVar(value=config.get("rename_suffix", DEFAULT_CONFIG["rename_suffix"]))
photo_naming_template_var = tk.StringVar(value=config.get("photo_naming_template", DEFAULT_CONFIG["photo_naming_template"]))
db_naming_template_var = tk.StringVar(value=config.get("db_naming_template", DEFAULT_CONFIG["db_naming_template"]))
photo_db_path_var = tk.StringVar(value=config.get("photo_db_path", DEFAULT_CONFIG["photo_db_path"]))
local_log_path_var = tk.StringVar(value=config.get("local_log_path", DEFAULT_CONFIG["local_log_path"]))
import_logs_with_photos_var = tk.BooleanVar(value=config.get("import_logs_with_photos", DEFAULT_CONFIG["import_logs_with_photos"]))
temp_path_var = tk.StringVar(value=config.get("temp_path", DEFAULT_CONFIG["temp_path"]))
adb_auto_start_var = tk.BooleanVar(value=config.get("adb_auto_start", DEFAULT_CONFIG["adb_auto_start"]))
log_target_path_var = tk.StringVar(value=config.get("log_target_path", DEFAULT_CONFIG["log_target_path"]))
log_source_path_var = tk.StringVar(value=config.get("log_source_path", DEFAULT_CONFIG["log_source_path"]))
photo_db_content_var = tk.StringVar(value="DB内容: 未選択")
status_var = tk.StringVar(value=STR.get("status_waiting", "待機中..."))

def load_help_text():
    """外部ファイルからヘルプテキストを読み込む"""
    if os.path.exists(HELP_FILE):
        try:
            with open(HELP_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            # テキスト内の {version} プレースホルダを実際のバージョンに置換
            return content.replace("{version}", version)
        except Exception as e:
            return f"ヘルプファイルの読み込みに失敗しました: {e}"
    return "ヘルプファイル(help_manual.md)が見つかりません。"

status_var = tk.StringVar(value=STR.get("status_waiting", "待機中..."))

# ログウィンドウの初期化
log_win = LogWindow(root)
log_win.show()

# --- Layout (Oracle VBox Style with Header Logo) ---

# 0. Header (Wide Logo Area)
header_frame = ttk.Frame(root, padding=(0, 0))
header_frame.pack(side=tk.TOP, fill=tk.X)

logo_image = load_logo()
if logo_image:
    logo_label = ttk.Label(header_frame, image=logo_image)
    logo_label.image = logo_image
    logo_label.pack(side=tk.LEFT, padx=10, pady=5)

# 1. Toolbar (Top)
toolbar = ttk.Frame(root, padding=5)
toolbar.pack(side=tk.TOP, fill=tk.X)

def create_toolbar_btn(parent, text, icon_name, command, side=tk.LEFT):
    icon = get_icon(icon_name, 16)
    btn = ttk.Button(parent, text=text, command=command, image=icon, compound=tk.LEFT)
    btn.pack(side=side, padx=2)
    return btn

create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("import_pics", " Import Pics"), "pics", run_import)
create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("import_logs", " Import Logs"), "logs", run_log_import)
create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("settings", " Settings"), "settings", lambda: switch_view("settings_item"))

ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("check_adb", " Check ADB"), "adb", run_config)
create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("view_log", " View Log"), "viewlog", log_win.show)
create_toolbar_btn(toolbar, STR.get("toolbar", {}).get("exit", " Exit"), "exit", root.destroy, side=tk.RIGHT)

# 2. Main Content Split (PanedWindow)
paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, borderwidth=0, sashwidth=4)
paned.pack(fill=tk.BOTH, expand=True)

# Sidebar (Left)
sidebar_frame = ttk.Frame(paned, relief="flat", padding=5)
paned.add(sidebar_frame, width=220)

sidebar_label = ttk.Label(sidebar_frame, text=STR.get("sidebar", {}).get("title", "Items"), font=("Arial", 10, "bold"))
sidebar_label.pack(anchor=tk.W, pady=(10, 5))

sidebar_list = ttk.Treeview(sidebar_frame, show="tree", selectmode="browse", height=4) # heightは表示行数、Treeviewはデフォルトでスクロールバーなし
sidebar_list.pack(fill=tk.BOTH, expand=True)

# Treeviewの項目データとアイコン
sidebar_items_data = [
    ("welcome_item", STR.get("sidebar", {}).get("welcome", " Welcome"), "pics"),
    ("pics_item", STR.get("sidebar", {}).get("pics", " Pictures"), "pics"),
    ("logs_item", STR.get("sidebar", {}).get("logs", " Logs"), "logs"),
    ("db_item", STR.get("sidebar", {}).get("db", " DB Management"), "logs"),
    ("settings_item", STR.get("sidebar", {}).get("settings", " Settings"), "settings"),
    ("help_item", STR.get("sidebar", {}).get("help", " Help"), "help"),
]

for iid, text, icon_name in sidebar_items_data:
    icon = get_icon(icon_name, 16)
    item_args = {"iid": iid, "text": text}
    if icon:
        item_args["image"] = icon
    sidebar_list.insert('', 'end', **item_args)

ttk.Label(sidebar_frame, text=f"Build: {build_number}", font=("Arial", 7), foreground="gray").pack(side=tk.BOTTOM)

# Content Area (Right)
content_area = ttk.Frame(paned, padding=10)
paned.add(content_area)

view_frames = {}

def switch_view(event_or_iid=None):
    selected_iid = None
    if isinstance(event_or_iid, str): # Called directly with an iid
        selected_iid = event_or_iid
    elif event_or_iid: # It's an event object from TreeviewSelect
        selection = sidebar_list.selection()
        if selection:
            selected_iid = selection[0] # Get the iid of the selected item

    if not selected_iid:
        return

    for f in view_frames.values():
        f.pack_forget()
    
    # Map iid to view_name (e.g., 'pics_item' -> 'pics')
    view_name = selected_iid.replace('_item', '')

    if view_name not in view_frames:
        return

    view_frames[view_name].pack(fill=tk.BOTH, expand=True)

sidebar_list.bind("<<TreeviewSelect>>", switch_view)

# -- View Welcome (初期表示) --
v_welcome = ttk.Frame(content_area)
view_frames["welcome"] = v_welcome
welcome_header = ttk.Label(v_welcome, text=STR.get("view_welcome", {}).get("header", "Welcome"), font=("Arial", 16, "bold"))
welcome_header.pack(anchor=tk.W, pady=(10, 20), fill=tk.X)
welcome_desc = ttk.Label(v_welcome, text=STR.get("view_welcome", {}).get("description", ""), justify=tk.LEFT)
welcome_desc.pack(anchor=tk.W, pady=10, fill=tk.X)

def _on_welcome_resize(event):
    # 親コンテナの幅に合わせてラベルの折り返し幅を調整 (パディング考慮)
    new_wrap = event.width - 20
    if new_wrap > 0:
        welcome_header.configure(wraplength=new_wrap)
        welcome_desc.configure(wraplength=new_wrap)
v_welcome.bind("<Configure>", _on_welcome_resize)

welcome_btn_frame = ttk.Frame(v_welcome)
welcome_btn_frame.pack(anchor=tk.W, pady=20)

ttk.Button(welcome_btn_frame, text=STR.get("view_welcome", {}).get("import_pics", "Import Pics"), 
           command=run_import, width=30).pack(pady=5, fill=tk.X)
ttk.Button(welcome_btn_frame, text=STR.get("view_welcome", {}).get("import_logs", "Import Logs"), 
           command=run_log_import, width=30).pack(pady=5, fill=tk.X)


# -- View 0: Pictures --
v_pics = ttk.Frame(content_area)
view_frames["pics"] = v_pics
pics_icon_24 = get_icon("pics", 24)
ttk.Label(v_pics, text=STR.get("view_pics", {}).get("header", " Pictures Manager"), font=("Arial", 14, "bold"), image=pics_icon_24, compound=tk.LEFT).pack(anchor=tk.W, pady=10)
p_path_frame = ttk.LabelFrame(v_pics, text=STR.get("view_pics", {}).get("path_label", " Save Directory"), padding=10)
p_path_frame.pack(fill=tk.X, pady=5)
ttk.Entry(p_path_frame, textvariable=target_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(p_path_frame, text=STR.get("view_pics", {}).get("browse", "Browse"), command=browse_folder).pack(side=tk.LEFT)
p_rename_frame = ttk.LabelFrame(v_pics, text=STR.get("view_pics", {}).get("rename_label", " Rename Suffix"), padding=10)
p_rename_frame.pack(fill=tk.X, pady=5)
ttk.Entry(p_rename_frame, textvariable=rename_suffix_var).pack(anchor=tk.W, padx=5)
p_rename_example = ttk.Label(p_rename_frame, text=STR.get("view_pics", {}).get("rename_example", ""), foreground="gray")
p_rename_example.pack(anchor=tk.W, padx=5, fill=tk.X)

p_db_frame = ttk.LabelFrame(v_pics, text="DBファイル選択", padding=10)
p_db_frame.pack(fill=tk.X, pady=5)
ttk.Entry(p_db_frame, textvariable=photo_db_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(p_db_frame, text="参照", command=browse_photo_db_file).pack(side=tk.LEFT)
ttk.Button(p_db_frame, text="DB内容確認", command=inspect_photo_db_content).pack(side=tk.LEFT, padx=(5, 0))
ttk.Label(p_db_frame, textvariable=photo_db_content_var, foreground="gray", wraplength=560).pack(anchor=tk.W, pady=(6, 0), fill=tk.X)

def _on_pics_resize(event):
    new_wrap = event.width - 40
    if new_wrap > 0:
        p_rename_example.configure(wraplength=new_wrap)
v_pics.bind("<Configure>", _on_pics_resize)

ttk.Button(v_pics, text=STR.get("view_pics", {}).get("import_btn", " Import"), command=run_import, width=30, image=pics_icon_24, compound=tk.LEFT).pack(pady=20)

# -- View 1: Logs --
v_logs = ttk.Frame(content_area)
view_frames["logs"] = v_logs
logs_icon_24 = get_icon("logs", 24)
ttk.Label(v_logs, text=STR.get("view_logs", {}).get("header", " Logs Manager"), font=("Arial", 14, "bold"), image=logs_icon_24, compound=tk.LEFT).pack(anchor=tk.W, pady=10)
l_target_frame = ttk.LabelFrame(v_logs, text=STR.get("view_logs", {}).get("path_label", " PC Save Directory"), padding=10)
l_target_frame.pack(fill=tk.X, pady=5)
ttk.Entry(l_target_frame, textvariable=log_target_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(l_target_frame, text=STR.get("view_pics", {}).get("browse", "Browse"), command=browse_log_folder).pack(side=tk.LEFT)
l_source_frame = ttk.LabelFrame(v_logs, text=STR.get("view_logs", {}).get("source_label", " Quest Source"), padding=10)
l_source_frame.pack(fill=tk.X, pady=5)
ttk.Entry(l_source_frame, textvariable=log_source_path_var, state="readonly").pack(fill=tk.X, padx=5)
log_button_frame = ttk.Frame(v_logs)
log_button_frame.pack(pady=20, fill=tk.X)
ttk.Button(log_button_frame, text=STR.get("view_logs", {}).get("import_btn", " Import & Merge"), command=run_log_import, width=20, image=logs_icon_24, compound=tk.LEFT).pack(side=tk.LEFT, padx=(0, 10))
ttk.Button(log_button_frame, text=STR.get("view_logs", {}).get("db_import_btn", " Import to DB"), command=run_db_import, width=20, image=logs_icon_24, compound=tk.LEFT).pack(side=tk.LEFT)

# -- View 2: DB Management --
v_db = ttk.Frame(content_area)
view_frames["db"] = v_db
db_icon_24 = get_icon("logs", 24)
ttk.Label(v_db, text="DB管理", font=("Arial", 14, "bold"), image=db_icon_24, compound=tk.LEFT).pack(anchor=tk.W, pady=10)

b_db_file_frame = ttk.LabelFrame(v_db, text="DBファイル", padding=10)
b_db_file_frame.pack(fill=tk.X, pady=5)
ttk.Entry(b_db_file_frame, textvariable=photo_db_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(b_db_file_frame, text="参照", command=browse_photo_db_file).pack(side=tk.LEFT)
ttk.Button(b_db_file_frame, text="DB内容確認", command=inspect_photo_db_content).pack(side=tk.LEFT, padx=(5, 0))
ttk.Label(b_db_file_frame, textvariable=photo_db_content_var, foreground="gray", wraplength=560).pack(anchor=tk.W, pady=(6, 0), fill=tk.X)

b_local_log_frame = ttk.LabelFrame(v_db, text="Windows ログフォルダ", padding=10)
b_local_log_frame.pack(fill=tk.X, pady=5)
ttk.Entry(b_local_log_frame, textvariable=local_log_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(b_local_log_frame, text="参照", command=browse_local_log_folder).pack(side=tk.LEFT)

b_db_action_frame = ttk.Frame(v_db, padding=10)
b_db_action_frame.pack(fill=tk.X, pady=5)
ttk.Button(b_db_action_frame, text="WindowsログをDBに変換", command=run_db_import, width=30).pack(side=tk.LEFT, padx=(0, 5))

b_db_summary = ttk.Label(v_db, textvariable=photo_db_content_var, foreground="gray", wraplength=560)
b_db_summary.pack(anchor=tk.W, pady=(10, 0), fill=tk.X)

# -- View 3: Settings --
v_settings = ttk.Frame(content_area)
view_frames["settings"] = v_settings
settings_icon_24 = get_icon("settings", 24)
ttk.Label(v_settings, text=STR.get("view_settings", {}).get("header", " Global Settings"), font=("Arial", 14, "bold"), image=settings_icon_24, compound=tk.LEFT).pack(anchor=tk.W, pady=10)
s_temp_frame = ttk.LabelFrame(v_settings, text=STR.get("view_settings", {}).get("temp_label", " Temp Directory"), padding=10)
s_temp_frame.pack(fill=tk.X, pady=5)
ttk.Entry(s_temp_frame, textvariable=temp_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

s_naming_frame = ttk.LabelFrame(v_settings, text=STR.get("view_settings", {}).get("naming_label", " Naming Templates"), padding=10)
s_naming_frame.pack(fill=tk.X, pady=5)
ttk.Label(s_naming_frame, text="写真命名テンプレート:").pack(anchor=tk.W)
ttk.Entry(s_naming_frame, textvariable=photo_naming_template_var).pack(fill=tk.X, padx=5, pady=(0, 5))
ttk.Label(s_naming_frame, text="DB命名テンプレート:").pack(anchor=tk.W)
ttk.Entry(s_naming_frame, textvariable=db_naming_template_var).pack(fill=tk.X, padx=5)
ttk.Label(s_naming_frame, text="使用可能なプレースホルダ: {date}, {time}, {world}, {instance}, {original}, {ext}", foreground="gray").pack(anchor=tk.W, pady=(4, 0))

s_log_frame = ttk.LabelFrame(v_settings, text=STR.get("view_settings", {}).get("log_import_label", " Log Import"), padding=10)
s_log_frame.pack(fill=tk.X, pady=5)
ttk.Checkbutton(s_log_frame, text=STR.get("view_settings", {}).get("import_logs_with_photos", "Import logs together with photos"), variable=import_logs_with_photos_var).pack(anchor=tk.W)

s_adb_frame = ttk.LabelFrame(v_settings, text=STR.get("view_settings", {}).get("adb_label", " ADB Settings"), padding=10)
s_adb_frame.pack(fill=tk.X, pady=5)
ttk.Checkbutton(s_adb_frame, text=STR.get("view_settings", {}).get("adb_auto_start", ""), variable=adb_auto_start_var).pack(anchor=tk.W)
ttk.Button(s_adb_frame, text=STR.get("view_settings", {}).get("adb_test", ""), command=run_config).pack(anchor=tk.W, pady=5)
ttk.Button(s_adb_frame, text=STR.get("view_settings", {}).get("diag", ""), command=run_test).pack(anchor=tk.W)

s_btn_frame = ttk.Frame(v_settings, padding=10)
s_btn_frame.pack(fill=tk.X, pady=20)
ttk.Button(s_btn_frame, text=STR.get("view_settings", {}).get("save", " Save"), command=save_settings, image=get_icon("save", 16), compound=tk.LEFT).pack(side=tk.LEFT, padx=5)
ttk.Button(s_btn_frame, text=STR.get("view_settings", {}).get("reset", " Reset"), command=reset_settings, image=get_icon("reset", 16), compound=tk.LEFT).pack(side=tk.LEFT, padx=5)
ttk.Button(s_btn_frame, text=STR.get("view_settings", {}).get("load_default", " Load Default"), command=load_default_settings, image=get_icon("load", 16), compound=tk.LEFT).pack(side=tk.LEFT, padx=5)


# -- View 3: Help --
v_help = ttk.Frame(content_area)
view_frames["help"] = v_help
tk.Text(v_help, wrap=tk.WORD, font=("Courier New", 9), height=15).pack(fill=tk.BOTH, expand=True)
v_help.winfo_children()[0].insert(1.0, load_help_text())
v_help.winfo_children()[0].config(state=tk.DISABLED)

# Init view
sidebar_list.selection_set('welcome_item') # ホームを初期選択
switch_view('welcome_item') # 初期画面を表示

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
                log_win.log(msg_data[0])
                
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
                
            elif msg_type == "preview":
                preview_text, preview_path = msg_data
                show_import_preview(preview_text, preview_path)
                
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
