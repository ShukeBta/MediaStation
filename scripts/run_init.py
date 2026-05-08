import sqlite3
conn = sqlite3.connect('c:/Users/Administrator/WorkBuddy/20260428130330/data/mediastation.db')
cursor = conn.cursor()

# 创建表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        provider VARCHAR(50) NOT NULL UNIQUE,
        api_key TEXT,
        base_url VARCHAR(500),
        extra TEXT,
        enabled BOOLEAN DEFAULT 1,
        description VARCHAR(200)
    )
''')
conn.commit()
print("Table created")

# 插入默认配置
defaults = [
    ('tmdb', 'https://api.themoviedb.org/3', None, 1, 'TMDb API - 电影/剧集主数据源'),
    ('douban', None, None, 1, '豆瓣 - 中文元数据补充源'),
    ('bangumi', 'https://api.bgm.tv/v0', None, 1, 'Bangumi - 番剧/动画元数据源'),
    ('thetvdb', 'https://api4.thetvdb.com/v4', None, 1, 'TheTVDB - 剧集增强数据源'),
    ('fanart', 'https://webservice.fanart.tv/v3', None, 1, 'Fanart.tv - 高质量图片增强源'),
    ('openai', 'https://api.openai.com/v1', None, 1, 'OpenAI 兼容 API - AI 刮削和智能增强'),
    ('siliconflow', 'https://api.siliconflow.cn/v1', None, 1, '硅基流动 - 国产 AI API 平替'),
    ('deepseek', 'https://api.deepseek.com/v1', None, 1, 'DeepSeek - 国产大模型 API'),
]

for provider, base_url, api_key, enabled, description in defaults:
    cursor.execute('''
        INSERT OR IGNORE INTO api_configs (provider, base_url, api_key, enabled, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (provider, base_url, api_key, enabled, description))

conn.commit()

# 查询结果
cursor.execute('SELECT provider, description, enabled FROM api_configs ORDER BY provider')
rows = cursor.fetchall()
print(f'\n数据库中现有 {len(rows)} 条 API 配置：')
for r in rows:
    print(f'  {r[0]:15s} | {"Y" if r[2] else "N"} | {r[1]}')

conn.close()
