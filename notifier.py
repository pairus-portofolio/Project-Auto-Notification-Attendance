"""
notifier.py
-----------
Modul pengirim notifikasi ke Telegram menggunakan Bot API.
Menggunakan requests langsung (tanpa library pihak ketiga tambahan)
agar dependensi tetap minimal.
"""

import logging
import requests
from config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Mengirim pesan notifikasi ke Telegram melalui Bot API.

    Referensi API: https://core.telegram.org/bots/api#sendmessage
    """

    API_BASE = "https://api.telegram.org/bot{token}"
    TIMEOUT = 15  # detik

    def __init__(self):
        self._bot_token = settings.TELEGRAM_BOT_TOKEN
        self._chat_id = settings.TELEGRAM_CHAT_ID
        self._base_url = self.API_BASE.format(token=self._bot_token)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Kirim pesan teks ke Telegram.

        Args:
            text: Isi pesan. Mendukung format HTML atau Markdown.
            parse_mode: Mode format pesan ("HTML" atau "Markdown").

        Returns:
            True jika berhasil, False jika gagal.
        """
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                logger.info(f"TelegramNotifier: Pesan berhasil dikirim ke chat_id={self._chat_id}")
                return True
            else:
                error_desc = data.get("description", "Unknown error")
                logger.error(
                    f"TelegramNotifier: Gagal mengirim pesan. "
                    f"Status={response.status_code} | Error='{error_desc}'"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("TelegramNotifier: Timeout saat menghubungi Telegram API.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("TelegramNotifier: Gagal terhubung ke Telegram API. Periksa koneksi internet.")
            return False
        except requests.exceptions.RequestException as exc:
            logger.error(f"TelegramNotifier: Error tidak terduga: {exc}")
            return False

    def send_attendance_alert(self, course_name: str) -> bool:
        """
        Kirim pesan notifikasi khusus ketika tombol absensi aktif.

        Args:
            course_name: Nama mata kuliah yang absensinya sudah dibuka.

        Returns:
            True jika berhasil, False jika gagal.
        """
        message = (
            f"⚠️ <b>Absensi Sudah Dibuka!</b>\n\n"
            f"📚 Mata Kuliah: <b>{course_name}</b>\n\n"
            f"🔗 Segera absen di portal:\n"
            f"<a href='https://akademik.polban.ac.id/ajar/absen'>"
            f"akademik.polban.ac.id/ajar/absen</a>\n\n"
            f"⏰ Jangan sampai terlambat!"
        )
        logger.info(f"TelegramNotifier: Mengirim alert untuk mata kuliah '{course_name}'")
        return self.send_message(message)

    def send_session_expired_alert(self) -> bool:
        """Kirim notifikasi bahwa sesi cookie sudah kedaluwarsa."""
        message = (
            "🔴 <b>Sesi Portal Kedaluwarsa!</b>\n\n"
            "Cookie <code>akad_session</code> sudah tidak valid.\n"
            "Silakan login ulang ke portal dan perbarui nilai cookie "
            "di file <code>.env</code> Anda, lalu restart script.\n\n"
            "📖 Lihat README.md untuk panduan memperbarui cookie."
        )
        logger.warning("TelegramNotifier: Mengirim alert sesi kedaluwarsa.")
        return self.send_message(message)

    def send_startup_message(self) -> bool:
        """Kirim pesan konfirmasi ketika monitoring dimulai."""
        message = (
            "✅ <b>Monitor Absensi Aktif</b>\n\n"
            "Sistem pemantauan absensi POLBAN telah berjalan.\n"
            f"⏱ Interval polling: setiap <b>{settings.POLL_INTERVAL_SECONDS} detik</b>\n\n"
            "Anda akan mendapat notifikasi otomatis saat tombol absensi aktif."
        )
        return self.send_message(message)

    def test_connection(self) -> bool:
        """
        Uji koneksi ke Telegram Bot API.
        Berguna untuk validasi token dan chat_id sebelum memulai monitoring.

        Returns:
            True jika koneksi berhasil dan bot dapat mengirim pesan.
        """
        logger.info("TelegramNotifier: Menguji koneksi ke Telegram Bot API...")
        url = f"{self._base_url}/getMe"
        try:
            response = requests.get(url, timeout=self.TIMEOUT)
            data = response.json()
            if data.get("ok"):
                bot_name = data["result"].get("username", "unknown")
                logger.info(f"TelegramNotifier: Koneksi berhasil. Bot aktif: @{bot_name}")
                return True
            else:
                logger.error(
                    f"TelegramNotifier: Token tidak valid. "
                    f"Error: {data.get('description', 'Unknown')}"
                )
                return False
        except requests.exceptions.RequestException as exc:
            logger.error(f"TelegramNotifier: Gagal uji koneksi: {exc}")
            return False
