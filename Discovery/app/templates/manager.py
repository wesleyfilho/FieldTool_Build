"""Template manager — loads built-in templates and manages user templates."""

import json
import sys
from pathlib import Path
from app.database import db

# PyInstaller empacota dados em sys._MEIPASS; em script normal usa __file__
if getattr(sys, "frozen", False):
    TEMPLATES_DIR = Path(sys._MEIPASS) / "app" / "templates"
else:
    TEMPLATES_DIR = Path(__file__).parent

BUILTIN_TEMPLATES = [
    TEMPLATES_DIR / "mikrotik_ap.json",
    TEMPLATES_DIR / "mikrotik_cliente.json",
    TEMPLATES_DIR / "ubnt_ap.json",
]


def load_builtin_templates():
    """Seed database with built-in templates (only if not already present)."""
    existing = {t["name"] for t in db.get_templates()}
    for path in BUILTIN_TEMPLATES:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["name"] not in existing:
                db.save_template(
                    name=data["name"],
                    device_type=data["device_type"],
                    config_type=data["config_type"],
                    config_data=json.dumps(data),
                )
        except Exception:
            pass


def get_templates(device_type: str = "") -> list[dict]:
    load_builtin_templates()
    rows = db.get_templates(device_type)
    result = []
    for row in rows:
        try:
            data = json.loads(row["config_data"])
            data["id"] = row["id"]
            data["created_at"] = row.get("created_at", "")
            result.append(data)
        except Exception:
            result.append(row)
    return result


def save_template(name: str, device_type: str, config_type: str, params: dict) -> bool:
    try:
        data = {
            "name": name,
            "device_type": device_type,
            "config_type": config_type,
            "params": params,
        }
        db.save_template(name, device_type, config_type, json.dumps(data))
        return True
    except Exception:
        return False


def delete_template(name: str) -> bool:
    try:
        db.delete_template(name)
        return True
    except Exception:
        return False


def export_template(name: str, path: str) -> bool:
    try:
        templates = get_templates()
        t = next((t for t in templates if t["name"] == name), None)
        if not t:
            return False
        Path(path).write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def import_template(path: str) -> tuple[bool, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        required = ("name", "device_type", "config_type")
        if not all(k in data for k in required):
            return False, "Arquivo de template invalido"
        save_template(data["name"], data["device_type"], data["config_type"], data.get("params", {}))
        return True, data["name"]
    except Exception as e:
        return False, str(e)
