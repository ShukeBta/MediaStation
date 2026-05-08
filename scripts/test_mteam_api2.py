import asyncio
import httpx

API_KEY = "019dde94-a633-7d35-b9b5-da2d54eb5eb4"
BASE_URL = "https://zp.m-team.cc"

print(f"测试 M-Team 正式环境 API")
print(f"  Base URL: {BASE_URL}")
print(f"  API Key: {API_KEY[:20]}...")
print()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-api-key": API_KEY
}

async def test():
    async with httpx.AsyncClient(follow_redirects=False) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/api/torrent/search",
                json={"pageNumber": 1, "pageSize": 1, "keyword": "test"},
                headers=headers,
                timeout=15.0
            )
            print(f"HTTP Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
            
            if resp.status_code in (301, 302, 303, 307, 308):
                print("❌ 认证失败：API Key 无效或已过期")
                print(f"  重定向到: {resp.headers.get('Location', '(无)')}")
            elif resp.status_code == 200:
                data = resp.json()
                code = str(data.get("code", ""))
                if code == "0":
                    print("✅ API Key 有效！")
                else:
                    print(f"❌ API 返回错误: code={code}, message={data.get('message')}")
        except Exception as e:
            print(f"❌ 请求失败: {type(e).__name__}: {e}")

asyncio.run(test())
