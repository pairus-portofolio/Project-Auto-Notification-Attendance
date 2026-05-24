"""
config.py
---------
Manajemen konfigurasi dari environment variables (.env).
Semua nilai sensitif (token, cookie) dibaca dari file .env
agar tidak pernah ditulis langsung di kode sumber.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Muat variabel dari file .env di direktori yang sama
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


class _Settings:
    """
    Kelas konfigurasi yang membaca nilai dari environment variables.
    Validasi dilakukan saat pertama kali diakses.
    """

    # -----------------------------------------------------------------------
    # Telegram
    # -----------------------------------------------------------------------

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        val = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not val:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN belum dikonfigurasi! "
                "Silakan isi nilai ini di file .env Anda."
            )
        return val

    @property
    def TELEGRAM_CHAT_ID(self) -> str:
        val = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not val:
            raise ValueError(
                "TELEGRAM_CHAT_ID belum dikonfigurasi! "
                "Silakan isi nilai ini di file .env Anda."
            )
        return val

    # -----------------------------------------------------------------------
    # Cookie & User-Agent
    # -----------------------------------------------------------------------

    @property
    def COOKIE_AKAD_SESSION(self) -> str:
        val = os.getenv("COOKIE_AKAD_SESSION", "").strip()
        if not val:
            raise ValueError(
                "COOKIE_AKAD_SESSION belum dikonfigurasi! "
                "Silakan login ke portal dan salin nilai cookie akad_session ke file .env."
            )
        return val

    @property
    def USER_AGENT(self) -> str:
        default = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        return os.getenv("USER_AGENT", default).strip()

    # -----------------------------------------------------------------------
    # Pengaturan Polling
    # -----------------------------------------------------------------------

    @property
    def POLL_INTERVAL_SECONDS(self) -> int:
        """Interval polling dalam detik (default: 60 detik)."""
        try:
            return int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
        except ValueError:
            return 60

    @property
    def LOG_LEVEL(self) -> str:
        """Level logging (DEBUG, INFO, WARNING, ERROR)."""
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def SEND_STARTUP_MESSAGE(self) -> bool:
        """Kirim pesan ke Telegram saat script pertama kali dijalankan."""
        return os.getenv("SEND_STARTUP_MESSAGE", "true").lower() == "true"

    def validate(self) -> None:
        """
        Validasi semua konfigurasi wajib sekaligus.
        Panggil fungsi ini di awal script untuk mendapatkan laporan error yang jelas.
        """
        errors: list[str] = []
        required_fields = {
            "TELEGRAM_BOT_TOKEN": self.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID": self.TELEGRAM_CHAT_ID,
            "COOKIE_AKAD_SESSION": self.COOKIE_AKAD_SESSION,
        }
        for field_name, getter in required_fields.items():
            try:
                _ = getter
            except ValueError as e:
                errors.append(f"  - {e}")

        if errors:
            raise SystemExit(
                "\n❌ Konfigurasi tidak lengkap! Perbaiki file .env Anda:\n"
                + "\n".join(errors)
            )


# Singleton instance
settings = _Settings()
