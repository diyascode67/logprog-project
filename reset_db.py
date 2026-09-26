import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_retail.db')

def reset():
    if not os.path.exists(DB_PATH):
        print(f"Database tidak ditemukan di {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM produk")
    prod_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM transaksi")
    trx_count = cur.fetchone()[0]

    print(f"Sebelum reset: {prod_count} produk, {trx_count} transaksi")

    cur.execute("DELETE FROM detail_transaksi")
    cur.execute("DELETE FROM transaksi")
    cur.execute("DELETE FROM produk")

    # Reset auto-increment ID ke 0
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('detail_transaksi', 'transaksi', 'produk')")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM produk")
    new_prod = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM transaksi")
    new_trx = cur.fetchone()[0]

    conn.close()

    print(f"Reset berhasil! Database bersih: {new_prod} produk, {new_trx} transaksi.")

if __name__ == '__main__':
    reset()
