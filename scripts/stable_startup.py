#!/usr/bin/env python3
"""
MediaStation 稳定启动脚本
自动重启并保持后端服务运行
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path

# 配置日志
log_file = Path(__file__).parent / 'stable_startup.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('stable_startup')

def is_port_in_use(port):
    """检查端口是否被占用"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def start_backend():
    """启动后端服务"""
    backend_dir = Path(__file__).parent / 'backend'

    logger.info("=" * 60)
    logger.info("启动 MediaStation 后端服务")
    logger.info("=" * 60)

    # 检查端口是否已占用
    if is_port_in_use(3001):
        logger.warning("端口 3001 已被占用，跳过启动")
        return False

    # 启动命令
    cmd = [
        sys.executable,
        '-m', 'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', '3001',
        '--log-level', 'info'
    ]

    logger.info(f"执行命令: {' '.join(cmd)}")
    logger.info(f"工作目录: {backend_dir}")

    try:
        # 启动进程
        process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )

        logger.info(f"进程已启动 (PID: {process.pid})")

        # 等待服务启动
        logger.info("等待服务启动 (10秒)...")
        time.sleep(10)

        # 验证服务
        if is_port_in_use(3001):
            logger.info("✓ 服务启动成功!")
            logger.info("访问地址: http://localhost:3001")
            return True
        else:
            logger.error("✗ 服务启动失败")
            # 读取输出
            logger.error("进程输出:")
            return False

    except Exception as e:
        logger.error(f"启动异常: {e}")
        return False

if __name__ == '__main__':
    start_backend()
