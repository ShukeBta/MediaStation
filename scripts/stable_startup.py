#!/usr/bin/env python3
"""
MediaStation 稳定启动脚本
自动重启并保持后端服务运行

安全设计：
- 所有 socket 操作带硬性超时，防止防火墙 Drop 导致永久阻塞
- 启动探测有最大重试次数，超限后 exit(1) 触发 Docker 重启策略
- 进程输出实时流式读取，避免 PIPE 死锁
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

# ── 安全常量 ──
STARTUP_TIMEOUT = 30       # 等待服务启动的最大秒数
PROBE_INTERVAL = 2         # 探测间隔秒数
SOCKET_TIMEOUT = 3         # 单次 socket 连接超时（秒）
MAX_LAUNCH_ATTEMPTS = 3    # 最大启动尝试次数


def is_port_in_use(port, timeout=SOCKET_TIMEOUT):
    """检查端口是否被占用（带硬性超时，防止防火墙 Drop 导致阻塞）"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except (socket.timeout, OSError) as e:
        logger.warning(f"端口探测超时或异常: {e}")
        return False


def wait_for_service(port, timeout=STARTUP_TIMEOUT):
    """
    带超时的服务就绪探测。
    返回 True 表示服务已就绪，False 表示超时。
    """
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(PROBE_INTERVAL)
    return False


def start_backend():
    """启动后端服务（带重试和超时保护）"""
    backend_dir = Path(__file__).parent / 'backend'

    logger.info("=" * 60)
    logger.info("启动 MediaStation 后端服务")
    logger.info("=" * 60)

    # 检查端口是否已占用
    if is_port_in_use(3001):
        logger.warning("端口 3001 已被占用，跳过启动")
        return True

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

    for attempt in range(1, MAX_LAUNCH_ATTEMPTS + 1):
        logger.info(f"启动尝试 {attempt}/{MAX_LAUNCH_ATTEMPTS}")

        try:
            # 启动进程（stdout/stderr 重定向到日志文件，避免 PIPE 死锁）
            log_path = Path(__file__).parent / 'backend.log'
            log_fh = open(log_path, 'a', encoding='utf-8')

            process = subprocess.Popen(
                cmd,
                cwd=str(backend_dir),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )

            logger.info(f"进程已启动 (PID: {process.pid})")

            # 带超时的服务就绪探测
            if wait_for_service(3001, timeout=STARTUP_TIMEOUT):
                logger.info(f"✓ 服务启动成功! (PID: {process.pid})")
                logger.info("访问地址: http://localhost:3001")
                return True
            else:
                logger.error(f"✗ 服务启动超时 ({STARTUP_TIMEOUT}s)，进程仍在运行")
                # 检查进程是否已退出
                retcode = process.poll()
                if retcode is not None:
                    logger.error(f"进程已退出，返回码: {retcode}")
                else:
                    logger.error("进程仍在运行但端口未监听，尝试终止...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

        except Exception as e:
            logger.error(f"启动异常 (尝试 {attempt}): {e}")
        finally:
            try:
                log_fh.close()
            except Exception:
                pass

    # 所有尝试都失败 → exit(1) 让 Docker restart 策略接管
    logger.critical(
        f"❌ 服务启动失败（已尝试 {MAX_LAUNCH_ATTEMPTS} 次），"
        f"退出以触发 Docker 重启策略"
    )
    sys.exit(1)


if __name__ == '__main__':
    start_backend()
