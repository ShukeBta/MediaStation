import sqlite3
import sys
import shutil
import os

# Backup database path
backup_db_path = r'c:\Users\Administrator\WorkBuddy\20260428130330\backend\data\mediastation.db'
# Current database path
current_db_path = r'c:\Users\Administrator\WorkBuddy\20260428130330\data\mediastation.db'

try:
    # Check current database
    print(f"=== Checking current database: {current_db_path} ===")
    conn = sqlite3.connect(current_db_path)
    cursor = conn.cursor()

    # Get table schema
    cursor.execute("PRAGMA table_info(subscriptions)")
    columns = cursor.fetchall()
    print("\n=== Subscriptions table columns in current DB ===")
    for c in columns:
        print(f"  {c[1]} ({c[2]})")

    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    count = cursor.fetchone()[0]
    print(f"\nSubscriptions count in current: {count}")

    conn.close()

    # Create backup of current database
    current_backup = current_db_path + ".before_restore"
    print(f"\n=== Creating backup of current database ===")
    shutil.copy2(current_db_path, current_backup)
    print(f"Current database backed up to: {current_backup}")

    # Option 1: Copy entire backup database to current
    print(f"\n=== Restoring database ===")
    shutil.copy2(backup_db_path, current_db_path)
    print(f"Database restored from backup!")

    # Verify
    print(f"\n=== Verifying restore ===")
    conn2 = sqlite3.connect(current_db_path)
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT COUNT(*) FROM subscriptions")
    new_count = cursor2.fetchone()[0]
    print(f"Current database now has {new_count} subscriptions")

    if new_count > 0:
        cursor2.execute("SELECT id, name, status FROM subscriptions")
        rows = cursor2.fetchall()
        print("\nRestored subscriptions:")
        for r in rows:
            print(f"  ID={r[0]}, name='{r[1]}', status={r[2]}")

    conn2.close()

    print("\n=== Restore complete! ===")
    print("Please restart the backend service to use the restored data.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
