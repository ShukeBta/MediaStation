"""
重置数据库中的敏感信息
运行前请备份数据库！
"""
import sqlite3
import secrets
import string
import hashlib
import os

DB_PATH = "data/mediastation.db"

def generate_password(length=16):
    """生成随机密码"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_api_key(length=32):
    """生成随机 API Key"""
    return secrets.token_hex(length)

def simple_hash(text):
    """简单哈希（用于演示，实际应使用 bcrypt）"""
    return hashlib.sha256(text.encode()).hexdigest()

def reset_sensitive_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=" * 50)
    print("开始重置敏感信息...")
    print("=" * 50)

    # 1. 重置用户密码
    print("\n[1] 重置用户密码...")
    new_password = generate_password()
    new_hash = simple_hash(new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (new_hash,))
    print(f"  admin 新密码: {new_password}")
    print(f"  ⚠️  请保存此密码！")

    # 2. 重置 API Keys
    print("\n[2] 重置 API Keys...")
    new_tmdb_key = generate_api_key(16)
    cur.execute("UPDATE api_configs SET api_key = ? WHERE provider = 'tmdb'", (new_tmdb_key,))
    print(f"  TMDB API Key: {new_tmdb_key}")
    print(f"  ⚠️  请更新 TMDB 账户中的 API Key！")

    # 3. 重置下载客户端密码
    print("\n[3] 重置下载客户端密码...")
    new_qb_password = generate_password()
    new_qb_hash = simple_hash(new_qb_password)
    cur.execute("UPDATE download_clients SET password = ? WHERE client_type = 'qbittorrent'", (new_qb_password,))
    print(f"  qBittorrent 新密码: {new_qb_password}")
    print(f"  ⚠️  请同时更新 qBittorrent Web UI 中的密码！")

    # 4. 重置站点 API Keys
    print("\n[4] 重置站点 API Keys...")
    new_mteam_key = generate_api_key(16)
    cur.execute("UPDATE sites SET api_key = ? WHERE name = 'M-Team'", (new_mteam_key,))
    print(f"  M-Team API Key: {new_mteam_key}")
    print(f"  ⚠️  请更新 M-Team 账户中的 API Key！")

    # 5. 生成新的许可证密钥
    print("\n[5] 许可证密钥（保持不变）...")
    print("  如需重置，请在许可证服务器管理界面生成新密钥")

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("✅ 重置完成！")
    print("=" * 50)
    print("\n⚠️  重要提醒：")
    print("1. 请保存上述所有新密码和 API Key")
    print("2. 请更新对应服务的密码/密钥")
    print("3. 建议立即备份数据库: data/mediastation.db")

    # 生成重置报告
    report = f"""
# 安全重置报告 - {os.path.basename(DB_PATH)}
生成时间: {os.path.getmtime(DB_PATH)}

## 新密码（本地用户）
- admin: {new_password}

## 新 API Keys
- TMDB: {new_tmdb_key}
- M-Team: {new_mteam_key}

## 下载客户端
- qBittorrent: {new_qb_password}

## 需要手动更新的服务
1. TMDB 账户: https://www.themoviedb.org/settings/api
2. M-Team: https://api.m-team.cc/
3. qBittorrent Web UI: http://127.0.0.1:8080
"""
    with open("data/reset_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n已生成重置报告: data/reset_report.txt")

if __name__ == "__main__":
    # 确认提示
    print("警告：此脚本将重置数据库中的所有密码和 API Keys！")
    response = input("继续？(yes/no): ")
    if response.lower() == "yes":
        reset_sensitive_data()
    else:
        print("已取消。")
