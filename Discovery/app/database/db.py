import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from app.core.config import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        db_path = Path(config.get("db_path"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_tables(_conn)
    return _conn


@contextmanager
def get_db():
    with _lock:
        conn = _get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL UNIQUE,
            mac TEXT,
            hostname TEXT,
            vendor TEXT,
            model TEXT,
            os_type TEXT,
            status TEXT DEFAULT 'online',
            ssh_open INTEGER DEFAULT 0,
            api_open INTEGER DEFAULT 0,
            uptime TEXT,
            firmware TEXT,
            last_seen TEXT,
            first_seen TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            username_enc TEXT NOT NULL,
            password_enc TEXT NOT NULL,
            device_type TEXT,
            port INTEGER DEFAULT 22,
            proto TEXT DEFAULT 'ssh',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ip, proto)
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            level TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            device_ip TEXT
        );

        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            device_type TEXT NOT NULL,
            config_type TEXT NOT NULL,
            config_data TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            device_ip TEXT DEFAULT '',
            device_mac TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            file_size INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip);
        CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
        CREATE INDEX IF NOT EXISTS idx_backups_type ON backups(device_type);
    """)
    conn.commit()


# --- Devices ---

def upsert_device(data: dict) -> int:
    with get_db() as conn:
        now = datetime.now().isoformat(timespec="seconds")
        existing = conn.execute("SELECT id, first_seen FROM devices WHERE ip=?", (data["ip"],)).fetchone()
        if existing:
            conn.execute("""
                UPDATE devices SET mac=?, hostname=?, vendor=?, model=?, os_type=?,
                status=?, ssh_open=?, api_open=?, uptime=?, firmware=?, last_seen=?
                WHERE ip=?
            """, (
                data.get("mac"), data.get("hostname"), data.get("vendor"),
                data.get("model"), data.get("os_type"), data.get("status", "online"),
                int(data.get("ssh_open", 0)), int(data.get("api_open", 0)),
                data.get("uptime"), data.get("firmware"), now, data["ip"]
            ))
            return existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO devices (ip, mac, hostname, vendor, model, os_type,
                status, ssh_open, api_open, uptime, firmware, last_seen, first_seen)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["ip"], data.get("mac"), data.get("hostname"), data.get("vendor"),
                data.get("model"), data.get("os_type"), data.get("status", "online"),
                int(data.get("ssh_open", 0)), int(data.get("api_open", 0)),
                data.get("uptime"), data.get("firmware"), now, now
            ))
            return cur.lastrowid


def get_all_devices() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
        return [dict(r) for r in rows]


def mark_devices_offline(active_ips: set):
    with get_db() as conn:
        placeholders = ",".join("?" * len(active_ips)) if active_ips else "''"
        if active_ips:
            conn.execute(
                f"UPDATE devices SET status='offline' WHERE ip NOT IN ({placeholders})",
                list(active_ips)
            )
        else:
            conn.execute("UPDATE devices SET status='offline'")


def delete_device(ip: str):
    with get_db() as conn:
        conn.execute("DELETE FROM devices WHERE ip=?", (ip,))


# --- Credentials ---

def save_credential(ip: str, username_enc: str, password_enc: str,
                    device_type: str = "", port: int = 22, proto: str = "ssh"):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO credentials (ip, username_enc, password_enc, device_type, port, proto)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(ip, proto) DO UPDATE SET
                username_enc=excluded.username_enc,
                password_enc=excluded.password_enc,
                device_type=excluded.device_type,
                port=excluded.port
        """, (ip, username_enc, password_enc, device_type, port, proto))


def get_credential(ip: str, proto: str = "ssh") -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM credentials WHERE ip=? AND proto=?", (ip, proto)
        ).fetchone()
        return dict(row) if row else None


# --- Logs ---

def add_log(level: str, category: str, message: str, device_ip: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO logs (level, category, message, device_ip) VALUES (?,?,?,?)",
            (level, category, message, device_ip)
        )


def get_logs(limit: int = 500, level: str = "", category: str = "") -> list[dict]:
    with get_db() as conn:
        q = "SELECT * FROM logs WHERE 1=1"
        params: list = []
        if level:
            q += " AND level=?"
            params.append(level)
        if category:
            q += " AND category=?"
            params.append(category)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def clear_logs():
    with get_db() as conn:
        conn.execute("DELETE FROM logs")


# --- Templates ---

def save_template(name: str, device_type: str, config_type: str, config_data: str):
    with get_db() as conn:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("""
            INSERT INTO templates (name, device_type, config_type, config_data, created_at, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                device_type=excluded.device_type,
                config_type=excluded.config_type,
                config_data=excluded.config_data,
                updated_at=excluded.updated_at
        """, (name, device_type, config_type, config_data, now, now))


def get_templates(device_type: str = "") -> list[dict]:
    with get_db() as conn:
        if device_type:
            rows = conn.execute(
                "SELECT * FROM templates WHERE device_type=? ORDER BY name",
                (device_type,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM templates ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def delete_template(name: str):
    with get_db() as conn:
        conn.execute("DELETE FROM templates WHERE name=?", (name,))


# --- Backups ---

def save_backup(name: str, device_type: str, filename: str,
                device_ip: str = "", device_mac: str = "",
                notes: str = "", file_size: int = 0) -> int:
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO backups (name, device_type, filename, device_ip, device_mac, notes, file_size)
            VALUES (?,?,?,?,?,?,?)
        """, (name, device_type, filename, device_ip, device_mac, notes, file_size))
        return cur.lastrowid


def get_backups() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM backups ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_backup_by_id(backup_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM backups WHERE id=?", (backup_id,)).fetchone()
        return dict(row) if row else None


def delete_backup(backup_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM backups WHERE id=?", (backup_id,))
