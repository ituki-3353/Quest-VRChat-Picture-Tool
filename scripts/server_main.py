import os
import json
import sqlite3
import hashlib
import logging
import re
import shutil
import subprocess
import threading
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
CONFIG_PATH = "config.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()

# --- Database Layer (LODDB) ---
def init_db():
    db_path = config.get("db_path", "/srv/vrc/loddb/photos.db")
    logger.info(f"Initializing database at: {db_path}")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    with conn:
        # 1. ワールド情報テーブル
        conn.execute('''
            CREATE TABLE IF NOT EXISTS worlds (
                world_id TEXT PRIMARY KEY,
                world_name TEXT,
                instance_id TEXT,
                last_visited TIMESTAMP
            )
        ''')
        # 2. 写真基本情報テーブル (正規化)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE,
                original_path TEXT,
                managed_path TEXT,
                file_name TEXT,
                created_at TIMESTAMP,
                world_id TEXT,
                user_name TEXT,
                latitude REAL,
                longitude REAL,
                FOREIGN KEY(world_id) REFERENCES worlds(world_id)
            )
        ''')
        # 3. 撮影時に同席していたプレイヤー情報
        conn.execute('''
            CREATE TABLE IF NOT EXISTS photo_players (
                photo_id INTEGER,
                player_name TEXT,
                avatar_id TEXT,
                FOREIGN KEY(photo_id) REFERENCES photos(id)
            )
        ''')
    conn.commit()
    conn.close()

# --- Metadata Engine (ExifTool) ---
def get_exif_metadata(file_path: str) -> dict:
    """ExifToolを使用して撮影日時・GPS・ワールド名(Description)を抽出"""
    try:
        # -j (JSON出力)
        cmd = ["exiftool", "-j", "-DateTimeOriginal", "-GPSLatitude", "-GPSLongitude", "-Description", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except Exception as e:
        logger.error(f"ExifTool Error for {file_path}: {e}")
        return {}

def calculate_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# --- Processing Engine ---
def find_vrc_context_at(target_dt: datetime):
    """ログを解析して指定時刻のワールドと滞在プレイヤーを特定する"""
    log_dir = config.get("log_dir", "/srv/vrc/logs")
    if not os.path.exists(log_dir):
        return None

    current_world = {"id": "Unknown", "name": "Unknown", "instance": ""}
    active_players = {} # name -> avatar_id

    # ログファイルを時間順に走査（撮影時刻を含む可能性のあるログを探す）
    log_files = sorted([os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.txt')])
    
    # 簡易的な実装: すべてのログからタイムラインを構築（本来はインデックス化が望ましい）
    for log_path in log_files:
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    # タイムスタンプ抽出 (2026.05.11 21:20:13)
                    ts_match = re.match(r'^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not ts_match: continue
                    
                    line_dt = datetime.strptime(ts_match.group(1), '%Y.%m.%d %H:%M:%S')
                    if line_dt > target_dt:
                        break # 撮影時刻を超えたら終了

                    # ワールド入室判定
                    if "Entering Room:" in line:
                        w_name = line.split("Entering Room:")[1].strip()
                        current_world["name"] = w_name
                    
                    id_match = re.search(r'Joining (wrld_[a-z0-9-]+):?([~\w]*)', line)
                    if id_match:
                        current_world["id"] = id_match.group(1)
                        current_world["instance"] = id_match.group(2)
                        active_players = {} # ワールド移動でリセット

                    # プレイヤー入室/初期化判定
                    # [Behaviour] OnPlayerJoined user (usr_...)
                    p_join = re.search(r'OnPlayerJoined ([^ ]+) \((usr_[a-z0-9-]+)\)', line)
                    if p_join:
                        active_players[p_join.group(1)] = "Unknown"

                    # アバター読み込み (直前のプレイヤーに紐付け)
                    av_match = re.search(r'Switching (.+) to avatar (.+)', line)
                    if av_match:
                        p_name = av_match.group(1).strip()
                        if p_name in active_players:
                            active_players[p_name] = av_match.group(2).strip()

                    # プレイヤー退出判定
                    p_left = re.search(r'OnPlayerLeft ([^ ]+)', line)
                    if p_left:
                        active_players.pop(p_left.group(1), None)
                    
                    # インスタンス破棄（ルーム退出）
                    if "OnLeftRoom" in line:
                        current_world = {"id": "Unknown", "name": "Unknown", "instance": ""}
                        active_players = {}

        except Exception as e:
            logger.error(f"Log parse error in {log_path}: {e}")
            continue
            
    return {
        "world": current_world,
        "players": [{"name": n, "avatar": a} for n, a in active_players.items()]
    }

def process_image(file_path: str):
    """画像の解析、命名、DB登録、管理フォルダへのコピー"""
    try:
        file_hash = calculate_hash(file_path)
        db_path = config.get("db_path", "/srv/vrc/loddb/photos.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 重複チェック (SHA256)
        cursor.execute("SELECT id FROM photos WHERE file_hash = ?", (file_hash,))
        if cursor.fetchone():
            logger.info(f"Duplicate detected, skipping: {os.path.basename(file_path)}")
            return

        # 2. メタデータ抽出
        exif = get_exif_metadata(file_path)
        
        # 撮影日時の特定 (Exif優先、なければファイル名、最後は作成日時)
        dt = None
        if "DateTimeOriginal" in exif:
            try:
                dt = datetime.strptime(exif["DateTimeOriginal"], '%Y:%m:%d %H:%M:%S')
            except: pass
        
        if not dt:
            # VRChat_YYYY-MM-DD_HH-MM-SS 形式から抽出
            match = re.search(r'VRChat_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})', os.path.basename(file_path))
            if match:
                dt = datetime.strptime(f"{match.group(1)} {match.group(2)}", '%Y-%m-%d %H-%M-%S')
            else:
                dt = datetime.fromtimestamp(os.path.getctime(file_path))

        # 3. 命名 (Naming Engine)
        world = exif.get("Description", "UnknownWorld")
        user = config.get("server_user", "ituki")
        ext = Path(file_path).suffix
        
        new_name = config.get("naming_template", "{date}_{world}_{user}_{seq}").format(
            date=dt.strftime("%Y%m%d_%H%M%S"),
            world=world,
            user=user,
            seq=file_hash[:8]
        ) + ext

        output_dir = config.get("output_dir", "/srv/vrc/photos")
        managed_path = os.path.join(output_dir, new_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # ファイルコピー
        shutil.copy2(file_path, managed_path)

        # 4. DB登録 (LODDB)
        cursor.execute('''
            INSERT INTO photos (
                file_hash, original_path, managed_path, file_name, created_at, 
                world_name, user_name, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_hash, file_path, managed_path, new_name, dt, 
            world, user, exif.get("GPSLatitude"), exif.get("GPSLongitude")
        ))
        
        conn.commit()
        logger.info(f"Processed and managed: {new_name}")
    except Exception as e:
        logger.error(f"Processing failed for {file_path}: {e}")
    finally:
        conn.close()

