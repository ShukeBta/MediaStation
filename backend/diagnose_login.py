#!/usr/bin/env python3
"""
登录问题诊断脚本
快速定位500错误的原因
"""
import asyncio
import sys
from pathlib import Path

# 添加backend目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

async def diagnose():
    print("=" * 60)
    print("登录问题诊断工具")
    print("=" * 60)
    
    # 1. 检查数据库连接
    print("\n[1] 检查数据库连接...")
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("  ✓ 数据库连接成功")
    except Exception as e:
        print(f"  ✗ 数据库连接失败: {e}")
        return
    
    # 2. 检查用户表
    print("\n[2] 检查用户表...")
    try:
        from app.database import async_session_factory
        from app.user.models import User
        from sqlalchemy import select
        
        async with async_session_factory() as session:
            result = await session.execute(select(User).limit(5))
            users = result.scalars().all()
            
            if not users:
                print("  ⚠ 用户表为空，没有用户数据")
                print("    请先注册或创建管理员账号")
            else:
                print(f"  ✓ 找到 {len(users)} 个用户:")
                for user in users:
                    print(f"    - {user.username} (role={user.role}, active={user.is_active})")
    except Exception as e:
        print(f"  ✗ 查询用户表失败: {e}")
        return
    
    # 3. 测试密码验证
    print("\n[3] 测试密码哈希验证...")
    try:
        from app.user.auth import verify_password, hash_password
        
        test_password = "test123"
        hashed = hash_password(test_password)
        print(f"  ✓ 密码哈希成功: {hashed[:20]}...")
        
        if verify_password(test_password, hashed):
            print("  ✓ 密码验证成功")
        else:
            print("  ✗ 密码验证失败")
    except Exception as e:
        print(f"  ✗ 密码哈希/验证失败: {e}")
        return
    
    # 4. 测试JWT token生成
    print("\n[4] 测试JWT token生成...")
    try:
        from app.user.auth import create_access_token, create_refresh_token
        
        access = create_access_token(1, "test", "user")
        refresh = create_refresh_token(1)
        print(f"  ✓ Access token 生成成功: {access[:30]}...")
        print(f"  ✓ Refresh token 生成成功: {refresh[:30]}...")
    except Exception as e:
        print(f"  ✗ Token生成失败: {e}")
        return
    
    # 5. 测试JWT token解码
    print("\n[5] 测试JWT token解码...")
    try:
        from app.user.auth import decode_token
        
        payload = decode_token(access)
        print(f"  ✓ Token解码成功: user_id={payload.get('sub')}")
    except Exception as e:
        print(f"  ✗ Token解码失败: {e}")
        return
    
    print("\n" + "=" * 60)
    print("诊断完成！如果所有检查都通过，请检查:")
    print("1. 后端控制台是否有详细的错误堆栈")
    print("2. 前端发送的请求格式是否正确")
    print("3. 用户名和密码是否匹配")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(diagnose())
