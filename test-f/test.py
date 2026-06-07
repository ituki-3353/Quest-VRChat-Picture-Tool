import os
import json
import sqlite3
import hashlib
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import paramiko
from scp import SCPClient

observer = None

# --- UI Logging Handler ---
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    """ログメッセージをUIスレッドのキューに転送するハンドラ"""
    def emit(self, record):
        log_queue.put(self.format(record))

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# コンソール出力
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# UI出力用
qh = QueueHandler()
qh.setFormatter(formatter)
logger.addHandler(qh)

logger = logging.getLogger(__name__)

# --- Configuration ---
CONFIG_PATH = "config.json"

def save_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

# --- Database Layer (LODDB) ---
def init_db():
    os.makedirs(os.path.dirname(config["db_path"]), exist_ok=True)
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    # 写真基本情報テーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE,
            original_path TEXT,
            managed_path TEXT,
            file_name TEXT,
            created_at TIMESTAMP,
            world_name TEXT,
            instance_id TEXT,
            user_name TEXT
        )
    ''')
    # 位置情報・LOD用拡張テーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_metadata (
            photo_id INTEGER,
            latitude REAL,
            longitude REAL,
            location_label TEXT,
            FOREIGN KEY(photo_id) REFERENCES photos(id)
        )
    ''')
    conn.commit()
    conn.close()

# --- Image Processing Engine ---
def calculate_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """VRChatのファイル名形式 (VRChat_YYYY-MM-DD_HH-MM-SS.mmm_...) から日時を抽出"""
    match = re.search(r'VRChat_(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})_(?P<H>\d{2})-(?P<M>\d{2})-(?P<S>\d{2})', filename)
    if match:
        return datetime.strptime(
            f"{match.group('y')}{match.group('m')}{match.group('d')}{match.group('H')}{match.group('M')}{match.group('S')}", 
            '%Y%m%d%H%M%S'
        )
    return None

