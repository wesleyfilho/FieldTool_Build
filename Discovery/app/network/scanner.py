"""Main network scanner orchestrator — runs in a QThread."""

import threading
from PySide6.QtCore import QThread, Signal, QObject
from app.network.arp_scan import scan_network, get_local_devices
from app.network.mndp import scan_mndp
from app.network.ubnt import scan_ubnt
from app.network.oui import lookup_vendor, is_mikrotik, is_ubiquiti
from app.database import db
from app.core.config import config


def _merge_device(base: dict, extra: dict) -> dict:
    """Merge extra info into base dict without overwriting non-empty values."""
    for k, v in extra.items():
        if v and not base.get(k):
            base[k] = v
    return base


def _enrich_device(device: dict) -> dict:
    """Add vendor info and determine OS type."""
    mac = device.get("mac", "")
    vendor = lookup_vendor(mac)
    device["vendor"] = vendor

    if device.get("os_type") in ("mikrotik", "ubiquiti", "local"):
        return device

    if is_mikrotik(mac):
        device["os_type"] = "mikrotik"
    elif is_ubiquiti(mac):
        device["os_type"] = "ubiquiti"
    else:
        device["os_type"] = "unknown"

    return device


class ScanWorker(QObject):
    device_found = Signal(dict)
    progress = Signal(str, int, int)    # message, current, total
    scan_complete = Signal(int)         # total devices found
    error = Signal(str)

    def __init__(self, scan_range: str = ""):
        super().__init__()
        self._stop = threading.Event()
        self._scan_range = scan_range

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            self._do_scan()
        except Exception as e:
            self.error.emit(str(e))
            db.add_log("ERROR", "DISCOVERY", f"Scan error: {e}")

    def _do_scan(self):
        found: dict[str, dict] = {}
        total_phases = 4

        # Phase 0: Local PC interfaces
        self.progress.emit("Detectando interfaces locais do PC...", 0, 0)
        try:
            for d in get_local_devices():
                ip = d.get("ip", "")
                if ip:
                    found[ip] = d
                    db.upsert_device(d)
                    self.device_found.emit(dict(d))
        except Exception as e:
            db.add_log("WARNING", "DISCOVERY", f"Local device error: {e}")

        # Phase 1: MNDP (MikroTik fast discovery)
        self.progress.emit("Executando MNDP discovery (MikroTik)...", 0, 0)
        if not self._stop.is_set():
            try:
                mndp_devices = scan_mndp(timeout=3.0)
                for d in mndp_devices:
                    ip = d.get("ip", "")
                    if ip:
                        d["os_type"] = "mikrotik"
                        found[ip] = _enrich_device(d)
                        db.upsert_device(found[ip])
                        self.device_found.emit(dict(found[ip]))
            except Exception as e:
                db.add_log("WARNING", "DISCOVERY", f"MNDP error: {e}")

        # Phase 2: UBNT discovery
        self.progress.emit("Executando UBNT discovery (Ubiquiti)...", 1, total_phases)
        if not self._stop.is_set():
            try:
                ubnt_devices = scan_ubnt(timeout=3.0)
                for d in ubnt_devices:
                    ip = d.get("ip", "")
                    if ip:
                        d["os_type"] = "ubiquiti"
                        if ip in found:
                            found[ip] = _merge_device(found[ip], d)
                        else:
                            found[ip] = _enrich_device(d)
                        db.upsert_device(found[ip])
                        self.device_found.emit(dict(found[ip]))
            except Exception as e:
                db.add_log("WARNING", "DISCOVERY", f"UBNT error: {e}")

        # Phase 3: ARP/Ping sweep
        self.progress.emit("Executando ARP/Ping sweep...", 2, total_phases)
        if not self._stop.is_set():
            scan_range = self._scan_range or config.get("scan_range", "")
            timeout_ms = config.get("ping_timeout_ms", 500)
            workers = config.get("scan_threads", 50)

            def progress_cb(ip: str, current: int, total: int):
                if not self._stop.is_set():
                    self.progress.emit(f"Pingando {ip}...", current, total)

            try:
                arp_devices = scan_network(
                    network=scan_range,
                    timeout_ms=timeout_ms,
                    max_workers=workers,
                    progress_cb=progress_cb,
                    stop_event=self._stop,
                )
                for d in arp_devices:
                    ip = d.get("ip", "")
                    if ip:
                        if ip in found:
                            found[ip] = _merge_device(found[ip], d)
                        else:
                            found[ip] = _enrich_device(d)
                            db.upsert_device(found[ip])
                            self.device_found.emit(dict(found[ip]))
                        # Update existing entries with ARP data (mac/ssh)
                        db.upsert_device(found[ip])
            except Exception as e:
                db.add_log("WARNING", "DISCOVERY", f"ARP scan error: {e}")

        # Mark devices not found in this scan as offline
        if not self._stop.is_set():
            db.mark_devices_offline(set(found.keys()))
            db.add_log("INFO", "DISCOVERY", f"Scan concluido: {len(found)} dispositivos encontrados")

        self.scan_complete.emit(len(found))


class ScanThread(QThread):
    device_found = Signal(dict)
    progress = Signal(str, int, int)
    scan_complete = Signal(int)
    error = Signal(str)

    def __init__(self, scan_range: str = "", parent=None):
        super().__init__(parent)
        self._worker = ScanWorker(scan_range)
        self._worker.device_found.connect(self.device_found)
        self._worker.progress.connect(self.progress)
        self._worker.scan_complete.connect(self.scan_complete)
        self._worker.error.connect(self.error)

    def run(self):
        self._worker.run()

    def stop(self):
        self._worker.stop()
        self.quit()
        self.wait(5000)
