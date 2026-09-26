"""Smart-Retail: aplikasi kasir toko kelontong berbasis terminal dan SQLite."""

import sqlite3
from datetime import datetime
from pathlib import Path


DB_NAME = "smart_retail.db"
RECEIPT_DIR = Path("struk")


def koneksi_db():
    """Membuat koneksi SQLite dan memastikan foreign key SQLite aktif."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def buat_database():
    """Membuat seluruh tabel dan akun awal bila database belum pernah dipakai."""
    with koneksi_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Admin', 'Kasir'))
            );

            CREATE TABLE IF NOT EXISTS Produk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_produk TEXT NOT NULL,
                harga_modal INTEGER NOT NULL CHECK(harga_modal >= 0),
                harga_jual INTEGER NOT NULL CHECK(harga_jual >= 0),
                stok INTEGER NOT NULL CHECK(stok >= 0)
            );

            CREATE TABLE IF NOT EXISTS Transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                total_bayar INTEGER NOT NULL CHECK(total_bayar >= 0)
            );

            CREATE TABLE IF NOT EXISTS Detail_Transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaksi INTEGER NOT NULL,
                id_produk INTEGER NOT NULL,
                jumlah INTEGER NOT NULL CHECK(jumlah > 0),
                subtotal INTEGER NOT NULL CHECK(subtotal >= 0),
                FOREIGN KEY (id_transaksi) REFERENCES Transaksi(id),
                FOREIGN KEY (id_produk) REFERENCES Produk(id)
            );
            """
        )
        # INSERT OR IGNORE membuat akun awal tanpa mengganti akun yang sudah ada.
        conn.executemany(
            """
            INSERT OR IGNORE INTO Users (username, password, role)
            VALUES (?, ?, ?)
            """,
            [("admin", "admin123", "Admin"), ("kasir", "kasir123", "Kasir")],
        )


def rupiah(nilai):
    """Mengubah angka menjadi tampilan uang Rupiah yang mudah dibaca."""
    return f"Rp{nilai:,.0f}".replace(",", ".")


def garis(judul=""):
    print("\n" + "=" * 72)
    if judul:
        print(judul.center(72))
        print("=" * 72)


def input_bilangan(pesan, minimum=0, boleh_kosong=False, nilai_lama=None):
    """Meminta bilangan bulat dan menghindari program berhenti saat input salah."""
    while True:
        nilai = input(pesan).strip()
        if boleh_kosong and nilai == "":
            return nilai_lama
        try:
            angka = int(nilai)
            if angka < minimum:
                print(f"ERROR: Nilai minimal adalah {minimum}.")
            else:
                return angka
        except ValueError:
            print("ERROR: Masukkan angka bulat yang valid.")


def tampilkan_tabel(headers, rows):
    """Menampilkan data sebagai tabel tanpa perlu memasang library tambahan."""
    data = [[str(item) for item in row] for row in rows]
    lebar = [len(str(header)) for header in headers]
    for row in data:
        for i, item in enumerate(row):
            lebar[i] = max(lebar[i], len(item))

    pembatas = "+" + "+".join("-" * (ukuran + 2) for ukuran in lebar) + "+"
    print(pembatas)
    print("|" + "|".join(f" {headers[i]:<{lebar[i]}} " for i in range(len(headers))) + "|")
    print(pembatas)
    for row in data:
        print("|" + "|".join(f" {row[i]:<{lebar[i]}} " for i in range(len(headers))) + "|")
    print(pembatas)


def ambil_produk(id_produk):
    with koneksi_db() as conn:
        return conn.execute("SELECT * FROM Produk WHERE id = ?", (id_produk,)).fetchone()


def lihat_produk():
    """Menampilkan seluruh produk yang tersimpan."""
    with koneksi_db() as conn:
        produk = conn.execute("SELECT * FROM Produk ORDER BY id").fetchall()

    garis("DAFTAR PRODUK")
    if not produk:
        print("Belum ada produk.")
        return
    tampilkan_tabel(
        ["ID", "Nama Produk", "Harga Modal", "Harga Jual", "Stok"],
        [(p["id"], p["nama_produk"], rupiah(p["harga_modal"]), rupiah(p["harga_jual"]), p["stok"]) for p in produk],
    )


def tambah_produk():
    garis("TAMBAH PRODUK")
    nama = input("Nama produk       : ").strip()
    if not nama:
        print("ERROR: Nama produk tidak boleh kosong.")
        return
    modal = input_bilangan("Harga modal       : ")
    jual = input_bilangan("Harga jual        : ")
    stok = input_bilangan("Stok awal         : ")
    with koneksi_db() as conn:
        conn.execute(
            "INSERT INTO Produk (nama_produk, harga_modal, harga_jual, stok) VALUES (?, ?, ?, ?)",
            (nama, modal, jual, stok),
        )
    print("Produk berhasil ditambahkan.")


