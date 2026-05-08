"""
M-Team API 详细诊断脚本
"""
import asyncio
import httpx
import sqlite3

# 1. 从数据库读取 API Key
conn = sqlite3.connect('c:/Users/Administrator/WorkBuddy/20260428130330/backend/data/mediastation.db')
cursor = conn.cursor()
cursor.execute('SELECT api_key, base_url, auth_type FROM sites WHERE id=1')
row = cursor.fetchone()
conn.close()

if not row:
    print("ERROR: Site ID=1 not found")
    exit(1)

api_key = row[0] or ""
base_url = row[1] or ""
auth_type = row[2] or ""

print("=" * 60)
print("数据库中的配置:")
print(f"  base_url:  {base_url}")
print(f"  auth_type: {auth_type}")
print(f"  api_key:    {repr(api_key)}")
print(f"  api_key长度: {len(api_key)}")
print(f"  api_key字节: {api_key.encode('utf-8')!r}")
print("=" * 60)

# 2. 测试 API 调用
API_BASE = "https://test2.m-team.cc/api"

async def test_api():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
    }
    
    print("\n发送的请求:")
    print(f"  URL: {API_BASE}/torrent/search")
    print(f"  Method: POST")
    print(f"  Headers: x-api-key = {repr(headers['x-api-key'])}")
    print(f"  Body: {{\"pageNumber\": 1, \"pageSize\": 5, \"keyword\": \"test\"}}")
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{API_BASE}/torrent/search",
                json={"pageNumber": 1, "pageSize": 5, "keyword": "test"},
                headers=headers,
                timeout=15,
            )
            print(f"\n响应状态码: {resp.status_code}")
            print(f"响应内容: {resp.text[:500]}")
    except Exception as e:
        print(f"\n请求失败: {e}")

asyncio.run(test_api())
