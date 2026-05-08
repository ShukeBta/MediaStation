"""测试扫描综艺媒体库"""
import asyncio
import sys

sys.path.insert(0, 'c:/Users/Administrator/WorkBuddy/20260428130330/backend')

from app.database import engine, get_session_factory, init_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.media.service import MediaService
from app.media.repository import MediaRepository
from app.system.events import get_event_bus


async def test_scan():
    """测试扫描"""
    # 先初始化数据库（导入所有模型）
    await init_db()
    
    # 创建会话
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        service = MediaService(MediaRepository(session), get_event_bus())
        
        print("开始扫描ID=6的媒体库（综艺）...")
        try:
            result = await service.scan_library(6, auto_scrape=False)
            # 手动提交事务
            await session.commit()
            print(f"扫描结果:")
            print(f"  新增: {result.added}")
            print(f"  更新: {result.updated}")
            print(f"  移除: {result.removed}")
            print(f"  刮削: {result.scraped}")
            if result.errors:
                print(f"  错误: {result.errors}")
            else:
                print("  无错误")
        except Exception as e:
            await session.rollback()
            print(f"扫描失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_scan())
