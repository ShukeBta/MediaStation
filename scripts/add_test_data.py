import sqlite3
from datetime import datetime

conn = sqlite3.connect('backend/data/mediastation.db')
cursor = conn.cursor()

now = datetime.now().isoformat()

# 先添加媒体库
cursor.execute('''
INSERT OR IGNORE INTO media_libraries (id, name, path, media_type, created_at)
VALUES 
(1, 'Movies', 'C:\\Movies', 'movie', ?),
(2, 'TV Shows', 'C:\\TV', 'tv', ?)
''', (now, now))

# 添加测试媒体项
cursor.execute('''
INSERT OR IGNORE INTO media_items (
    id, library_id, title, original_title, year, tmdb_id, 
    overview, poster_url, backdrop_url, media_type, 
    rating, date_added, scraped, created_at, updated_at
) VALUES (
    1, 1, 'The Shawshank Redemption', 'The Shawshank Redemption', 1994, 278,
    'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
    'https://image.tmdb.org/t/p/w500/9cjIGRQL4ImFcPTmH8L21znZdE.jpg',
    'https://image.tmdb.org/t/p/original/kzzo160xCXv13LdJTOXD0Jiirfn.jpg',
    'movie', 9.3, ?, 1, ?, ?)
''', (now, now, now))

cursor.execute('''
INSERT OR IGNORE INTO media_items (
    id, library_id, title, original_title, year, tmdb_id, 
    overview, poster_url, backdrop_url, media_type, 
    rating, date_added, scraped, created_at, updated_at
) VALUES (
    2, 1, 'The Godfather', 'The Godfather', 1972, 238,
    'The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.',
    'https://image.tmdb.org/t/p/w500/3bh7Zxj0qXpyINVyCGBl4x2cIi9.jpg',
    'https://image.tmdb.org/t/p/original/rSPw8lJ67SkGw5xN7FznjXuden.jpg',
    'movie', 9.2, ?, 1, ?, ?)
''', (now, now, now))

cursor.execute('''
INSERT OR IGNORE INTO media_items (
    id, library_id, title, original_title, year, tmdb_id, 
    overview, poster_url, backdrop_url, media_type, 
    rating, date_added, scraped, created_at, updated_at
) VALUES (
    3, 2, 'Breaking Bad', 'Breaking Bad', 2008, 1396,
    'A high school chemistry teacher diagnosed with inoperable lung cancer turns to manufacturing and selling methamphetamine.',
    'https://image.tmdb.org/t/p/w500/9MrSpicrtaQMQPylaxb3DAu0gR.jpg',
    'https://image.tmdb.org/t/p/original/tsRy63Mu5cu8etL1AWn9W0QcXv0.jpg',
    'tv', 9.1, ?, 1, ?, ?)
''', (now, now, now))

# 添加季（使用 media_item_id 而不是 media_id）
cursor.execute('''
INSERT OR IGNORE INTO media_seasons (id, media_item_id, season_number, name, poster_url, created_at)
VALUES 
(1, 3, 1, 'Season 1', 'https://image.tmdb.org/t/p/w500/9MrSpicrtaQMQPylaxb3DAu0gR.jpg', ?)
''', (now,))

# 添加集
cursor.execute('''
INSERT OR IGNORE INTO media_episodes (id, season_id, episode_number, title, file_path, created_at, updated_at)
VALUES 
(1, 1, 1, 'Pilot', 'C:\\TV\\Breaking Bad\\Season 1\\S01E01.mkv', ?, ?)
''', (now, now))

conn.commit()
print('测试数据已添加')

# 验证
cursor.execute('SELECT COUNT(*) FROM media_items')
print(f'媒体项数量: {cursor.fetchone()[0]}')

cursor.execute('SELECT id, title, media_type FROM media_items')
for row in cursor.fetchall():
    print(f'  {row}')

conn.close()
