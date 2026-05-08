"""
测试 JavDB 刮削功能
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加 backend 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.media.providers.adult import AdultProvider, AdultProviderConfig

# 测试番号
TEST_CODES = ["IPX-177", "ABP-300", "MIDE-159"]


async def test_javdb():
    """测试 JavDB 刮削"""
    print("=" * 60)
    print("JavDB 刮削测试")
    print("=" * 60)
    
    # 从环境变量读取配置
    javdb_url = os.environ.get("JAVDB_URL", "https://javdb.com")
    javdb_cookie = os.environ.get("JAVDB_COOKIE", "")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    
    print(f"\n配置信息:")
    print(f"  JavDB URL: {javdb_url}")
    print(f"  Cookie: {'已设置' if javdb_cookie else '未设置'}")
    print(f"  代理: {proxy or '未设置'}")
    
    if not javdb_cookie:
        print("\n⚠️ 警告: 未设置 JAVDB_COOKIE 环境变量")
        print("请设置环境变量: set JAVDB_COOKIE=your_cookie_here")
        return
    
    # 创建 Provider
    config = AdultProviderConfig(
        enabled=True,
        javdb_url=javdb_url,
        javdb_cookie=javdb_cookie,
        proxy=proxy,
    )
    provider = AdultProvider(config)
    
    try:
        # 测试每个番号
        for code in TEST_CODES:
            print(f"\n{'─' * 60}")
            print(f"测试番号: {code}")
            print("─" * 60)
            
            try:
                metadata = await provider.get_metadata(code, "movie")
                
                if metadata:
                    print(f"✅ 刮削成功!")
                    print(f"  标题: {metadata.title}")
                    print(f"  番号: {metadata.extra.get('adult_code', 'N/A')}")
                    print(f"  评分: {metadata.rating}")
                    print(f"  片商: {metadata.extra.get('studio', 'N/A')}")
                    print(f"  演员: {', '.join(metadata.extra.get('actors', [])[:3])}")
                    print(f"  海报: {metadata.poster_url[:80]}..." if metadata.poster_url else "  海报: N/A")
                else:
                    print(f"❌ 刮削失败: 未获取到元数据")
                    
            except Exception as e:
                print(f"❌ 刮削出错: {e}")
        
    finally:
        await provider.close()
    
    print(f"\n{'=' * 60}")
    print("测试完成")
    print("=" * 60)


async def test_javdb_connectivity():
    """测试 JavDB 网络连通性"""
    print("\n" + "=" * 60)
    print("JavDB 网络连通性测试")
    print("=" * 60)
    
    import aiohttp
    
    javdb_url = os.environ.get("JAVDB_URL", "https://javdb.com")
    javdb_cookie = os.environ.get("JAVDB_COOKIE", "")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": javdb_cookie,
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            # 测试主页访问
            print(f"\n测试 URL: {javdb_url}")
            print(f"代理: {proxy or '无'}")
            
            async with session.get(javdb_url, proxy=proxy, ssl=False) as resp:
                print(f"状态码: {resp.status}")
                print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
                
                if resp.status == 200:
                    html = await resp.text()
                    print(f"响应长度: {len(html)} 字符")
                    
                    # 检查是否需要登录
                    if "login" in html.lower() or "登录" in html:
                        print("⚠️ 提示: 页面可能需要登录")
                    
                    # 检查 cookie 是否有效
                    if "sign in" in html.lower() or "register" in html.lower():
                        print("⚠️ 警告: Cookie 可能无效或已过期")
                    else:
                        print("✅ Cookie 可能有效（未检测到登录页面）")
                        
                elif resp.status == 403:
                    print("❌ 403 Forbidden: 可能被反爬机制拦截")
                    print("   建议: 更新 Cookie 或使用代理")
                elif resp.status == 429:
                    print("❌ 429 Too Many Requests: 请求过多，请稍后再试")
                else:
                    print(f"❌ 请求失败: HTTP {resp.status}")
                    
    except Exception as e:
        print(f"❌ 连接错误: {e}")


if __name__ == "__main__":
    # 先测试连通性
    asyncio.run(test_javdb_connectivity())
    
    # 再测试刮削功能
    asyncio.run(test_javdb())
