# ============================================================
#  MediaStation — 多平台 Docker 构建
#  支持 linux/amd64, linux/arm64/v8
# ============================================================

# ── 多平台基础镜像 ──
# 使用 buildx 构建时指定平台
# docker buildx build --platform linux/amd64,linux/arm64/v8 -t mediastation:latest .

# ── Stage 1: 前端构建 ──
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# 先拷贝依赖文件，利用 Docker 缓存层
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --registry=https://registry.npmmirror.com

# 拷贝前端源码并构建
COPY frontend/ ./
RUN npm run build


# ── Stage 2: 后端运行 ──
FROM python:3.11-slim

LABEL maintainer="MediaStation"
LABEL description="Lightweight Home Media Server"
LABEL org.opencontainers.image.source="https://github.com/your-repo/mediastation"

# 系统依赖（FFmpeg + curl 健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    # 字体支持（字幕渲染）
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建非 root 用户（安全最佳实践）
RUN groupadd --gid 1000 mediastation \
    && useradd --uid 1000 --gid mediastation --shell /bin/bash --create-home mediastation

WORKDIR /app

# Python 依赖（先拷贝 requirements.txt 利用缓存）
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝后端源码
COPY backend/ ./

# 从 Stage 1 拷贝前端构建产物到 static 目录
COPY --from=frontend-builder /build/frontend/dist ./static

# 数据目录
RUN mkdir -p /data && chown -R mediastation:mediastation /data

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    TZ=Asia/Shanghai \
    # 安全：使用非 root 用户运行
    PYTHONUSERBASE=/app/.python \
    HOME=/home/mediastation

# 切换到非 root 用户
USER mediastation

# 暴露端口
EXPOSE 3001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3001/api/system/health || exit 1

# 启动（使用单 worker，容器环境足够了）
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
