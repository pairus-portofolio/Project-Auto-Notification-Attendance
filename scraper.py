"""
scraper.py
----------
Modul scraping untuk memeriksa status tombol absensi pada halaman portal akademik.
Menggunakan BeautifulSoup untuk mem-parsing HTML dan mengidentifikasi
apakah tombol absensi sedang aktif/bisa diklik untuk setiap mata kuliah.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class CourseAttendance:
    """Representasi status absensi untuk satu mata kuliah."""

    course_name: str
    schedule_id: str          # ID unik jadwal (dipakai sebagai kunci state tracking)
    is_active: bool           # True jika tombol absensi aktif/bisa diklik
    button_label: str = ""    # Label teks pada tombol (misal: "Absen", "Sudah Absen")
    raw_class: str = ""       # Class HTML asli untuk debugging


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class AbsenScraper:
    """
    Parser HTML untuk halaman absensi akademik.polban.ac.id/ajar/absen.

    Strategi deteksi tombol aktif:
    - Tombol aktif biasanya memiliki class btn-primary, btn-success, atau
      tidak memiliki atribut 'disabled'.
    - Tombol tidak aktif biasanya memiliki class btn-secondary, btn-default,
      atau memiliki atribut 'disabled'.

    CATATAN: Anda mungkin perlu menyesuaikan selector HTML di bawah ini
    setelah memeriksa struktur HTML asli halaman absensi kampus Anda.
    Gunakan Developer Tools browser (F12) untuk inspeksi elemen.
    """

    # Kelas CSS yang menandakan tombol AKTIF (bisa diklik)
    ACTIVE_BUTTON_CLASSES = {
        "btn-primary",
        "btn-success",
        "btn-warning",
        "btn-info",
    }

    # Kelas CSS yang menandakan tombol TIDAK AKTIF / sudah diklik
    INACTIVE_BUTTON_CLASSES = {
        "btn-secondary",
        "btn-default",
        "btn-light",
        "btn-outline-secondary",
        "disabled",
    }

    def parse_attendance_status(self, html: str) -> list[CourseAttendance]:
        """
        Parse HTML dan kembalikan daftar status absensi per mata kuliah.

        Args:
            html: String HTML dari halaman absensi.

        Returns:
            List CourseAttendance. List kosong jika tidak ada jadwal atau parsing gagal.
        """
        if not html:
            logger.warning("AbsenScraper: HTML kosong, tidak ada yang di-parse.")
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: list[CourseAttendance] = []

        # ---------------------------------------------------------------
        # Cari semua baris jadwal pada tabel absensi.
        # Selector ini mencari baris <tr> di dalam elemen dengan id/class
        # yang umumnya dipakai portal Polban. SESUAIKAN jika berbeda.
        # ---------------------------------------------------------------
        schedule_rows = self._find_schedule_rows(soup)

        if not schedule_rows:
            logger.info("AbsenScraper: Tidak ada jadwal absensi yang ditemukan di halaman.")
            return []

        for row in schedule_rows:
            attendance = self._parse_row(row)
            if attendance:
                results.append(attendance)
                logger.debug(
                    f"AbsenScraper: [{attendance.course_name}] "
                    f"aktif={attendance.is_active} | "
                    f"class='{attendance.raw_class}'"
                )

        logger.info(f"AbsenScraper: Ditemukan {len(results)} jadwal absensi.")
        return results

    def _find_schedule_rows(self, soup: BeautifulSoup) -> list[Tag]:
        """
        Cari baris-baris jadwal dalam tabel HTML.

        Mencoba beberapa strategi selector secara berurutan agar lebih robust:
        1. Tabel dengan id 'tabel-jadwal' atau class 'table-jadwal'
        2. Semua <tr> yang mengandung tombol absensi
        3. Div card yang berisi informasi jadwal
        """
        rows: list[Tag] = []

        # Strategi 1: Cari tabel spesifik berdasarkan ID
        table = soup.find("table", {"id": "tabel-jadwal"})
        if table is None:
            # Coba cari berdasarkan class
            table = soup.find("table", class_=lambda c: c and "jadwal" in c.lower())

        if table:
            rows = table.find_all("tr")[1:]  # Skip header row
            if rows:
                logger.debug(f"AbsenScraper: Ditemukan tabel jadwal dengan {len(rows)} baris.")
                return rows

        # Strategi 2: Cari semua <tr> yang mengandung tombol absensi
        all_rows = soup.find_all("tr")
        rows = [
            row for row in all_rows
            if row.find("button", class_=lambda c: c and "btn" in c.lower())
            or row.find("a", class_=lambda c: c and "btn" in c.lower())
        ]
        if rows:
            logger.debug(f"AbsenScraper: Ditemukan {len(rows)} baris dengan tombol absensi.")
            return rows

        # Strategi 3: Cari div card jadwal
        cards = soup.find_all("div", class_=lambda c: c and (
            "card" in c.lower() or "jadwal" in c.lower()
        ))
        if cards:
            logger.debug(f"AbsenScraper: Menggunakan {len(cards)} card sebagai jadwal.")
            return cards

        return []

    def _parse_row(self, row: Tag) -> Optional[CourseAttendance]:
        """
        Ekstrak informasi absensi dari satu baris/elemen jadwal.

        Args:
            row: Elemen BeautifulSoup yang mewakili satu jadwal.

        Returns:
            CourseAttendance atau None jika parsing gagal.
        """
        try:
            # ---------------------------------------------------------------
            # Ekstrak nama mata kuliah
            # Coba beberapa selector umum
            # ---------------------------------------------------------------
            course_name = self._extract_course_name(row)
            if not course_name:
                return None

            # ---------------------------------------------------------------
            # Ekstrak ID unik jadwal (dari atribut data-*, id, atau href)
            # ---------------------------------------------------------------
            schedule_id = self._extract_schedule_id(row, course_name)

            # ---------------------------------------------------------------
            # Periksa status tombol absensi
            # ---------------------------------------------------------------
            is_active, button_label, raw_class = self._check_button_status(row)

            return CourseAttendance(
                course_name=course_name,
                schedule_id=schedule_id,
                is_active=is_active,
                button_label=button_label,
                raw_class=raw_class,
            )

        except Exception as exc:
            logger.error(f"AbsenScraper: Error parsing baris: {exc}", exc_info=True)
            return None

    def _extract_course_name(self, row: Tag) -> str:
        """Coba ekstrak nama mata kuliah dari berbagai kemungkinan selector."""
        # Selector 1: <td> dengan class 'matkul', 'mata-kuliah', atau 'course'
        for class_hint in ["matkul", "mata-kuliah", "course", "nama-mk", "subject"]:
            el = row.find(class_=lambda c: c and class_hint in c.lower() if c else False)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)

        # Selector 2: <td> pertama yang berisi teks (bukan angka saja)
        cells = row.find_all("td")
        for cell in cells:
            text = cell.get_text(strip=True)
            if text and not text.isdigit() and len(text) > 3:
                return text

        # Selector 3: heading atau strong di dalam card
        for tag in ["h5", "h6", "strong", "b"]:
            el = row.find(tag)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)

        return ""

    def _extract_schedule_id(self, row: Tag, course_name: str) -> str:
        """Coba ekstrak ID unik jadwal sebagai kunci state tracking."""
        # Cari atribut data-id atau data-jadwal
        for attr in ["data-id", "data-jadwal-id", "data-schedule-id", "id"]:
            val = row.get(attr) or ""
            if val:
                return str(val)

        # Cari di tombol/link
        button = row.find(["button", "a"])
        if button:
            for attr in ["data-id", "data-jadwal-id", "href", "id"]:
                val = button.get(attr) or ""
                if val and val != "#":
                    return str(val)

        # Fallback: gunakan nama mata kuliah sebagai ID
        return course_name.lower().replace(" ", "_")

    def _check_button_status(self, row: Tag) -> tuple[bool, str, str]:
        """
        Periksa apakah tombol absensi aktif.

        Returns:
            Tuple (is_active, button_label, raw_class)
        """
        # Cari elemen tombol (button atau anchor dengan class btn)
        button = row.find("button", class_=lambda c: c and "btn" in c.lower())
        if button is None:
            button = row.find("a", class_=lambda c: c and "btn" in c.lower())

        if button is None:
            logger.debug("AbsenScraper: Tidak ditemukan tombol pada baris ini.")
            return False, "", ""

        classes: list[str] = button.get("class", [])
        raw_class = " ".join(classes)
        label = button.get_text(strip=True)

        # Cek apakah tombol memiliki atribut disabled
        if button.has_attr("disabled"):
            return False, label, raw_class

        class_set = set(classes)

        # Cek kelas tidak aktif lebih dulu
        if class_set & self.INACTIVE_BUTTON_CLASSES:
            return False, label, raw_class

        # Cek kelas aktif
        if class_set & self.ACTIVE_BUTTON_CLASSES:
            return True, label, raw_class

        # Jika tidak ada class yang cocok, anggap tidak aktif
        return False, label, raw_class
