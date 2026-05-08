# ============================================================
#  MediaStation 后端 Docker 构建 - 超轻量版
#  目标大小: 400-500MB
#
#  构建命令:
#    docker build -t shukebta/mediastation-backend:latest -f docker/Dockerfile .
# ============================================================

# ── Stage 1: 前端构建 ──
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com || npm install --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# ── Stage 2: 后端运行 ──
FROM python:3.11-slim-bookworm

LABEL maintainer="MediaStation"
LABEL description="MediaStation Backend"

# 更换为清华Debian镜像源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端应用
COPY backend/app/ ./app/

# 复制前端构建产物
COPY --from=frontend-builder /build/frontend/dist ./static

# 清理不必要文件
RUN find /usr/local/lib/python3.11/site-packages -name "test*" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete 2>/dev/null || true

# 创建数据目录
RUN mkdir -p /data && chmod 755 /data

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    TZ=Asia/Shanghai

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3001/api/system/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
