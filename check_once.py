"""
check_once.py
-------------
Mode single-check untuk GitHub Actions.
Script ini melakukan SATU siklus pengecekan lalu keluar.
State tracking disimpan ke file JSON lokal (di-cache oleh GitHub Actions).

Dijalankan otomatis oleh GitHub Actions setiap beberapa menit.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import settings
from client import AkademikClient
from scraper import AbsenScraper, CourseAttendance
from notifier import TelegramNotifier

# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State file (di-cache oleh GitHub Actions antar run)
# ---------------------------------------------------------------------------
STATE_FILE = Path(__file__).parent / "notified_state.json"


def load_state() -> dict:
    """
    Muat state dari file JSON.
    State berisi daftar schedule_id yang sudah dinotifikasi hari ini.
    Format: {"date": "2026-05-24", "notified": ["id1", "id2"]}
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            # Reset state jika hari sudah berganti
            if data.get("date") != today:
                logger.info(f"State lama dari {data.get('date')} direset untuk hari ini ({today}).")
                return {"date": today, "notified": []}
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"date": today, "notified": []}


def save_state(state: dict) -> None:
    """Simpan state ke file JSON."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.debug(f"State disimpan: {state}")


def main() -> None:
    logger.info("=" * 50)
    logger.info("  CHECK ABSENSI POLBAN — SINGLE RUN")
    logger.info(f"  Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # Validasi konfigurasi
    settings.validate()

    # Inisialisasi komponen
    client = AkademikClient()
    scraper = AbsenScraper()
    notifier = TelegramNotifier()

    # Muat state hari ini
    state = load_state()
    notified_ids: list[str] = state["notified"]

    # Ambil halaman absensi
    html = client.get_absen_page()
    if html is None:
        logger.error("Gagal mengambil halaman absensi. Kemungkinan sesi kedaluwarsa.")
        notifier.send_session_expired_alert()
        sys.exit(1)

    # Parse status absensi
    courses: list[CourseAttendance] = scraper.parse_attendance_status(html)

    if not courses:
        logger.info("Tidak ada jadwal absensi aktif saat ini.")
        sys.exit(0)

    # Proses tiap mata kuliah
    state_changed = False
    for course in courses:
        status_icon = "🟢" if course.is_active else "🔴"
        logger.info(
            f"{status_icon} {course.course_name:<30} | "
            f"Aktif: {str(course.is_active):<5} | "
            f"Tombol: '{course.button_label}'"
        )

        if not course.is_active:
            continue

        if course.schedule_id in notified_ids:
            logger.info(f"  ⏭  {course.course_name}: Sudah dinotifikasi hari ini. Skip.")
            continue

        # Kirim notifikasi
        logger.info(f"  📣 Mengirim notifikasi untuk: {course.course_name}")
        success = notifier.send_attendance_alert(course.course_name)

        if success:
            notified_ids.append(course.schedule_id)
            state_changed = True
            logger.info(f"  ✅ Notifikasi berhasil dikirim!")
        else:
            logger.error(f"  ❌ Gagal kirim notifikasi. Akan dicoba di run berikutnya.")

    # Simpan state jika ada perubahan
    if state_changed:
        state["notified"] = notified_ids
        save_state(state)

    logger.info("Check selesai.")


if __name__ == "__main__":
    main()
