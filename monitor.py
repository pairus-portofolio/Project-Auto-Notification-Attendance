"""
monitor.py
----------
Modul utama yang mengintegrasikan semua komponen dan menjalankan
loop polling untuk memantau status absensi secara berkala.

Fitur utama:
- State tracking: notifikasi hanya dikirim SEKALI per jadwal per sesi
- Penanganan error yang robust (retry, session expired)
- Graceful shutdown via Ctrl+C
"""

import time
import logging
import signal
import sys
from datetime import datetime

from config import settings
from client import AkademikClient
from scraper import AbsenScraper, CourseAttendance
from notifier import TelegramNotifier

# ---------------------------------------------------------------------------
# Setup Logging
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Konfigurasi logging ke konsol dan file."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("monitor.log", encoding="utf-8"),
        ],
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Tracker
# ---------------------------------------------------------------------------

class AttendanceStateTracker:
    """
    Melacak jadwal mana yang sudah pernah mendapatkan notifikasi.
    Mencegah pengiriman notifikasi berulang (spam) untuk jadwal yang sama.

    State di-reset setiap hari tengah malam agar bisa menerima notifikasi
    lagi untuk hari berikutnya.
    """

    def __init__(self):
        self._notified_ids: set[str] = set()
        self._last_reset_date: str = self._today()

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _auto_reset_if_new_day(self) -> None:
        """Reset state tracker setiap hari baru."""
        today = self._today()
        if today != self._last_reset_date:
            count = len(self._notified_ids)
            self._notified_ids.clear()
            self._last_reset_date = today
            logger.info(
                f"StateTracker: Hari baru ({today}). "
                f"Reset {count} entri state dari kemarin."
            )

    def should_notify(self, schedule_id: str) -> bool:
        """
        Periksa apakah notifikasi perlu dikirim untuk jadwal ini.

        Args:
            schedule_id: ID unik jadwal.

        Returns:
            True jika belum pernah dinotifikasi hari ini.
        """
        self._auto_reset_if_new_day()
        return schedule_id not in self._notified_ids

    def mark_notified(self, schedule_id: str) -> None:
        """Tandai jadwal ini sebagai sudah dinotifikasi."""
        self._notified_ids.add(schedule_id)
        logger.debug(f"StateTracker: Jadwal '{schedule_id}' ditandai sudah dinotifikasi.")

    def get_notified_count(self) -> int:
        return len(self._notified_ids)


# ---------------------------------------------------------------------------
# Monitor Utama
# ---------------------------------------------------------------------------

class AttendanceMonitor:
    """
    Kelas utama yang mengintegrasikan semua komponen dan menjalankan
    loop polling berkelanjutan.
    """

    def __init__(self):
        self._client = AkademikClient()
        self._scraper = AbsenScraper()
        self._notifier = TelegramNotifier()
        self._state_tracker = AttendanceStateTracker()
        self._running = False
        self._session_expired_notified = False
        self._poll_count = 0

    def start(self) -> None:
        """
        Mulai loop monitoring. Berjalan sampai dihentikan dengan Ctrl+C.
        """
        logger.info("=" * 60)
        logger.info("  MONITOR ABSENSI POLBAN - AKTIF")
        logger.info(f"  Interval polling : {settings.POLL_INTERVAL_SECONDS} detik")
        logger.info(f"  Log level        : {settings.LOG_LEVEL}")
        logger.info("=" * 60)

        # Uji koneksi Telegram
        if not self._notifier.test_connection():
            logger.error(
                "Tidak dapat terhubung ke Telegram Bot API. "
                "Periksa TELEGRAM_BOT_TOKEN di file .env Anda."
            )
            sys.exit(1)

        # Kirim pesan startup (opsional)
        if settings.SEND_STARTUP_MESSAGE:
            self._notifier.send_startup_message()

        # Setup graceful shutdown
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Loop polling utama
        while self._running:
            self._poll_count += 1
            logger.info(f"--- Poll #{self._poll_count} | {datetime.now().strftime('%H:%M:%S')} ---")
            self._run_poll_cycle()

            if self._running:
                logger.info(
                    f"Menunggu {settings.POLL_INTERVAL_SECONDS} detik "
                    f"sebelum poll berikutnya..."
                )
                # Gunakan sleep berkala agar bisa merespons SIGINT dengan cepat
                self._interruptible_sleep(settings.POLL_INTERVAL_SECONDS)

        logger.info("Monitor dihentikan. Sampai jumpa!")

    def _run_poll_cycle(self) -> None:
        """Satu siklus polling: ambil HTML → parse → kirim notifikasi jika perlu."""
        html = self._client.get_absen_page()

        if html is None:
            # Mungkin sesi kedaluwarsa atau masalah koneksi
            if not self._session_expired_notified:
                self._notifier.send_session_expired_alert()
                self._session_expired_notified = True
                logger.warning(
                    "Gagal mengambil halaman absensi. "
                    "Notifikasi sesi kedaluwarsa telah dikirim ke Telegram."
                )
            return

        # Reset flag session expired jika berhasil
        self._session_expired_notified = False

        # Parse status absensi
        courses: list[CourseAttendance] = self._scraper.parse_attendance_status(html)

        if not courses:
            logger.info("Tidak ada jadwal absensi aktif saat ini.")
            return

        # Proses setiap mata kuliah
        for course in courses:
            self._process_course(course)

    def _process_course(self, course: CourseAttendance) -> None:
        """
        Proses satu mata kuliah: kirim notifikasi jika tombol aktif
        dan belum pernah dinotifikasi.
        """
        status_icon = "🟢" if course.is_active else "🔴"
        logger.info(
            f"  {status_icon} {course.course_name:<30} | "
            f"Aktif: {str(course.is_active):<5} | "
            f"Tombol: '{course.button_label}'"
        )

        if not course.is_active:
            return  # Tombol belum aktif, tidak perlu notifikasi

        if not self._state_tracker.should_notify(course.schedule_id):
            logger.info(
                f"  ⏭  {course.course_name}: Notifikasi sudah pernah dikirim hari ini. Skip."
            )
            return

        # Kirim notifikasi!
        logger.info(f"  📣 Mengirim notifikasi untuk: {course.course_name}")
        success = self._notifier.send_attendance_alert(course.course_name)

        if success:
            self._state_tracker.mark_notified(course.schedule_id)
        else:
            logger.error(
                f"  ❌ Gagal mengirim notifikasi untuk {course.course_name}. "
                f"Akan dicoba kembali pada poll berikutnya."
            )

    def _interruptible_sleep(self, seconds: int) -> None:
        """
        Tidur dalam interval kecil agar Ctrl+C bisa langsung direspons.
        """
        interval = 1  # cek setiap 1 detik
        elapsed = 0
        while self._running and elapsed < seconds:
            time.sleep(interval)
            elapsed += interval

    def _handle_shutdown(self, signum, frame) -> None:
        """Handler untuk SIGINT (Ctrl+C) dan SIGTERM."""
        logger.info(
            f"\n🛑 Menerima sinyal shutdown ({signum}). "
            f"Menghentikan monitor..."
        )
        self._running = False
