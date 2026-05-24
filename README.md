# 🔔 Monitor Absensi POLBAN

Sistem notifikasi berbasis Python yang **memonitor** status tombol absensi di portal akademik.polban.ac.id dan mengirimkan **notifikasi Telegram** secara otomatis saat tombol absensi aktif.

> ⚠️ **Penting**: Sistem ini **tidak** melakukan absensi otomatis. Ia hanya memberitahu Anda kapan harus absen.

---

## 📁 Struktur Proyek

```
Attendace-Notification/
├── main.py          # Entry point — jalankan file ini
├── monitor.py       # Loop polling & state tracking
├── client.py        # HTTP client dengan manajemen sesi & rate limiter
├── scraper.py       # Parser HTML untuk mendeteksi status tombol absensi
├── notifier.py      # Pengirim notifikasi ke Telegram
├── config.py        # Manajemen konfigurasi dari .env
├── .env.example     # Template konfigurasi (salin ke .env)
├── .env             # ← Anda buat sendiri (JANGAN di-commit ke Git!)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Cara Menjalankan

### Langkah 1 — Install dependensi

Buka terminal di folder proyek ini, lalu jalankan:

```bash
pip install -r requirements.txt
```

### Langkah 2 — Buat file konfigurasi `.env`

```bash
# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Buka file `.env` dengan teks editor dan isi semua nilai yang diperlukan:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=987654321
COOKIE_AKAD_SESSION=eyJpdiI6Ii...
```

### Langkah 3 — Uji koneksi Telegram

Sebelum memulai monitoring, pastikan konfigurasi Telegram Anda benar:

```bash
python main.py --test
```

Jika berhasil, Anda akan menerima pesan konfirmasi di Telegram. ✅

### Langkah 4 — Mulai monitoring

```bash
python main.py
```

Untuk menghentikan: tekan **Ctrl+C**

---

## ⚙️ Opsi Command Line

| Perintah | Keterangan |
|---|---|
| `python main.py` | Jalankan monitoring normal |
| `python main.py --test` | Uji koneksi ke Telegram tanpa polling |
| `python main.py --debug` | Jalankan dengan log level DEBUG (lebih verbose) |

---

## 🍪 Cara Mendapatkan Cookie `akad_session`

Cookie ini dibutuhkan agar script bisa mengakses halaman absensi dengan identitas Anda.

1. Buka browser, login ke [akademik.polban.ac.id](https://akademik.polban.ac.id)
2. Tekan **F12** untuk membuka Developer Tools
3. Pilih tab **Application** (Chrome) atau **Storage** (Firefox)
4. Di panel kiri, klik **Cookies** → pilih `akademik.polban.ac.id`
5. Cari baris bernama `akad_session`
6. Salin nilai di kolom **Value**
7. Tempel ke file `.env` pada baris `COOKIE_AKAD_SESSION=`

> 💡 **Cookie kedaluwarsa?** Ulangi langkah di atas dan perbarui nilai `COOKIE_AKAD_SESSION` di file `.env`. Restart script setelah update.

---

## 🤖 Cara Membuat Telegram Bot

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot` dan ikuti instruksi
3. Salin **token** yang diberikan ke `TELEGRAM_BOT_TOKEN` di `.env`
4. Untuk mendapatkan **Chat ID** Anda:
   - Cari bot **@userinfobot** di Telegram
   - Kirim `/start` → bot akan balas dengan Chat ID Anda
5. Salin Chat ID ke `TELEGRAM_CHAT_ID` di `.env`

---

## 🔧 Menyesuaikan Scraper

Jika struktur HTML portal berubah atau tombol tidak terdeteksi dengan benar, edit file `scraper.py`:

1. Buka portal di browser, login dan buka halaman absensi
2. Klik kanan tombol absensi → **Inspect Element**
3. Perhatikan `class` pada elemen `<button>` atau `<a>`
4. Tambahkan class tersebut ke `ACTIVE_BUTTON_CLASSES` atau `INACTIVE_BUTTON_CLASSES` di `scraper.py`

Contoh: Jika tombol aktif menggunakan class `btn-biru`, tambahkan:
```python
ACTIVE_BUTTON_CLASSES = {
    "btn-primary",
    "btn-success",
    "btn-biru",   # ← tambahkan di sini
}
```

---

## 📊 Contoh Output Log

```
2026-05-24 08:00:00 | INFO     | monitor | --- Poll #1 | 08:00:00 ---
2026-05-24 08:00:01 | INFO     | scraper | AbsenScraper: Ditemukan 3 jadwal absensi.
2026-05-24 08:00:01 | INFO     | monitor |   🔴 Matematika Teknik              | Aktif: False | Tombol: 'Belum Dibuka'
2026-05-24 08:00:01 | INFO     | monitor |   🟢 Pemrograman Web                | Aktif: True  | Tombol: 'Absen'
2026-05-24 08:00:01 | INFO     | monitor |   📣 Mengirim notifikasi untuk: Pemrograman Web
2026-05-24 08:00:02 | INFO     | notifier| TelegramNotifier: Pesan berhasil dikirim ke chat_id=987654321
2026-05-24 08:00:02 | INFO     | monitor |   🔴 Basis Data                     | Aktif: False | Tombol: 'Belum Dibuka'
2026-05-24 08:00:02 | INFO     | monitor | Menunggu 60 detik sebelum poll berikutnya...
```

---

## 📦 Dependensi

| Package | Versi | Kegunaan |
|---|---|---|
| `requests` | ≥2.31 | HTTP client untuk mengambil halaman web dan Telegram API |
| `beautifulsoup4` | ≥4.12 | Parser HTML untuk mendeteksi status tombol |
| `python-dotenv` | ≥1.0 | Membaca konfigurasi dari file `.env` |
| `lxml` | ≥5.0 | Parser HTML yang lebih cepat (backend untuk BeautifulSoup) |

---

## ❓ Troubleshooting

| Masalah | Solusi |
|---|---|
| `Sesi kedaluwarsa! Diarahkan ke halaman login` | Perbarui `COOKIE_AKAD_SESSION` di `.env` |
| `Token tidak valid` | Periksa `TELEGRAM_BOT_TOKEN` di `.env` |
| `Tidak ada jadwal absensi yang ditemukan` | Periksa dan sesuaikan selector di `scraper.py` |
| `Connection error` | Periksa koneksi internet, server mungkin down |
| Notifikasi terkirim berulang kali | Tidak akan terjadi — state tracker mencegah spam |
