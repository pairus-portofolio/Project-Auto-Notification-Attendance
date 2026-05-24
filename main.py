"""
main.py
-------
Entry point utama untuk menjalankan sistem monitoring absensi.

Cara menjalankan:
    python main.py          # Jalankan monitoring normal
    python main.py --test   # Uji koneksi Telegram tanpa memulai polling
    python main.py --debug  # Jalankan dengan log level DEBUG
"""

import sys
import logging

from config import settings
from monitor import AttendanceMonitor, setup_logging


def main() -> None:
    """Fungsi utama yang memulai sistem monitoring."""

    # Handle argumen command line sederhana
    args = sys.argv[1:]

    if "--debug" in args:
        import os
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Setup logging terlebih dahulu
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Memulai sistem monitor absensi POLBAN...")

    # Validasi konfigurasi sebelum memulai
    try:
        settings.validate()
    except SystemExit as e:
        print(str(e))
        sys.exit(1)

    # Mode tes koneksi
    if "--test" in args:
        logger.info("Mode tes: memeriksa koneksi ke Telegram...")
        from notifier import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.test_connection():
            success = notifier.send_message(
                "🧪 <b>Tes Koneksi Berhasil!</b>\n\n"
                "Bot Telegram monitor absensi POLBAN berfungsi dengan baik.\n"
                "Jalankan <code>python main.py</code> untuk memulai monitoring."
            )
            if success:
                print("\n✅ Tes berhasil! Periksa Telegram Anda.")
            else:
                print("\n❌ Koneksi berhasil tapi gagal mengirim pesan. Periksa TELEGRAM_CHAT_ID.")
        else:
            print("\n❌ Tes gagal! Periksa TELEGRAM_BOT_TOKEN di file .env.")
        sys.exit(0)

    # Mulai monitoring
    monitor = AttendanceMonitor()
    monitor.start()


if __name__ == "__main__":
    main()
