"""重置admin用户密码为admin123（带重试逻辑）"""
import sys
import os
import time

# 添加backend目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.user.auth import hash_password
import sqlite3

# 生成新的密码哈希
new_hash = hash_password("admin123")
print(f"新密码哈希: {new_hash}")

# 更新数据库（带重试逻辑）
max_retries = 5
retry_delay = 1  # 秒

for attempt in range(1, max_retries + 1):
    try:
        print(f"尝试更新数据库 (第 {attempt} 次)...")
        conn = sqlite3.connect('backend/data/mediastation.db', timeout=30)
        conn.execute('PRAGMA busy_timeout = 30000')  # 设置忙等待超时30秒
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = "admin"', (new_hash,))
        conn.commit()
        conn.close()
        print("密码已重置为: admin123")
        break
    except sqlite3.OperationalError as e:
        print(f"第 {attempt} 次尝试失败: {e}")
        if attempt < max_retries:
            print(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
        else:
            print("达到最大重试次数，放弃")
            raise
