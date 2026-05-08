import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    try:
        from app.database import async_session_factory, init_db
        from sqlalchemy import select
        from app.subscribe.models import Site
        
        await init_db()
        async with async_session_factory() as session:
            # 测试ORM查询
            result = await session.execute(select(Site))
            sites = result.scalars().all()
            print(f"ORM query: {len(sites)} sites")
            for s in sites:
                print(f"  Site: id={s.id}, name={s.name}, site_type={s.site_type}")
                print(f"  api_key present: {bool(s.api_key)}")
                if s.api_key:
                    print(f"  api_key: {s.api_key[:20]}...")
                
                # 测试适配器
                from app.subscribe.site_adapter import create_site_adapter, MTeamAdapter
                adapter = create_site_adapter(s)
                print(f"  Adapter type: {type(adapter).__name__}")
                
                if isinstance(adapter, MTeamAdapter):
                    # 测试genDlToken
                    print("  Testing genDlToken...")
                    content, error = await adapter._download_torrent_file(767692)
                    if content:
                        print(f"  SUCCESS: Got {len(content)} bytes torrent")
                    else:
                        print(f"  FAILED: {error}")
                
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

asyncio.run(test())
