# Smart-Retail Web

Aplikasi kasir toko kelontong berbahasa Indonesia, dibangun dengan Flask dan SQLite. Database lokalnya adalah `smart_retail.db`, sehingga tidak perlu memasang atau menjalankan server MySQL.

## Menjalankan aplikasi

1. Buka folder proyek ini di VS Code.
2. Buka terminal VS Code (`Ctrl` + `` ` ``), lalu pasang dependensi satu kali:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Jalankan aplikasi:

   ```powershell
   python app.py
   ```

4. Buka `http://127.0.0.1:5000` di browser.

Database dibuat otomatis sebagai `smart_retail.db` di folder proyek saat aplikasi pertama dijalankan.

## Membuka dan mengatur database di VS Code

Pasang ekstensi **SQLite Viewer** atau **SQLite** dari marketplace VS Code. Setelah itu, klik file `smart_retail.db` pada Explorer VS Code untuk melihat tabel `users`, `produk`, `transaksi`, dan `detail_transaksi`.

Database memakai mode **WAL**, sehingga VS Code dapat membaca database ketika aplikasi berjalan. Untuk mengubah atau menghapus data langsung dari editor database, tunggu operasi aplikasi yang sedang berjalan selesai lalu jalankan perintah SQL sekali lagi. SQLite tetap hanya mengizinkan satu penulis pada waktu yang sama.

Produk yang sudah terhubung ke riwayat transaksi tidak boleh dihapus karena akan merusak isi struk. Ubah stok menjadi `0` bila produk tidak lagi dijual. Sebelum mengedit struktur tabel atau menghapus banyak data, tutup aplikasi dan buat salinan `smart_retail.db` sebagai cadangan. Untuk mengganti lokasi file database, set variabel lingkungan `SQLITE_DB_PATH` sebelum menjalankan aplikasi.

## Fitur

- Login Admin dan Kasir dengan kata sandi yang di-hash
- Dasbor pendapatan, transaksi, produk, dan stok menipis
- Manajemen produk: tambah, cari, ubah, hapus (Admin)
- Point of Sale: keranjang, validasi stok, pembayaran, dan kembalian
- Riwayat transaksi, detail struk, dan laporan produk terlaris
- Antarmuka responsif tanpa animasi navigasi yang mengganggu

## Akun awal

| Peran | Username | Kata sandi |
| --- | --- | --- |
| Admin | `admin` | `admin123` |
| Kasir | `kasir` | `kasir123` |

## Struktur proyek

```text
app.py                 # Flask, SQLite, otorisasi, dan transaksi
smart_retail.db        # Database lokal yang dapat dibuka dari VS Code
templates/             # Halaman HTML berbahasa Indonesia
static/style.css       # Sistem desain responsif
static/app.js          # Perilaku antarmuka tanpa transisi halaman
requirements.txt       # Dependensi Python
```