def update_produk():
    lihat_produk()
    id_produk = input_bilangan("ID produk yang diubah: ", minimum=1)
    produk = ambil_produk(id_produk)
    if not produk:
        print("ERROR: Produk tidak ditemukan.")
        return

    print("Kosongkan input untuk mempertahankan nilai lama.")
    nama = input(f"Nama produk [{produk['nama_produk']}]: ").strip() or produk["nama_produk"]
    harga_jual = input_bilangan(
        f"Harga jual [{produk['harga_jual']}]: ", boleh_kosong=True, nilai_lama=produk["harga_jual"]
    )
    stok = input_bilangan(f"Stok [{produk['stok']}]: ", boleh_kosong=True, nilai_lama=produk["stok"])

    with koneksi_db() as conn:
        conn.execute(
            "UPDATE Produk SET nama_produk = ?, harga_jual = ?, stok = ? WHERE id = ?",
            (nama, harga_jual, stok, id_produk),
        )
    print("Produk berhasil diperbarui.")


def hapus_produk():
    lihat_produk()
    id_produk = input_bilangan("ID produk yang dihapus: ", minimum=1)
    produk = ambil_produk(id_produk)
    if not produk:
        print("ERROR: Produk tidak ditemukan.")
        return

    konfirmasi = input(f"Yakin (Y/T) menghapus produk '{produk['nama_produk']}'? ").strip().upper()
    if konfirmasi != "Y":
        print("Penghapusan dibatalkan.")
        return
    try:
        with koneksi_db() as conn:
            conn.execute("DELETE FROM Produk WHERE id = ?", (id_produk,))
        print("Produk berhasil dihapus.")
    except sqlite3.IntegrityError:
        print("ERROR: Produk sudah tercatat dalam transaksi dan tidak dapat dihapus.")


def cari_produk():
    garis("PENCARIAN PRODUK")
    print("1. Cari berdasarkan nama")
    print("2. Cari berdasarkan ID")
    pilihan = input("Pilih metode pencarian: ").strip()
    with koneksi_db() as conn:
        if pilihan == "1":
            kata_kunci = input("Masukkan nama produk: ").strip()
            hasil = conn.execute(
                "SELECT * FROM Produk WHERE nama_produk LIKE ? COLLATE NOCASE ORDER BY nama_produk",
                (f"%{kata_kunci}%",),
            ).fetchall()
        elif pilihan == "2":
            id_produk = input_bilangan("Masukkan ID produk: ", minimum=1)
            hasil = conn.execute("SELECT * FROM Produk WHERE id = ?", (id_produk,)).fetchall()
        else:
            print("Pilihan tidak valid.")
            return

    if not hasil:
        print("Produk tidak ditemukan.")
        return
    tampilkan_tabel(
        ["ID", "Nama Produk", "Harga Jual", "Stok"],
        [(p["id"], p["nama_produk"], rupiah(p["harga_jual"]), p["stok"]) for p in hasil],
    )


def cetak_struk(id_transaksi, tanggal, keranjang, total, bayar, kembalian):
    """Menyimpan salinan struk transaksi ke folder struk dalam format TXT."""
    RECEIPT_DIR.mkdir(exist_ok=True)
    nama_file = RECEIPT_DIR / f"struk_{id_transaksi}_{datetime.now():%Y%m%d_%H%M%S}.txt"
    baris = [
        "=" * 40,
        "        SMART-RETAIL TOKO KELONTONG",
        "=" * 40,
        f"No. Transaksi : {id_transaksi}",
        f"Tanggal       : {tanggal}",
        "-" * 40,
    ]
    for item in keranjang:
        baris.extend(
            [
                item["nama"],
                f"  {item['jumlah']} x {rupiah(item['harga'])} = {rupiah(item['subtotal'])}",
            ]
        )
    baris.extend(
        [
            "-" * 40,
            f"TOTAL       : {rupiah(total)}",
            f"UANG BAYAR  : {rupiah(bayar)}",
            f"KEMBALIAN   : {rupiah(kembalian)}",
            "=" * 40,
            "Terima kasih sudah berbelanja!",
        ]
    )
    nama_file.write_text("\n".join(baris), encoding="utf-8")
    return nama_file


