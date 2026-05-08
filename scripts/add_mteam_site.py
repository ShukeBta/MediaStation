import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/mediastation.db')
cursor = conn.cursor()

# 检查是否已存在 M-Team 站点
cursor.execute('SELECT id FROM sites WHERE name=?', ('M-Team',))
existing = cursor.fetchone()
if existing:
    print(f'站点已存在，ID={existing[0]}，进行更新...')
    cursor.execute('''
    UPDATE sites SET 
        base_url=?, site_type=?, auth_type=?, api_key=?,
        timeout=?, priority=?, use_proxy=?, rate_limit=?,
        browser_emulation=?, enabled=?, login_status=?,
        upload_bytes=?, download_bytes=?,
        updated_at=?
    WHERE id=?
    ''', (
        'https://api.m-team.cc/',
        'mteam',
        'api_key',
        '019dde94-a633-7d35-b9b5-da2d54eb5eb4',
        30,
        0,
        0,
        0,
        0,
        1,
        'unknown',
        0,
        0,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        existing[0]
    ))
    site_id = existing[0]
else:
    # 插入 M-Team 站点配置
    cursor.execute('''
    INSERT INTO sites (
        name, base_url, site_type, auth_type, api_key,
        timeout, priority, use_proxy, rate_limit,
        browser_emulation, enabled, login_status,
        upload_bytes, download_bytes,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'M-Team',
        'https://api.m-team.cc/',
        'mteam',
        'api_key',
        '019dde94-a633-7d35-b9b5-da2d54eb5eb4',
        30,
        0,
        0,
        0,
        0,
        1,
        'unknown',
        0,
        0,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    site_id = cursor.lastrowid
    print(f'✅ 站点已添加，ID={site_id}')

conn.commit()

# 验证结果
cursor.execute('SELECT id, name, base_url, site_type, api_key FROM sites WHERE id=?', (site_id,))
row = cursor.fetchone()
print(f'\n验证配置:')
print(f'  ID: {row[0]}')
print(f'  Name: {row[1]}')
print(f'  Base URL: {row[2]}')
print(f'  Site Type: {row[3]}')
print(f'  API Key: {row[4][:30]}...')

conn.close()
print('\n✅ 数据库更新完成')