def get_vrc_location_from_logs(timestamp: datetime) -> tuple:
    """ログディレクトリを走査し、指定時刻に滞在していたワールドを特定する"""
    log_dir = config.get("log_dir", "/srv/vrc/logs")
    if not os.path.exists(log_dir):
        return "UnknownWorld", "UnknownInstance"

    # ログ内のイベントパターン
    patterns = [
        re.compile(r'Entering Room: (?P<world>.+?) \((?P<instance>[^)]+)\)', re.I),
        re.compile(r'Joined world "(?P<world>[^"]+)"', re.I),
    ]
    
    closest_world = "UnknownWorld"
    closest_instance = "UnknownInstance"
    
    # タイムスタンプに最も近い過去の入室ログを探す
    # 本来的にはSQLiteに構造化されたログDB（master_log_db）から検索するのが高速です
    try:
        log_files = sorted(
            [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.txt')],
            key=os.path.getmtime,
            reverse=True
        )

        for log_path in log_files:
            # ファイルの更新時刻が写真より古すぎる場合はスキップ
            if os.path.getmtime(log_path) < timestamp.timestamp() - 86400:
                continue
                
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    # ログの行から時刻を取得 (形式: 2026.05.20 15:10:42)
                    line_match = re.match(r'^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not line_match:
                        continue
                    
                    line_dt = datetime.strptime(line_match.group(1), '%Y.%m.%d %H:%M:%S')
                    if line_dt > timestamp:
                        continue # 写真より後のログは見ない

                    for pattern in patterns:
                        m = pattern.search(line)
                        if m:
                            closest_world = m.group('world').strip()
                            if 'instance' in m.groupdict():
                                closest_instance = m.group('instance').strip()
    except Exception as e:
        logger.error(f"Log parsing error: {e}")

    return closest_world, closest_instance

def sanitize_vrc_name(name: str) -> str:
    """ファイル名に使えない文字を除去"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def process_new_image(file_path: str):
    """新規画像を解析、リネーム、DB登録する"""
    try:
        file_name = os.path.basename(file_path)
        file_hash = calculate_hash(file_path)
        
        conn = sqlite3.connect(config["db_path"])
        cursor = conn.cursor()
        
        # 重複チェック
        cursor.execute("SELECT id FROM photos WHERE file_hash = ?", (file_hash,))
        res = cursor.fetchone()
        if res:
            logger.info(f"Duplicate detected (ID: {res[0]}), skipping: {file_name}")
            return

        # 1. 撮影時刻の特定
        dt = extract_timestamp_from_filename(file_name) or datetime.fromtimestamp(os.path.getctime(file_path))
        timestamp_str = dt.strftime("%Y%m%d_%H%M%S")

        # 2. ワールド情報の特定 (ログ解析)
        world_raw, instance = get_vrc_location_from_logs(dt)
        world = sanitize_vrc_name(world_raw)
        user = config.get("default_user", "ituki")
        
        # 3. 新しいファイル名の生成
        new_name = config["naming_template"].format(
            date=timestamp_str,
            world=world,
            user=user,
            seq=file_hash[:8]
        ) + Path(file_path).suffix
        
        # ファイル名の重複回避
        output_base = os.path.join(config["output_dir"], new_name)
        if os.path.exists(output_base):
            new_name = f"{Path(new_name).stem}_{file_hash[:4]}{Path(new_name).suffix}"
            output_base = os.path.join(config["output_dir"], new_name)

        managed_path = os.path.join(config["output_dir"], new_name)
        os.makedirs(config["output_dir"], exist_ok=True)
        
        # ファイル移動（コピー）
        import shutil
        shutil.copy2(file_path, managed_path)

        # DB登録
        cursor.execute('''
            INSERT INTO photos (file_hash, original_path, managed_path, file_name, created_at, world_name, user_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (file_hash, file_path, managed_path, new_name, datetime.now(), world, user))
        
        conn.commit()
        logger.info(f"管理完了: {new_name}")
    except Exception as e:
        logger.error(f"画像処理エラー: {e}")
    finally:
        conn.close()

# --- Watchdog Monitoring ---
class VRCPhotoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            logger.info(f"新規画像を検知: {event.src_path}")
            process_new_image(event.src_path)

def start_observer():
    path = config["input_dir"]
    os.makedirs(path, exist_ok=True)
    event_handler = VRCPhotoHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    logger.info(f"監視を開始しました: {path}")
    return observer

# --- FastAPI Web API ---
app = FastAPI(title="VRChat Photo LODDB Manager API")

class PhotoRecord(BaseModel):
    id: int
    file_name: str
    world_name: str
    managed_path: str

@app.get("/api/photos", response_model=List[PhotoRecord])
async def get_photos(world: Optional[str] = None):
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    if world:
        cursor.execute("SELECT id, file_name, world_name, managed_path FROM photos WHERE world_name LIKE ?", (f"%{world}%",))
    else:
        cursor.execute("SELECT id, file_name, world_name, managed_path FROM photos ORDER BY created_at DESC LIMIT 100")
    
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "file_name": r[1], "world_name": r[2], "managed_path": r[3]} for r in rows]

@app.post("/api/import/scan")
async def trigger_scan():
    """入力フォルダを手動スキャンする（既存ファイル用）"""
    files = [os.path.join(config["input_dir"], f) for f in os.listdir(config["input_dir"]) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    for f in files:
        process_new_image(f)
    return {"status": "success", "processed_files": len(files)}

# --- GUI Components ---
class LogWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("VRC Photo Manager - ログ")
        self.geometry("700x400")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        
        self.text = tk.Text(self, state='disabled', wrap='none', font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.scroll_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        self.scroll_x = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, message):
        self.text.config(state='normal')
        self.text.insert(tk.END, message + "\n")
        self.text.see(tk.END)
        self.text.config(state='disabled')

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat Photo LODDB Manager")
        self.root.geometry("640x300")
        
        self.log_win = LogWindow(self.root)
        
        # UI レイアウト
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="VRChat 写真管理システム", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        self.status_label = ttk.Label(frame, text="ステータス: 準備中...", foreground="blue")
        self.status_label.pack(pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="手動スキャン実行", command=self.trigger_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="開発ファイルを削除", command=self.clean_dev_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="サーバーへデプロイ", command=self.show_deploy_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="サーバーから削除", command=self.show_uninstall_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="ログを表示", command=self.log_win.deiconify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="終了", command=self.on_exit).pack(side=tk.LEFT, padx=5)
        
        srv_ctrl_frame = ttk.LabelFrame(frame, text="サーバー操作", padding=10)
        srv_ctrl_frame.pack(fill=tk.X, pady=10)
        ttk.Button(srv_ctrl_frame, text="サービス開始", command=lambda: self.run_service_control("start")).pack(side=tk.LEFT, padx=5)
        ttk.Button(srv_ctrl_frame, text="サービス停止", command=lambda: self.run_service_control("stop")).pack(side=tk.LEFT, padx=5)

        # 定期的にログキューを確認
        self.update_logs()

    def trigger_scan(self):
        logger.info("手動スキャンをリクエストしました...")
        files = [os.path.join(config["input_dir"], f) for f in os.listdir(config["input_dir"]) 
                 if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for f in files:
            process_new_image(f)
        messagebox.showinfo("スキャン完了", f"{len(files)} 件のファイルを処理しました。")

    def clean_dev_files(self):
        """開発用の一時ファイルやキャッシュを削除する"""
        if not messagebox.askyesno("確認", "開発用の一時ファイル（config_server.json等）やキャッシュ（__pycache__）を削除しますか？"):
            return

        targets = ["config_server.json", "vrc-manager.service"]
        count = 0
        
        # 特定のファイルを削除
        for f in targets:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"削除しました: {f}")
                count += 1
        
        # Python キャッシュディレクトリを再帰的に削除
        for p in Path(".").rglob("__pycache__"):
            shutil.rmtree(p)
            logger.info(f"キャッシュを削除しました: {p}")
            count += 1
            
        messagebox.showinfo("クリーンアップ完了", f"{count} 件のアイテムを削除しました。")

    def show_deploy_dialog(self):
        """サーバーデプロイ用の入力ダイアログを表示"""
        deploy_win = tk.Toplevel(self.root)
        deploy_win.title("サーバーセットアップ")
        deploy_win.geometry("300x300")
        
        ttk.Label(deploy_win, text="ホスト:").pack(pady=2)
        host_ent = ttk.Entry(deploy_win)
        host_ent.insert(0, config.get("server_ip", "192.168.0.109"))
        host_ent.pack(pady=2)
        
        ttk.Label(deploy_win, text="ポート:").pack(pady=2)
        port_ent = ttk.Entry(deploy_win)
        port_ent.insert(0, config.get("server_port", "9800"))
        port_ent.pack(pady=2)
        
        ttk.Label(deploy_win, text="ユーザー名:").pack(pady=2)
        user_ent = ttk.Entry(deploy_win)
        user_ent.insert(0, config.get("server_user", "ituki"))
        user_ent.pack(pady=2)
        
        ttk.Label(deploy_win, text="パスワード:").pack(pady=2)
        pass_ent = ttk.Entry(deploy_win, show="*")
        pass_ent.insert(0, config.get("server_pass", ""))
        pass_ent.pack(pady=2)
        
        def start_deploy():
            host = host_ent.get()
            port = port_ent.get()
            user = user_ent.get()
            pwd = pass_ent.get()
            port = port_ent.get()
            user = user_ent.get()
            pwd = pass_ent.get()
            # 設定を保存
            config.update({"server_ip": host, "server_port": port, "server_user": user, "server_pass": pwd})
            save_config(config)
            
            deploy_win.destroy()
            threading.Thread(target=self.run_deploy_worker, args=(host, port, user, pwd), daemon=True).start()

        ttk.Button(deploy_win, text="実行", command=start_deploy).pack(pady=10)

    def show_uninstall_dialog(self):
        """サーバー側のファイルを削除するための入力ダイアログを表示"""
        uninst_win = tk.Toplevel(self.root)
        uninst_win.title("サーバークリーンアップ")
        uninst_win.geometry("300x300")
        
        ttk.Label(uninst_win, text="ホスト:").pack(pady=2)
        host_ent = ttk.Entry(uninst_win)
        host_ent.insert(0, config.get("server_ip", "192.168.0.109"))
        host_ent.pack(pady=2)
        
        ttk.Label(uninst_win, text="ポート:").pack(pady=2)
        port_ent = ttk.Entry(uninst_win)
        port_ent.insert(0, config.get("server_port", "9800"))
        port_ent.pack(pady=2)
        
        ttk.Label(uninst_win, text="ユーザー名:").pack(pady=2)
        user_ent = ttk.Entry(uninst_win)
        user_ent.insert(0, config.get("server_user", "ituki"))
        user_ent.pack(pady=2)
        
        ttk.Label(uninst_win, text="パスワード:").pack(pady=2)
        pass_ent = ttk.Entry(uninst_win, show="*")
        pass_ent.insert(0, config.get("server_pass", ""))
        pass_ent.pack(pady=2)
        
        def start_uninstall():
            if not messagebox.askyesno("最終確認", "サーバー上のプログラムとサービスを完全に削除しますか？\n（写真は削除されません）"):
                return
            host = host_ent.get()
            port = port_ent.get()
            user = user_ent.get()
            pwd = pass_ent.get()
            uninst_win.destroy()
            threading.Thread(target=self.run_uninstall_worker, args=(host, port, user, pwd), daemon=True).start()

        ttk.Button(uninst_win, text="削除実行", command=start_uninstall).pack(pady=10)

    def run_uninstall_worker(self, host, port, user, pwd):
        """サーバー側の削除処理本体"""
        project_dir = "/srv/vrc/photo_manager"
        logger.info(f"--- サーバークリーンアップ開始: {host} ---")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=int(port), username=user, password=pwd, timeout=30)
            
            def exec_remote_simple(cmd, use_sudo=False):
                logger.info(f"実行中: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
                if use_sudo:
                    import time
                    time.sleep(0.5)
                    stdin.write(pwd + "\n")
                    stdin.flush()
                # 出力読み取り（デッドロック防止）
                for line in stdout: pass
                return stdout.channel.recv_exit_status()

            # 1. サービスの停止と削除
            logger.info("サービスを停止・削除中...")
            exec_remote_simple("sudo systemctl stop vrc-manager", use_sudo=True)
            exec_remote_simple("sudo systemctl disable vrc-manager", use_sudo=True)
            exec_remote_simple("sudo rm -f /etc/systemd/system/vrc-manager.service", use_sudo=True)
            exec_remote_simple("sudo systemctl daemon-reload", use_sudo=True)
            
            # 2. プログラムディレクトリの削除
            logger.info("プログラムディレクトリを削除中...")
            exec_remote_simple(f"sudo rm -rf {project_dir}", use_sudo=True)
            
            logger.info("--- サーバークリーンアップ完了！ ---")
            ssh.close()
            messagebox.showinfo("成功", "サーバー側の関連ファイルを削除しました。")
        except Exception as e:
            logger.error(f"削除エラー: {e}")
            messagebox.showerror("エラー", f"サーバー側ファイルの削除に失敗しました:\n{e}")

    def run_service_control(self, action):
        """サーバーサービスの開始・停止を実行"""
        host = config.get("server_ip")
        port = config.get("server_port")
        user = config.get("server_user")
        pwd = config.get("server_pass")
        
        if not all([host, port, user, pwd]):
            messagebox.showwarning("警告", "サーバー接続情報が不足しています。一度デプロイを実行してください。")
            return

        def worker():
            logger.info(f"サーバーサービスを {action} 中...")
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=int(port), username=user, password=pwd, timeout=10)
                
                cmd = f"sudo systemctl {action} vrc-manager"
                stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
                import time
                time.sleep(0.5)
                stdin.write(pwd + "\n")
                stdin.flush()
                
                # 終了を待機
                stdout.channel.recv_exit_status()
                ssh.close()
                logger.info(f"サービス {action} 完了")
            except Exception as e:
                logger.error(f"サービス操作エラー ({action}): {e}")

        threading.Thread(target=worker, daemon=True).start()

    def run_deploy_worker(self, host, port, user, pwd):
        """デプロイ処理の本体（スレッドで実行）"""
        project_dir = "/srv/vrc/photo_manager"
        logger.info(f"--- サーバーセットアップ開始: {host} ---")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 接続プロセスを効率化し、タイムアウト許容範囲を最大化
            ssh.connect(
                host, 
                port=int(port),
                username=user, 
                password=pwd, 
                timeout=300, # Increased timeout to 5 minutes
                banner_timeout=200,
                auth_timeout=60,
                allow_agent=False, 
                look_for_keys=False
            )
            
            def exec_remote(cmd, use_sudo=False):
                logger.info(f"実行中: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
                if use_sudo:
                    # sudoのパスワード入力待ちを考慮
                    import time
                    time.sleep(0.5)
                    stdin.write(pwd + "\n")
                    stdin.flush()
                
                # 出力を読み取らないとバッファフルでデッドロックするため、読み取りつつログに流す
                for line in stdout:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("[sudo] password for"):
                        logger.info(f"  [Remote] {line_str}")
                
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    logger.error(f"コマンド失敗 (Status {exit_status})")
                return exit_status

            # 1. 依存パッケージのインストール
            exec_remote("sudo apt-get update && sudo apt-get install -y python3-venv exiftool sqlite3", use_sudo=True)
            
            # 2. ディレクトリ作成
            exec_remote(f"sudo mkdir -p {project_dir} /srv/vrc/input /srv/vrc/photos /srv/vrc/loddb && sudo chown -R {user}:{user} /srv/vrc", use_sudo=True)
            
            # 3. サーバー用設定ファイルの生成と転送
            logger.info("サーバー用設定を生成中...")
            server_config = config.copy()
            server_config["log_dir"] = "/srv/vrc/logs"
            server_config["db_path"] = "/srv/vrc/loddb/photos.db"
            server_config["input_dir"] = "/srv/vrc/input"
            server_config["output_dir"] = "/srv/vrc/photos"
            server_config["server_ip"] = "0.0.0.0" # 外部からの接続を許可
            
            with open("config_server.json", "w", encoding="utf-8") as f:
                json.dump(server_config, f, indent=2)

            logger.info("ファイルを転送中...")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put("test.py", f"{project_dir}/main.py")
                scp.put("config_server.json", f"{project_dir}/config.json")
                scp.put("requirements.txt", f"{project_dir}/requirements.txt")
            os.remove("config_server.json")
            
            # 4. 仮想環境構築とライブラリインストール
            exec_remote(f"python3 -m venv {project_dir}/venv && {project_dir}/venv/bin/pip install --upgrade pip && {project_dir}/venv/bin/pip install -r {project_dir}/requirements.txt")
            
            # 5. Systemd サービス化
            service_content = f"""[Unit]
Description=VRChat Photo Manager
After=network.target

[Service]
User={user}
WorkingDirectory={project_dir}
ExecStart={project_dir}/venv/bin/python3 {project_dir}/main.py
Restart=always

[Install]
WantedBy=multi-user.target
"""
            with open("vrc-manager.service", "w") as f:
                f.write(service_content)
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put("vrc-manager.service", "/tmp/vrc-manager.service")
            os.remove("vrc-manager.service")
            
            exec_remote("sudo mv /tmp/vrc-manager.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable vrc-manager && sudo systemctl restart vrc-manager", use_sudo=True)
            
            logger.info("--- サーバーセットアップ完了！ ---")
            log_queue.put("DONE: サーバーでの稼働を開始しました。")
            
            ssh.close()
            messagebox.showinfo("成功", f"サーバー {host} へのデプロイが完了しました。")
            
        except Exception as e:
            logger.error(f"デプロイエラー: {e}")
            messagebox.showerror("エラー", f"デプロイに失敗しました:\n{e}")

    def update_logs(self):
        try:
            while True:
                msg = log_queue.get_nowait()
                self.log_win.log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.update_logs)

    def on_exit(self):
        # サーバーのサービスを停止させてから終了
        self.run_service_control("stop")
        
        if observer:
            observer.stop()
        self.root.after(1000, self.root.destroy) # 停止コマンド送信の猶予を与えて終了

def run_api():
    try:
        uvicorn.run(
            app, 
            host=config["server_ip"], 
            port=config["api_port"],
            log_level="info"
        )
    finally:
        if observer:
            observer.stop()
            observer.join()

# --- Main Execution ---
if __name__ == "__main__":
    init_db()
    observer = start_observer()
    
    # APIサーバーを別スレッドで起動
    threading.Thread(target=run_api, daemon=True).start()
    
    # Tkinter UI起動
    root = tk.Tk()
    app_ui = MainApp(root)
    app_ui.status_label.config(text="稼働中 (監視・API有効)", foreground="green")
    root.mainloop()