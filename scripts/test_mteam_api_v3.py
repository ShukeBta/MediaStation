"""
测试 M-Team API v3 的正确调用方式
"""
import asyncio
import httpx
import json

API_KEY = "019dde94-a633-7d35-b9b5-da2d54eb5eb4"
BASE_URL = "https://api.m-team.cc"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-api-key": API_KEY
}

async def test_endpoint(client, method, url, data=None, params=None):
    try:
        if method.upper() == "GET":
            resp = await client.get(url, params=params, headers=headers, timeout=10.0)
        elif method.upper() == "POST":
            resp = await client.post(url, json=data, headers=headers, timeout=10.0)
        else:
            return f"Unsupported method: {method}"
        
        if resp.status_code == 200:
            return f"✅ HTTP 200: {json.dumps(resp.json(), ensure_ascii=False)[:200]}"
        else:
            return f"❌ HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"❌ Error: {type(e).__name__}: {str(e)[:100]}"

async def main():
    print("=" * 60)
    print("M-Team API v3 测试")
    print("=" * 60)
    
    async with httpx.AsyncClient(follow_redirects=False, verify=False) as client:
        
        # 测试 1: 搜索接口
        print("\n[测试 1] 搜索接口 POST /api/torrent/search")
        search_data = {
            "pageNumber": 1,
            "pageSize": 10,
            "keyword": "avatar"
        }
        result = await test_endpoint(client, "POST", f"{BASE_URL}/api/torrent/search", data=search_data)
        print(f"  结果: {result}")
        
        # 测试 2: 获取下载 Token
        print("\n[测试 2] 获取下载 Token POST /api/torrent/genDlToken")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/torrent/search",
                json={"pageNumber": 1, "pageSize": 1, "keyword": "test"},
                headers=headers,
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "0":
                    torrents = data.get("data", {}).get("data", [])
                    if torrents:
                        torrent_id = torrents[0].get("id")
                        print(f"  使用种子 ID: {torrent_id}")
                        result = await test_endpoint(
                            client, "POST",
                            f"{BASE_URL}/api/torrent/genDlToken?id={torrent_id}"
                        )
                        print(f"  结果: {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # 测试 3: 用户信息接口
        print("\n[测试 3] 用户信息 GET /api/member/profile")
        result = await test_endpoint(client, "GET", f"{BASE_URL}/api/member/profile")
        print(f"  结果: {result}")
        
        # 测试 4: 消息通知接口
        print("\n[测试 4] 消息统计 GET /api/msg/statistic")
        result = await test_endpoint(client, "GET", f"{BASE_URL}/api/msg/statistic")
        print(f"  结果: {result}")

asyncio.run(main())
