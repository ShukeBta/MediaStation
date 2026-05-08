"""测试SubscribeService.create_subscription方法"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.subscribe.service import SubscribeService
from app.subscribe.schemas import SubscriptionCreate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

async def test_create_subscription():
    # 创建数据库会话
    engine = create_engine('sqlite:///data/mediastation.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 创建服务实例
        service = SubscribeService(session)
        
        # 创建订阅数据
        data = SubscriptionCreate(name='测试订阅', media_type='movie')
        print(f"尝试创建订阅: {data}")
        
        # 调用服务方法
        result = await service.create_subscription(data)
        print(f"创建成功! ID: {result.id}, 名称: {result.name}")
        
    except Exception as e:
        print(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_create_subscription())