def transaksi_penjualan(nama_kasir):
    """Membuat keranjang, memvalidasi stok, lalu menyimpan transaksi secara atomik."""
    garis(f"TRANSAKSI PENJUALAN - Kasir: {nama_kasir}")
    lihat_produk()
    keranjang = {}

    while True:
        id_produk = input_bilangan("\nMasukkan ID barang: ", minimum=1)
        produk = ambil_produk(id_produk)
        if not produk:
            print("ERROR: Produk tidak ditemukan.")
            continue
        jumlah = input_bilangan(f"Jumlah beli {produk['nama_produk']}: ", minimum=1)
        jumlah_di_keranjang = keranjang.get(id_produk, {}).get("jumlah", 0)
        if jumlah + jumlah_di_keranjang > produk["stok"]:
            print("ERROR: Stok tidak mencukupi")
            continue

        if id_produk in keranjang:
            keranjang[id_produk]["jumlah"] += jumlah
            keranjang[id_produk]["subtotal"] = keranjang[id_produk]["jumlah"] * produk["harga_jual"]
        else:
            keranjang[id_produk] = {
                "id_produk": id_produk,
                "nama": produk["nama_produk"],
                "harga": produk["harga_jual"],
                "jumlah": jumlah,
                "subtotal": jumlah * produk["harga_jual"],
            }
        print(f"Ditambahkan: {produk['nama_produk']} ({rupiah(jumlah * produk['harga_jual'])})")
        if input("Tambah barang lain? (Y/T): ").strip().upper() != "Y":
            break

    item_keranjang = list(keranjang.values())
    total = sum(item["subtotal"] for item in item_keranjang)
    garis("RINGKASAN BELANJA")
    tampilkan_tabel(
        ["Produk", "Harga", "Jumlah", "Subtotal"],
        [(i["nama"], rupiah(i["harga"]), i["jumlah"], rupiah(i["subtotal"])) for i in item_keranjang],
    )
    print(f"Total bayar: {rupiah(total)}")

    while True:
        uang_bayar = input_bilangan("Uang bayar pelanggan: ")
        if uang_bayar < total:
            print(f"ERROR: Uang bayar kurang {rupiah(total - uang_bayar)}.")
        else:
            break
    kembalian = uang_bayar - total
    tanggal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Satu transaksi database menjaga stok dan riwayat selalu konsisten.
    try:
        with koneksi_db() as conn:
            cursor = conn.execute(
                "INSERT INTO Transaksi (tanggal, total_bayar) VALUES (?, ?)",
                (tanggal, total),
            )
            id_transaksi = cursor.lastrowid
            for item in item_keranjang:
                hasil = conn.execute(
                    "UPDATE Produk SET stok = stok - ? WHERE id = ? AND stok >= ?",
                    (item["jumlah"], item["id_produk"], item["jumlah"]),
                )
                if hasil.rowcount != 1:
                    raise ValueError("Stok berubah atau tidak mencukupi saat transaksi disimpan.")
                conn.execute(
                    """
                    INSERT INTO Detail_Transaksi (id_transaksi, id_produk, jumlah, subtotal)
                    VALUES (?, ?, ?, ?)
                    """,
                    (id_transaksi, item["id_produk"], item["jumlah"], item["subtotal"]),
                )
    except (sqlite3.Error, ValueError) as error:
        print(f"ERROR: Transaksi gagal disimpan. {error}")
        return

    garis("STRUK BELANJA")
    print(f"No. Transaksi : {id_transaksi}")
    print(f"Tanggal       : {tanggal}")
    for item in item_keranjang:
        print(f"{item['nama']} - {item['jumlah']} x {rupiah(item['harga'])} = {rupiah(item['subtotal'])}")
    print(f"TOTAL         : {rupiah(total)}")
    print(f"UANG BAYAR    : {rupiah(uang_bayar)}")
    print(f"KEMBALIAN     : {rupiah(kembalian)}")
    file_struk = cetak_struk(id_transaksi, tanggal, item_keranjang, total, uang_bayar, kembalian)
    print(f"Struk TXT berhasil disimpan: {file_struk}")


