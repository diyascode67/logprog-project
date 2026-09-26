"""Aplikasi web Smart-Retail: Flask + SQLite lokal, seluruh antarmuka berbahasa Indonesia."""

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "ganti-kunci-rahasia-sebelum-produksi")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600  # cache static 1 jam


@app.after_request
def add_cache_headers(response):
    """Tambah cache-control untuk static files agar browser tidak re-download tiap kunjungan."""
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response

DEFAULT_DB_FILE = Path(__file__).with_name("smart_retail.db")
# Lokasi dapat diganti saat diperlukan, tetapi secara bawaan file .db selalu
# berada di folder proyek sehingga mudah dibuka dari VS Code.
DB_FILE = Path(os.getenv("SQLITE_DB_PATH", DEFAULT_DB_FILE))
Error = sqlite3.Error


class SQLiteCursor:
    """Adapter kecil agar query aplikasi memakai parameter aman SQLite."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=()):
        self._cursor.execute(query.replace("%s", "?"), params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


class SQLiteConnection:
    def __init__(self):
        self._conn = sqlite3.connect(DB_FILE, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 10000")

    def cursor(self, dictionary=False):
        return SQLiteCursor(self._conn.cursor())

    def start_transaction(self):
        self._conn.execute("BEGIN")

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def koneksi_db(pilih_database=True):
    """Membuka smart_retail.db di folder proyek (bisa dibuka dari VS Code)."""
    return SQLiteConnection()


def format_rupiah(nilai):
    return f"Rp{int(nilai or 0):,}".replace(",", ".")


@app.template_filter("rupiah")
def filter_rupiah(nilai):
    return format_rupiah(nilai)


@app.template_filter("tanggal_indonesia")
def filter_tanggal_indonesia(nilai, format_waktu="%d %b %Y, %H:%M"):
    """Menampilkan tanggal SQLite yang tersimpan sebagai teks atau datetime."""
    if isinstance(nilai, datetime):
        return nilai.strftime(format_waktu)
    try:
        return datetime.fromisoformat(str(nilai)).strftime(format_waktu)
    except (TypeError, ValueError):
        return str(nilai or "-")


def initialize_database():
    """Membuat atau memigrasikan smart_retail.db tanpa menghapus data lama."""
    try:
        conn = koneksi_db()
        cursor = conn.cursor()
        # WAL memungkinkan VS Code membaca database ketika aplikasi berjalan.
        # busy_timeout memberi waktu pada penulis lain untuk menyelesaikan transaksi.
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Admin', 'Kasir')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS produk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_produk TEXT NOT NULL,
                kategori TEXT NOT NULL DEFAULT 'Lainnya',
                harga_modal INTEGER NOT NULL CHECK(harga_modal >= 0),
                harga_jual INTEGER NOT NULL CHECK(harga_jual >= 0),
                stok INTEGER NOT NULL DEFAULT 0 CHECK(stok >= 0)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                total_bayar INTEGER NOT NULL,
                uang_bayar INTEGER NOT NULL DEFAULT 0,
                kembalian INTEGER NOT NULL DEFAULT 0,
                id_kasir INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (id_kasir) REFERENCES users(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS detail_transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaksi INTEGER NOT NULL,
                id_produk INTEGER NOT NULL,
                jumlah INTEGER NOT NULL,
                subtotal INTEGER NOT NULL,
                FOREIGN KEY (id_transaksi) REFERENCES transaksi(id),
                FOREIGN KEY (id_produk) REFERENCES produk(id)
            )
            """
        )

        # Mendukung file SQLite CLI lama yang belum punya kolom versi web.
        for table, column, definition in [
            ("produk", "kategori", "TEXT NOT NULL DEFAULT 'Lainnya'"),
            ("transaksi", "uang_bayar", "INTEGER NOT NULL DEFAULT 0"),
            ("transaksi", "kembalian", "INTEGER NOT NULL DEFAULT 0"),
            ("transaksi", "id_kasir", "INTEGER NOT NULL DEFAULT 1"),
        ]:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row["name"] for row in cursor.fetchall()}
            if column not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        # Indeks ini menjaga halaman riwayat dan grafik tetap cepat saat data bertambah.
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transaksi_tanggal ON transaksi(tanggal)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_detail_transaksi_transaksi ON detail_transaksi(id_transaksi)")

        # Password akun awal di-hash, termasuk saat memigrasikan database CLI lama
        # yang masih menyimpan kata sandi sebagai teks biasa.
        for username, password, role in [("admin", "admin123", "Admin"), ("kasir", "kasir123", "Kasir")]:
            cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            pengguna = cursor.fetchone()
            if not pengguna:
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, generate_password_hash(password), role),
                )
            elif not str(pengguna["password"]).startswith(("scrypt:", "pbkdf2:")):
                cursor.execute(
                    "UPDATE users SET password = %s WHERE id = %s",
                    (generate_password_hash(password), pengguna["id"]),
                )

        # Menambahkan produk contoh awal jika tabel produk masih kosong
        cursor.execute("SELECT COUNT(*) AS total FROM produk")
        if cursor.fetchone()["total"] == 0:
            sample_produk = [
                ("Minyak Goreng Sania 2L", "Sembako", 32000, 38000, 24),
                ("Beras Pandan Wangi 5kg", "Sembako", 68000, 78000, 16),
                ("Gula Pasir Gulaku 1kg", "Sembako", 14500, 17500, 30),
                ("Telur Ayam Negeri 1kg", "Sembako", 26000, 30000, 12),
                ("Kopi Kapal Api Special 165g", "Minuman", 13000, 16000, 8),
                ("Susu UHT Ultra Milk 1L", "Minuman", 17500, 21000, 5),
                ("Teh Celup Sosro 30s", "Minuman", 6500, 8500, 25),
                ("Indomie Goreng Spesial", "Makanan Instan", 2800, 3500, 100),
            ]
            for nama, kat, modal, jual, stok in sample_produk:
                cursor.execute(
                    "INSERT INTO produk (nama_produk, kategori, harga_modal, harga_jual, stok) VALUES (%s, %s, %s, %s, %s)",
                    (nama, kat, modal, jual, stok),
                )

        conn.commit()
        cursor.close()
        conn.close()
        return None
    except Error as error:
        return str(error)


