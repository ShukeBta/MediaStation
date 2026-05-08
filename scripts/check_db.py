import sqlite3
import sys

try:
    conn = sqlite3.connect('c:/Users/Administrator/WorkBuddy/20260428130330/data/mediastation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_configs'")
    if cursor.fetchone():
        cursor.execute("SELECT * FROM api_configs")
        rows = cursor.fetchall()
        result = "Found {} rows\n".format(len(rows))
        for row in rows:
            result += str(row) + "\n"
    else:
        result = "Table api_configs does not exist!"
    conn.close()
    
    with open('c:/Users/Administrator/WorkBuddy/20260428130330/db_result.txt', 'w') as f:
        f.write(result)
except Exception as e:
    with open('c:/Users/Administrator/WorkBuddy/20260428130330/db_error.txt', 'w') as f:
        f.write(str(e))
