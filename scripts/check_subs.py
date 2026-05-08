import sqlite3

db_path = r'c:\Users\Administrator\WorkBuddy\20260428130330\data\mediastation.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, status FROM subscriptions")
    rows = cursor.fetchall()

    print(f"Total subscriptions: {len(rows)}")
    for r in rows:
        print(f"  ID={r[0]}, name='{r[1]}', status={r[2]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
