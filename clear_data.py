import sqlite3, os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_retail.db')
print(f"Database: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('PRAGMA foreign_keys = OFF')
c.execute('DELETE FROM detail_transaksi')
c.execute('DELETE FROM transaksi')
c.execute('DELETE FROM produk')

# Reset auto-increment counters
for tbl in ('produk', 'transaksi', 'detail_transaksi'):
    c.execute("DELETE FROM sqlite_sequence WHERE name=?", (tbl,))

c.execute('PRAGMA foreign_keys = ON')
conn.commit()
c.execute('VACUUM')

print("\n=== Row counts after cleanup ===")
for tbl in ('users', 'produk', 'transaksi', 'detail_transaksi'):
    c.execute(f'SELECT COUNT(*) FROM {tbl}')
    print(f'  {tbl}: {c.fetchone()[0]} rows')

conn.close()
print("\nDONE. Database cleared. Users preserved.")