# --- Watchdog ---
class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            # ファイルの書き込み完了を待つため1秒猶予
            threading.Timer(1.0, process_image, args=[event.src_path]).start()

def start_watchdog():
    input_dir = config.get("input_dir", "/srv/vrc/input")
    os.makedirs(input_dir, exist_ok=True)
    obs = Observer()
    obs.schedule(ImageHandler(), input_dir, recursive=False)
    obs.start()
    logger.info(f"Monitoring directory: {input_dir}")
    return obs

# --- FastAPI ---
app = FastAPI(title="VRChat Photo Server API")

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head><title>VRChat Photo Library</title><style>body{font-family:sans-serif;background:#121212;color:white;padding:20px;} .gallery{display:grid;grid-template-columns:repeat(auto-fill, minmax(250px, 1fr));gap:15px;} .card{background:#1e1e1e;padding:10px;border-radius:8px;} img{width:100%;border-radius:4px;}</style></head>
        <body>
            <h1>ituki-server Photo Library</h1>
            <div id="gallery" class="gallery">Loading...</div>
            <script>
                fetch('/api/photos').then(r=>r.json()).then(data=>{
                    const container = document.getElementById('gallery');
                    container.innerHTML = data.map(p=>`
                        <div class="card">
                            <img src="/api/image/${p.id}">
                            <p style="font-size:0.8em;margin-top:8px;">${p.file_name}<br><b>${p.world_name}</b></p>
                        </div>
                    `).join('');
                });
            </script>
        </body>
    </html>
    """

@app.get("/api/photos")
async def list_photos(world: Optional[str] = None):
    db_path = config.get("db_path", "/srv/vrc/loddb/photos.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        SELECT p.id, p.file_name, w.world_name 
        FROM photos p 
        LEFT JOIN worlds w ON p.world_id = w.world_id 
        WHERE 1=1
    """
    params = []
    if world:
        query += " AND w.world_name LIKE ?"
        params.append(f"%{world}%")
    cursor.execute(query + " ORDER BY p.created_at DESC LIMIT 100", params)
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "file_name": r[1], "world_name": r[2]} for r in rows]

@app.get("/api/image/{photo_id}")
async def get_image(photo_id: int):
    db_path = config.get("db_path", "/srv/vrc/loddb/photos.db")
    conn = sqlite3.connect(db_path)
    res = conn.execute("SELECT managed_path FROM photos WHERE id = ?", (photo_id,)).fetchone()
    conn.close()
    if res and os.path.exists(res[0]):
        return FileResponse(res[0])
    raise HTTPException(status_code=404, detail="Image not found")

@app.post("/api/import/scan")
async def manual_scan():
    """入力フォルダを再スキャン"""
    input_dir = config.get("input_dir", "/srv/vrc/input")
    files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    for f in files:
        process_image(f)
    return {"status": "success", "count": len(files)}

if __name__ == "__main__":
    observer = None
    try:
        init_db()
        observer = start_watchdog()
        
        # ネットワーク設定
        api_port = int(config.get("api_port", 1010))
        logger.info(f"Starting API server on host 0.0.0.0, port {api_port}")
        
        uvicorn.run(app, host="0.0.0.0", port=api_port, log_level="info")
    except Exception as e:
        logger.critical(f"FATAL ERROR AT STARTUP: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if observer:
            observer.stop()
            observer.join()