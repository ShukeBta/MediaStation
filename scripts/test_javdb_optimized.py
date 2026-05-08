"""
测试优化版 JavDB 刮削功能

新增特性测试：
- 多镜像轮询
- 健康检查和熔断机制
- 请求延迟
- Cookie 支持
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加 backend 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.media.providers.adult_optimized import AdultProvider, AdultProviderConfig

# 测试番号
TEST_CODES = ["IPX-177", "ABP-300", "MIDE-159"]


async def test_mirror_health():
    """测试镜像健康检查"""
    print("\n" + "=" * 60)
    print("镜像健康检查测试")
    print("=" * 60)
    
    config = AdultProviderConfig(
        enabled=True,
        javbus_mirrors=[
            "https://www.javbus.com",
            "https://www.buscdn.work",
            "https://www.javbus.red",
        ],
        javdb_mirrors=[
            "https://javdb.com",
            "https://javdb001.com",
        ],
        enable_health_check=True,
    )
    provider = AdultProvider(config)
    
    try:
        session = await provider._get_session()
        result = await provider.mirror_manager.health_check(session)
        
        print(f"\n健康检查结果:")
        print(f"  总镜像数: {result['total']}")
        print(f"  健康数: {result['healthy']}")
        
        print(f"\nJavBus 镜像状态:")
        for m in provider.mirror_manager.get_mirror_status("javbus"):
            print(f"  {m['url']}: {m['status']} (失败: {m['fail_count']}, 响应: {m['response_time']}s)")
        
        print(f"\nJavDB 镜像状态:")
        for m in provider.mirror_manager.get_mirror_status("javdb"):
            print(f"  {m['url']}: {m['status']} (失败: {m['fail_count']}, 响应: {m['response_time']}s)")
        
    finally:
        await provider.close()


async def test_javdb_scrape():
    """测试 JavDB 刮削（使用多镜像）"""
    print("\n" + "=" * 60)
    print("JavDB 刮削测试（多镜像模式）")
    print("=" * 60)
    
    # 从环境变量读取配置
    javdb_cookie = os.environ.get("JAVDB_COOKIE", "")
    javbus_cookie = os.environ.get("JAVBUS_COOKIE", "")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    
    print(f"\n配置信息:")
    print(f"  JavBus Cookie: {'已设置' if javbus_cookie else '未设置'}")
    print(f"  JavDB Cookie: {'已设置' if javdb_cookie else '未设置'}")
    print(f"  代理: {proxy or '未设置'}")
    
    # 创建优化版 Provider
    config = AdultProviderConfig(
        enabled=True,
        javbus_cookie=javbus_cookie,
        javdb_cookie=javdb_cookie,
        proxy=proxy,
        # 反爬配置
        enable_delay=True,
        min_delay_ms=1500,
        max_delay_ms=3000,
        # 健康检查
        enable_health_check=True,
        health_check_interval=300,
        # 熔断配置
        max_fail_count=3,
        cooldown_seconds=600,
        # 多镜像
        javbus_mirrors=[
            "https://www.javbus.com",
            "https://www.buscdn.work",
            "https://www.javbus.red",
            "https://www.seejav.art",
        ],
        javdb_mirrors=[
            "https://javdb.com",
            "https://javdb001.com",
            "https://javdb002.com",
            "https://javdb521.com",
        ],
    )
    provider = AdultProvider(config)
    
    try:
        # 打印配置状态
        status = provider.get_status()
        print(f"\n刮削器状态:")
        print(f"  延迟: {status['config']['min_delay_ms']}-{status['config']['max_delay_ms']}ms")
        print(f"  健康检查: {'启用' if status['config']['enable_health_check'] else '禁用'}")
        print(f"  熔断: {status['config']['max_fail_count']}次失败后冷却{status['config']['cooldown_seconds']}s")
        
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
                    print(f"   提示: 请检查 Cookie 配置是否正确")
                    
            except Exception as e:
                print(f"❌ 刮削出错: {e}")
        
        # 打印最终镜像状态
        print(f"\n{'─' * 60}")
        print(f"最终镜像状态")
        print("─" * 60)
        
        print(f"\nJavBus:")
        for m in provider.mirror_manager.get_mirror_status("javbus"):
            print(f"  {m['url']}: {m['status']} (成功: {m['success_count']}, 失败: {m['fail_count']})")
        
        print(f"\nJavDB:")
        for m in provider.mirror_manager.get_mirror_status("javdb"):
            print(f"  {m['url']}: {m['status']} (成功: {m['success_count']}, 失败: {m['fail_count']})")
        
    finally:
        await provider.close()


if __name__ == "__main__":
    # 先测试镜像健康检查
    print("\n🚀 开始测试优化版 JavDB 刮削功能")
    print("=" * 60)
    
    asyncio.run(test_mirror_health())
    
    # 再测试刮削功能
    asyncio.run(test_javdb_scrape())
    
    print(f"\n{'=' * 60}")
    print("测试完成！")
    print("=" * 60)
