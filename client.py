"""
client.py
---------
Modul HTTP Client untuk mengakses portal akademik.polban.ac.id.
Menangani manajemen sesi (Cookie), User-Agent, dan Rate Limiting
agar request tidak dianggap sebagai serangan oleh server kampus.
"""

import time
import logging
import requests
from threading import Lock
from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate Limiter sederhana berbasis token bucket
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Membatasi jumlah request per detik menggunakan mekanisme token bucket.
    Secara default hanya mengizinkan 1 request per interval tertentu.
    """

    def __init__(self, min_interval_seconds: float = 2.0):
        """
        Args:
            min_interval_seconds: Jarak minimum antar request (detik).
        """
        self._min_interval = min_interval_seconds
        self._last_call_time: float = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        """Tunggu jika perlu agar interval minimum terpenuhi."""
        with self._lock:
            elapsed = time.monotonic() - self._last_call_time
            wait_time = self._min_interval - elapsed
            if wait_time > 0:
                logger.debug(f"RateLimiter: menunggu {wait_time:.2f} detik sebelum request berikutnya.")
                time.sleep(wait_time)
            self._last_call_time = time.monotonic()


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

class AkademikClient:
    """
    Client HTTP untuk berkomunikasi dengan portal akademik.polban.ac.id.
    Menggunakan sesi requests dengan Cookie dan User-Agent yang sudah dikonfigurasi.
    """

    BASE_URL = "https://akademik.polban.ac.id"
    ABSEN_PATH = "/ajar/absen"

    def __init__(self):
        self._session = requests.Session()
        self._rate_limiter = RateLimiter(min_interval_seconds=2.0)
        self._setup_session()

    def _setup_session(self) -> None:
        """Konfigurasi header dan cookie pada sesi requests."""
        self._session.headers.update(
            {
                "User-Agent": settings.USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        # Pasang cookie sesi akademik
        self._session.cookies.set(
            "akad_session",
            settings.COOKIE_AKAD_SESSION,
            domain="akademik.polban.ac.id",
        )
        logger.info("AkademikClient: sesi berhasil dikonfigurasi.")

    def refresh_cookie(self, new_cookie_value: str) -> None:
        """
        Perbarui nilai Cookie akad_session jika sesi kedaluwarsa.

        Args:
            new_cookie_value: Nilai cookie baru yang valid.
        """
        self._session.cookies.set(
            "akad_session",
            new_cookie_value,
            domain="akademik.polban.ac.id",
        )
        logger.info("AkademikClient: cookie akad_session berhasil diperbarui.")

    def get_absen_page(self) -> str | None:
        """
        Ambil konten HTML halaman absensi.

        Returns:
            String HTML halaman absensi, atau None jika terjadi error.
        """
        url = f"{self.BASE_URL}{self.ABSEN_PATH}"
        self._rate_limiter.wait()  # Pastikan rate limit terpenuhi

        try:
            logger.debug(f"AkademikClient: GET {url}")
            response = self._session.get(url, timeout=30)
            response.raise_for_status()

            # Deteksi redirect ke halaman login (sesi kedaluwarsa)
            if "login" in response.url.lower():
                logger.warning(
                    "AkademikClient: Sesi kedaluwarsa! "
                    "Diarahkan ke halaman login. Perbarui Cookie Anda."
                )
                return None

            return response.text

        except requests.exceptions.Timeout:
            logger.error("AkademikClient: Request timeout. Server tidak merespons dalam 30 detik.")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("AkademikClient: Gagal terhubung ke server. Periksa koneksi internet Anda.")
            return None
        except requests.exceptions.HTTPError as exc:
            logger.error(f"AkademikClient: HTTP error {exc.response.status_code}: {exc}")
            return None
        except requests.exceptions.RequestException as exc:
            logger.error(f"AkademikClient: Request error tidak terduga: {exc}")
            return None