def lihat_transaksi():
    """Admin dapat melihat transaksi beserta item yang dibeli."""
    with koneksi_db() as conn:
        transaksi = conn.execute("SELECT * FROM Transaksi ORDER BY id DESC").fetchall()
    garis("RIWAYAT TRANSAKSI")
    if not transaksi:
        print("Belum ada transaksi.")
        return
    tampilkan_tabel(
        ["ID", "Tanggal", "Total Bayar"],
        [(t["id"], t["tanggal"], rupiah(t["total_bayar"])) for t in transaksi],
    )

    if input("Lihat detail transaksi? (Y/T): ").strip().upper() == "Y":
        id_transaksi = input_bilangan("ID transaksi: ", minimum=1)
        with koneksi_db() as conn:
            detail = conn.execute(
                """
                SELECT p.nama_produk, d.jumlah, d.subtotal
                FROM Detail_Transaksi d
                JOIN Produk p ON p.id = d.id_produk
                WHERE d.id_transaksi = ?
                """,
                (id_transaksi,),
            ).fetchall()
        if detail:
            tampilkan_tabel(
                ["Produk", "Jumlah", "Subtotal"],
                [(d["nama_produk"], d["jumlah"], rupiah(d["subtotal"])) for d in detail],
            )
        else:
            print("Detail transaksi tidak ditemukan.")


def laporan_penjualan():
    """Mengambil ringkasan penjualan menggunakan query agregasi SQLite."""
    with koneksi_db() as conn:
        ringkasan = conn.execute(
            "SELECT COUNT(*) AS total_transaksi, COALESCE(SUM(total_bayar), 0) AS total_pendapatan FROM Transaksi"
        ).fetchone()
        terlaris = conn.execute(
            """
            SELECT p.nama_produk, SUM(d.jumlah) AS total_terjual
            FROM Detail_Transaksi d
            JOIN Produk p ON p.id = d.id_produk
            GROUP BY d.id_produk, p.nama_produk
            ORDER BY total_terjual DESC, p.nama_produk ASC
            LIMIT 1
            """
        ).fetchone()
        stok_menipis = conn.execute(
            "SELECT id, nama_produk, stok FROM Produk WHERE stok < 10 ORDER BY stok ASC, nama_produk ASC"
        ).fetchall()

    garis("LAPORAN PENJUALAN")
    print(f"Total transaksi : {ringkasan['total_transaksi']}")
    print(f"Total pendapatan: {rupiah(ringkasan['total_pendapatan'])}")
    if terlaris:
        print(f"Produk terlaris : {terlaris['nama_produk']} ({terlaris['total_terjual']} unit)")
    else:
        print("Produk terlaris : Belum ada data penjualan.")
    print("\nStok hampir habis (di bawah 10):")
    if stok_menipis:
        tampilkan_tabel(
            ["ID", "Nama Produk", "Stok"],
            [(p["id"], p["nama_produk"], p["stok"]) for p in stok_menipis],
        )
    else:
        print("Tidak ada produk dengan stok di bawah 10.")


def login():
    """Mengembalikan data pengguna jika username dan password benar."""
    garis("LOGIN SMART-RETAIL")
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    with koneksi_db() as conn:
        user = conn.execute(
            "SELECT username, role FROM Users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
    if not user:
        print("ERROR: Username atau password salah.")
    return user


def menu_admin(user):
    while True:
        garis(f"MENU ADMIN - {user['username']}")
        print("1. Tambah produk")
        print("2. Lihat produk")
        print("3. Update produk")
        print("4. Hapus produk")
        print("5. Cari produk")
        print("6. Lihat transaksi")
        print("7. Laporan penjualan")
        print("0. Logout")
        pilihan = input("Pilih menu: ").strip()
        if pilihan == "1":
            tambah_produk()
        elif pilihan == "2":
            lihat_produk()
        elif pilihan == "3":
            update_produk()
        elif pilihan == "4":
            hapus_produk()
        elif pilihan == "5":
            cari_produk()
        elif pilihan == "6":
            lihat_transaksi()
        elif pilihan == "7":
            laporan_penjualan()
        elif pilihan == "0":
            print("Logout berhasil.")
            break
        else:
            print("Pilihan menu tidak valid.")


def menu_kasir(user):
    while True:
        garis(f"MENU KASIR - {user['username']}")
        print("1. Lihat daftar produk")
        print("2. Transaksi penjualan")
        print("0. Logout")
        pilihan = input("Pilih menu: ").strip()
        if pilihan == "1":
            lihat_produk()
        elif pilihan == "2":
            transaksi_penjualan(user["username"])
        elif pilihan == "0":
            print("Logout berhasil.")
            break
        else:
            print("Pilihan menu tidak valid.")


def main():
    buat_database()
    print("Smart-Retail siap digunakan.")
    print("Akun awal: admin/admin123 atau kasir/kasir123")
    while True:
        user = login()
        if user:
            if user["role"] == "Admin":
                menu_admin(user)
            else:
                menu_kasir(user)
        lagi = input("Login kembali? (Y/T): ").strip().upper()
        if lagi != "Y":
            print("Terima kasih telah menggunakan Smart-Retail.")
            break


if __name__ == "__main__":
    main()