def buat_path_grafik(nilai, width=560, height=225, top=22, bottom=24):
    """Membuat garis SVG dari nilai penjualan tanpa library grafik tambahan."""
    maksimum = max(nilai) if any(nilai) else 1
    jarak = width / max(len(nilai) - 1, 1)
    titik = []
    for index, nilai_item in enumerate(nilai):
        y = top + (height - top - bottom) * (1 - nilai_item / maksimum)
        titik.append(f"{index * jarak + 20:.1f},{y:.1f}")
    return "M " + " L ".join(titik)


def data_grafik_penjualan(cursor):
    """Mengambil total penjualan tujuh hari terakhir untuk grafik dasbor."""
    hari_ini = datetime.now().date()
    hari = [hari_ini - timedelta(days=jarak) for jarak in range(6, -1, -1)]
    cursor.execute(
        """
        SELECT DATE(tanggal) AS hari, COALESCE(SUM(total_bayar), 0) AS total
        FROM transaksi
        WHERE DATE(tanggal) BETWEEN %s AND %s
        GROUP BY DATE(tanggal)
        """,
        (hari[0].isoformat(), hari[-1].isoformat()),
    )
    total_per_hari = {baris["hari"]: baris["total"] for baris in cursor.fetchall()}
    nilai = [int(total_per_hari.get(tanggal.isoformat(), 0)) for tanggal in hari]
    label = [
        {"teks": tanggal.strftime("%d/%m"), "x": f"{20 + index * (560 / 6):.1f}"}
        for index, tanggal in enumerate(hari)
    ]
    garis = buat_path_grafik(nilai)
    garis_dasar = 201
    area = f"{garis} L 580,{garis_dasar} L 20,{garis_dasar} Z"
    return {
        "nilai": nilai,
        "label": label,
        "garis": garis,
        "area": area,
        "total": sum(nilai),
        "maksimum": max(nilai) if any(nilai) else 0,
        "ada_penjualan": any(nilai),
    }


