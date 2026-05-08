"""
测试 M-Team API 的正确调用格式
根据用户的说明：文档可能有 bug，请求格式（json/form）可能不匹配实际
"""
import asyncio
import httpx
import json

API_KEY = "019dde94-a633-7d35-b9b5-da2d54eb5eb4"
BASE_URL = "https://api.m-team.cc"  # 生产环境（你的 API Key 在这里有效）

headers_json = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-api-key": API_KEY
}

headers_form = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "x-api-key": API_KEY
}

async def test_search_json(client):
    """测试 JSON 格式的搜索请求"""
    print("\n[测试 1] JSON 格式 POST /api/torrent/search")
    payload = {
        "pageNumber": 1,
        "pageSize": 10,
        "keyword": "avatar"
    }
    try:
        resp = await client.post(
            f"{BASE_URL}/api/torrent/search",
            json=payload,
            headers=headers_json,
            timeout=10.0
        )
        print(f"  HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  code: {data.get('code')}")
            print(f"  message: {data.get('message')}")
            if data.get('code') == '0':
                items = data.get('data', {}).get('data', [])
                print(f"  ✅ 返回 {len(items)} 个结果")
                if items:
                    print(f"  第一个: {items[0].get('name', '')[:60]}")
            else:
                print(f"  ❌ API 错误: {data.get('message')}")
        else:
            print(f"  Response: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def test_search_form(client):
    """测试 Form 格式的搜索请求"""
    print("\n[测试 2] Form 格式 POST /api/torrent/search")
    form_data = {
        "pageNumber": "1",
        "pageSize": "10",
        "keyword": "avatar"
    }
    try:
        resp = await client.post(
            f"{BASE_URL}/api/torrent/search",
            data=form_data,
            headers=headers_form,
            timeout=10.0
        )
        print(f"  HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  code: {data.get('code')}")
            print(f"  message: {data.get('message')}")
            if data.get('code') == '0':
                items = data.get('data', {}).get('data', [])
                print(f"  ✅ 返回 {len(items)} 个结果")
                if items:
                    print(f"  第一个: {items[0].get('name', '')[:60]}")
            else:
                print(f"  ❌ API 错误: {data.get('message')}")
        else:
            print(f"  Response: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def test_search_get(client):
    """测试 GET 格式的搜索请求"""
    print("\n[测试 3] GET 格式 /api/torrent/search")
    params = {
        "pageNumber": 1,
        "pageSize": 10,
        "keyword": "avatar"
    }
    try:
        resp = await client.get(
            f"{BASE_URL}/api/torrent/search",
            params=params,
            headers=headers_json,
            timeout=10.0
        )
        print(f"  HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  code: {data.get('code')}")
            print(f"  message: {data.get('message')}")
        else:
            print(f"  Response: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def test_gen_token(client):
    """测试 genDlToken 端点"""
    print("\n[测试 4] POST /api/torrent/genDlToken")
    try:
        # 先搜索获取一个种子 ID
        resp = await client.post(
            f"{BASE_URL}/api/torrent/search",
            json={"pageNumber": 1, "pageSize": 1, "keyword": "test"},
            headers=headers_json,
            timeout=10.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == '0':
                items = data.get('data', {}).get('data', [])
                if items:
                    torrent_id = items[0].get('id')
                    print(f"  使用种子 ID: {torrent_id}")
                    
                    # 测试 genDlToken
                    resp2 = await client.post(
                        f"{BASE_URL}/api/torrent/genDlToken?id={torrent_id}",
                        headers={"x-api-key": API_KEY, "User-Agent": "Mozilla/5.0"}
                    )
                    print(f"  HTTP {resp2.status_code}")
                    print(f"  Response: {resp2.text[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def main():
    print("=" * 60)
    print("M-Team API 调用格式测试")
    print("=" * 60)
    print(f"API Key: {API_KEY[:20]}...")
    print(f"Base URL: {BASE_URL}")
    
    async with httpx.AsyncClient(follow_redirects=False) as client:
        # 测试不同的请求格式
        await test_search_json(client)
        await test_search_form(client)
        await test_search_get(client)
        await test_gen_token(client)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
