#!/usr/bin/env python3
"""
MediaStation 服务管理器
自动监控并重启后端服务
"""
import os
import sys
import time
import socket
import subprocess
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler('service_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('service_manager')

class ServiceManager:
    def __init__(self, port=3001):
        self.port = port
        self.process = None
        self.backend_dir = Path(__file__).parent / 'backend'

    def check_port(self):
        """检查端口是否被占用"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', self.port))
        sock.close()
        return result == 0

    def is_process_alive(self):
        """检查进程是否存活"""
        if self.process is None:
            return False
        return self.process.poll() is None

    def start_backend(self):
        """启动后端服务"""
        try:
            logger.info(f"启动后端服务 (端口 {self.port})...")
            cmd = [
                sys.executable, '-m', 'uvicorn',
                'app.main:app',
                '--host', '0.0.0.0',
                '--port', str(self.port),
                '--log-level', 'info'
            ]
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.backend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(5)

            if self.check_port():
                logger.info(f"✓ 后端服务启动成功 (PID: {self.process.pid})")
                return True
            else:
                logger.error("✗ 后端服务启动失败")
                return False
        except Exception as e:
            logger.error(f"启动失败: {e}")
            return False

    def stop_backend(self):
        """停止后端服务"""
        if self.process:
            logger.info("停止后端服务...")
            self.process.terminate()
            self.process.wait(timeout=10)

    def run(self, check_interval=30):
        """运行服务管理器"""
        logger.info("=" * 50)
        logger.info("MediaStation 服务管理器启动")
        logger.info(f"监控端口: {self.port}")
        logger.info(f"检查间隔: {check_interval}秒")
        logger.info("=" * 50)

        while True:
            try:
                # 检查端口占用
                if not self.check_port():
                    logger.warning("检测到服务未运行，正在重启...")

                    # 如果进程存在但端口未监听，先停止
                    if self.is_process_alive():
                        self.stop_backend()

                    # 重启服务
                    if not self.start_backend():
                        logger.error("重启失败，10秒后重试...")
                        time.sleep(10)
                        continue

                # 检查进程健康
                elif not self.is_process_alive():
                    logger.warning("进程异常退出，重新启动...")
                    self.start_backend()

                # 进程健康
                else:
                    logger.debug(f"服务运行正常 (PID: {self.process.pid})")

                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("收到停止信号...")
                self.stop_backend()
                logger.info("服务管理器已停止")
                break
            except Exception as e:
                logger.error(f"监控异常: {e}")
                time.sleep(check_interval)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='MediaStation 服务管理器')
    parser.add_argument('--port', type=int, default=3001, help='服务端口')
    parser.add_argument('--interval', type=int, default=30, help='检查间隔(秒)')
    args = parser.parse_args()

    manager = ServiceManager(args.port)
    manager.run(args.interval)