def login_required(*roles):
    """Membatasi halaman berdasarkan sesi login dan peran pengguna."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Silakan masuk terlebih dahulu.", "error")
                return redirect(url_for("login"))
            if roles and session.get("role") not in roles:
                flash("Anda tidak memiliki akses ke halaman tersebut.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


def ambil_angka(nilai, nama, minimum=0):
    try:
        angka = int(nilai)
    except (TypeError, ValueError):
        raise ValueError(f"{nama} harus berupa angka bulat.")
    if angka < minimum:
        raise ValueError(f"{nama} tidak boleh kurang dari {minimum}.")
    return angka


@app.context_processor
def inject_globals():
    return {"user": {"nama": session.get("username"), "role": session.get("role")}}


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            conn = koneksi_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
        except Error as error:
            flash(f"Database SQLite belum dapat dibuka: {error}", "error")
            return render_template("login.html")

        if not user or not check_password_hash(user["password"], password):
            flash("Username atau kata sandi tidak sesuai.", "error")
        else:
            session.clear()
            session.update(user_id=user["id"], username=user["username"], role=user["role"], cart=[])
            return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("Anda telah keluar dari sistem.", "success")
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required("Admin", "Kasir")
def dashboard():
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COALESCE(SUM(total_bayar), 0) AS total FROM transaksi WHERE DATE(tanggal) = DATE('now', 'localtime')")
    pendapatan = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM transaksi WHERE DATE(tanggal) = DATE('now', 'localtime')")
    jumlah_transaksi = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM produk")
    jumlah_produk = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM produk WHERE stok < 10")
    stok_menipis = cursor.fetchone()["total"]
    grafik_penjualan = data_grafik_penjualan(cursor)
    cursor.execute(
        """
        SELECT t.id, t.tanggal, t.total_bayar, u.username
        FROM transaksi t JOIN users u ON u.id = t.id_kasir
        ORDER BY t.id DESC LIMIT 5
        """
    )
    transaksi_terbaru = cursor.fetchall()
    cursor.execute("SELECT nama_produk, stok FROM produk WHERE stok < 10 ORDER BY stok ASC, nama_produk LIMIT 5")
    produk_menipis = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        "dashboard.html", pendapatan=pendapatan, jumlah_transaksi=jumlah_transaksi,
        jumlah_produk=jumlah_produk, stok_menipis=stok_menipis,
        transaksi_terbaru=transaksi_terbaru, produk_menipis=produk_menipis,
        grafik_penjualan=grafik_penjualan,
    )


@app.route("/produk", methods=["GET", "POST"])
@login_required("Admin", "Kasir")
def produk():
    if request.method == "POST":
        if session["role"] != "Admin":
            flash("Hanya Admin yang dapat menambah produk.", "error")
            return redirect(url_for("produk"))
        try:
            nama = request.form.get("nama_produk", "").strip()
            kategori = request.form.get("kategori", "Lainnya").strip() or "Lainnya"
            if not nama:
                raise ValueError("Nama produk wajib diisi.")
            modal = ambil_angka(request.form.get("harga_modal"), "Harga modal")
            jual = ambil_angka(request.form.get("harga_jual"), "Harga jual")
            stok = ambil_angka(request.form.get("stok"), "Stok")
            conn = koneksi_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO produk (nama_produk, kategori, harga_modal, harga_jual, stok) VALUES (%s, %s, %s, %s, %s)",
                (nama, kategori, modal, jual, stok),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Produk berhasil ditambahkan.", "success")
        except (ValueError, Error) as error:
            flash(str(error), "error")
        return redirect(url_for("produk"))

    kata_kunci = request.args.get("q", "").strip()
    halaman = max(request.args.get("page", 1, type=int), 1)
    ukuran_halaman = 10
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    kondisi = ""
    params = ()
    if kata_kunci:
        kondisi = " WHERE nama_produk LIKE %s OR CAST(id AS TEXT) LIKE %s"
        params = (f"%{kata_kunci}%", f"%{kata_kunci}%")

    cursor.execute(f"SELECT COUNT(*) AS total FROM produk{kondisi}", params)
    total_hasil = cursor.fetchone()["total"]
    total_halaman = max((total_hasil + ukuran_halaman - 1) // ukuran_halaman, 1)
    halaman = min(halaman, total_halaman)
    offset = (halaman - 1) * ukuran_halaman

    query = f"SELECT * FROM produk{kondisi} ORDER BY id DESC LIMIT %s OFFSET %s"
    cursor.execute(query, params + (ukuran_halaman, offset))
    daftar_produk = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS total FROM produk")
    jumlah_produk = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM produk WHERE stok < 10")
    stok_menipis = cursor.fetchone()["total"]
    cursor.close()
    conn.close()
    nomor_halaman = list(range(1, total_halaman + 1))
    if total_halaman > 7:
        sekitar_halaman = {1, 2, total_halaman - 1, total_halaman, halaman - 1, halaman, halaman + 1}
        nomor_halaman = []
        sebelumnya = None
        for nomor in sorted(n for n in sekitar_halaman if 1 <= n <= total_halaman):
            if sebelumnya is not None and nomor - sebelumnya > 1:
                nomor_halaman.append(None)
            nomor_halaman.append(nomor)
            sebelumnya = nomor

    return render_template(
        "produk.html", produk=daftar_produk, q=kata_kunci,
        jumlah_produk=jumlah_produk, stok_menipis=stok_menipis,
        halaman=halaman, total_halaman=total_halaman,
        total_hasil=total_hasil, nomor_halaman=nomor_halaman,
    )


@app.post("/produk/<int:id_produk>/ubah")
@login_required("Admin")
def ubah_produk(id_produk):
    try:
        nama = request.form.get("nama_produk", "").strip()
        kategori = request.form.get("kategori", "Lainnya").strip() or "Lainnya"
        if not nama:
            raise ValueError("Nama produk wajib diisi.")
        jual = ambil_angka(request.form.get("harga_jual"), "Harga jual")
        stok = ambil_angka(request.form.get("stok"), "Stok")
        conn = koneksi_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE produk SET nama_produk=%s, kategori=%s, harga_jual=%s, stok=%s WHERE id=%s",
            (nama, kategori, jual, stok, id_produk),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Produk berhasil diperbarui.", "success")
    except (ValueError, Error) as error:
        flash(str(error), "error")
    return redirect(url_for("produk"))


@app.post("/produk/<int:id_produk>/hapus")
@login_required("Admin")
def hapus_produk(id_produk):
    conn = None
    cursor = None
    try:
        conn = koneksi_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM produk WHERE id = %s", (id_produk,))
        conn.commit()
        flash("Produk berhasil dihapus.", "success")
    except sqlite3.IntegrityError:
        flash("Produk yang sudah tercatat dalam transaksi tidak dapat dihapus.", "error")
    except sqlite3.OperationalError as error:
        if "locked" in str(error).lower():
            flash("Database sedang dipakai proses lain. Coba lagi beberapa saat lagi.", "error")
        else:
            flash(f"Produk tidak dapat dihapus: {error}", "error")
    except Error as error:
        flash(f"Produk tidak dapat dihapus: {error}", "error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect(url_for("produk"))


def keranjang():
    return session.get("cart", [])


def payload_keranjang():
    """Payload JSON kecil untuk memperbarui UI POS tanpa memuat ulang halaman."""
    items = keranjang()
    return {
        "items": items,
        "jumlah_item": sum(item["jumlah"] for item in items),
        "total": sum(item["subtotal"] for item in items),
    }


def ubah_jumlah_keranjang(id_produk, jumlah_baru):
    """Menetapkan jumlah satu produk di keranjang setelah memeriksa stok terbaru."""
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM produk WHERE id = %s", (id_produk,))
        produk = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if not produk:
        raise ValueError("Produk tidak ditemukan.")
    if jumlah_baru > produk["stok"]:
        raise ValueError(f"Stok {produk['nama_produk']} tidak mencukupi.")

    cart = keranjang()
    item = next((baris for baris in cart if baris["id_produk"] == id_produk), None)
    if jumlah_baru <= 0:
        cart = [baris for baris in cart if baris["id_produk"] != id_produk]
    elif item:
        item["jumlah"] = jumlah_baru
        item["subtotal"] = item["harga"] * jumlah_baru
    else:
        cart.append({
            "id_produk": id_produk,
            "nama": produk["nama_produk"],
            "harga": produk["harga_jual"],
            "jumlah": jumlah_baru,
            "subtotal": produk["harga_jual"] * jumlah_baru,
        })
    session["cart"] = cart
    return payload_keranjang()


@app.get("/pos")
@login_required("Admin", "Kasir")
def pos():
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM produk WHERE stok > 0 ORDER BY nama_produk")
    daftar_produk = cursor.fetchall()
    cursor.close()
    conn.close()
    cart = keranjang()
    total = sum(item["subtotal"] for item in cart)
    return render_template("pos.html", produk=daftar_produk, cart=cart, total=total)


@app.get("/api/pos/keranjang")
@login_required("Admin", "Kasir")
def api_keranjang():
    return jsonify(payload_keranjang())


@app.post("/api/pos/ubah-jumlah")
@login_required("Admin", "Kasir")
def api_ubah_jumlah_keranjang():
    data = request.get_json(silent=True) or {}
    try:
        id_produk = ambil_angka(data.get("id_produk"), "Produk", 1)
        jumlah = ambil_angka(data.get("jumlah"), "Jumlah", 0)
        return jsonify(ubah_jumlah_keranjang(id_produk, jumlah))
    except (ValueError, Error) as error:
        return jsonify(error=str(error)), 400


@app.post("/api/pos/selesai")
@login_required("Admin", "Kasir")
def api_selesai_transaksi():
    data = request.get_json(silent=True) or {}
    cart = keranjang()
    if not cart:
        return jsonify(error="Keranjang belanja masih kosong."), 400
    conn = None
    cursor = None
    try:
        uang_bayar = ambil_angka(data.get("uang_bayar"), "Uang bayar")
        total = sum(item["subtotal"] for item in cart)
        if uang_bayar < total:
            raise ValueError(f"Uang bayar kurang {format_rupiah(total - uang_bayar)}.")
        conn = koneksi_db()
        cursor = conn.cursor(dictionary=True)
        conn.start_transaction()
        for item in cart:
            cursor.execute(
                "UPDATE produk SET stok = stok - %s WHERE id = %s AND stok >= %s",
                (item["jumlah"], item["id_produk"], item["jumlah"]),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Stok {item['nama']} berubah atau tidak mencukupi.")
        kembalian = uang_bayar - total
        cursor.execute(
            "INSERT INTO transaksi (tanggal, total_bayar, uang_bayar, kembalian, id_kasir) VALUES (%s, %s, %s, %s, %s)",
            (datetime.now(), total, uang_bayar, kembalian, session["user_id"]),
        )
        id_transaksi = cursor.lastrowid
        for item in cart:
            cursor.execute(
                "INSERT INTO detail_transaksi (id_transaksi, id_produk, jumlah, subtotal) VALUES (%s, %s, %s, %s)",
                (id_transaksi, item["id_produk"], item["jumlah"], item["subtotal"]),
            )
        conn.commit()
        session["cart"] = []
        return jsonify({
            "id_transaksi": id_transaksi,
            "total": total,
            "uang_bayar": uang_bayar,
            "kembalian": kembalian,
            "receipt_url": url_for("detail_transaksi", id_transaksi=id_transaksi),
        })
    except (ValueError, Error) as error:
        if conn:
            conn.rollback()
        return jsonify(error=str(error)), 400
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.get("/transaksi")
@login_required("Admin")
def transaksi():
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT t.*, u.username FROM transaksi t JOIN users u ON u.id = t.id_kasir ORDER BY t.id DESC")
    daftar_transaksi = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("transaksi.html", transaksi=daftar_transaksi)


@app.get("/transaksi/<int:id_transaksi>")
@login_required("Admin", "Kasir")
def detail_transaksi(id_transaksi):
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT t.*, u.username FROM transaksi t JOIN users u ON u.id = t.id_kasir WHERE t.id = %s", (id_transaksi,))
    transaksi_data = cursor.fetchone()
    if not transaksi_data:
        cursor.close()
        conn.close()
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))
    cursor.execute("SELECT d.*, p.nama_produk FROM detail_transaksi d JOIN produk p ON p.id = d.id_produk WHERE d.id_transaksi = %s", (id_transaksi,))
    detail = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("detail_transaksi.html", transaksi=transaksi_data, detail=detail)


@app.post("/transaksi/<int:id_transaksi>/hapus")
@login_required("Admin")
def hapus_transaksi(id_transaksi):
    conn = None
    cursor = None
    try:
        conn = koneksi_db()
        cursor = conn.cursor(dictionary=True)

        # 1. Ambil detail produk yang dibeli untuk mengembalikan stok
        cursor.execute("SELECT id_produk, jumlah FROM detail_transaksi WHERE id_transaksi = %s", (id_transaksi,))
        items = cursor.fetchall()

        if not items:
            cursor.execute("SELECT id FROM transaksi WHERE id = %s", (id_transaksi,))
            if not cursor.fetchone():
                flash("Transaksi tidak ditemukan.", "error")
                return redirect(url_for("transaksi"))

        # 2. Kembalikan stok produk ke inventaris toko
        for item in items:
            cursor.execute("UPDATE produk SET stok = stok + %s WHERE id = %s", (item["jumlah"], item["id_produk"]))

        # 3. Hapus data detail transaksi & transaksi
        cursor.execute("DELETE FROM detail_transaksi WHERE id_transaksi = %s", (id_transaksi,))
        cursor.execute("DELETE FROM transaksi WHERE id = %s", (id_transaksi,))

        conn.commit()
        flash(f"Transaksi #{id_transaksi} berhasil dibatalkan dan stok produk telah dikembalikan ke inventaris.", "success")
    except sqlite3.OperationalError as error:
        if conn:
            conn.rollback()
        if "locked" in str(error).lower():
            flash("Database sedang dipakai proses lain. Coba lagi beberapa saat lagi.", "error")
        else:
            flash(f"Gagal membatalkan transaksi: {error}", "error")
    except Exception as error:
        if conn:
            conn.rollback()
        flash(f"Gagal membatalkan transaksi: {error}", "error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect(url_for("transaksi"))


@app.get("/laporan")
@login_required("Admin")
def laporan():
    conn = koneksi_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_transaksi, COALESCE(SUM(total_bayar), 0) AS total_pendapatan FROM transaksi")
    ringkasan = cursor.fetchone()
    cursor.execute("""SELECT p.nama_produk, SUM(d.jumlah) AS total_terjual FROM detail_transaksi d JOIN produk p ON p.id=d.id_produk GROUP BY p.id, p.nama_produk ORDER BY total_terjual DESC LIMIT 5""")
    terlaris = cursor.fetchall()
    cursor.execute("SELECT nama_produk, stok FROM produk WHERE stok < 10 ORDER BY stok ASC")
    stok_menipis = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("laporan.html", ringkasan=ringkasan, terlaris=terlaris, stok_menipis=stok_menipis)


if __name__ == "__main__":
    error_db = initialize_database()
    if error_db:
        raise SystemExit(f"Gagal menyiapkan database SQLite: {error_db}")
    # Reloader debug menjalankan app.py dua kali dan dapat mengunci SQLite di Windows.
    print(f"Database aktif: {DB_FILE.resolve()}")
    print("Buka aplikasi di http://127.0.0.1:5000")
    app.run(debug=False)
