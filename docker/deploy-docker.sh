#!/bin/bash
# ===========================================
# MediaStation Docker 一键部署脚本
# ===========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_DIR/docker"

echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}   MediaStation Docker 部署脚本${NC}"
echo -e "${BLUE}===========================================${NC}"
echo

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

# Docker Compose 命令
DOCKER_COMPOSE="docker-compose"
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
fi

# 创建必要目录
echo -e "${YELLOW}[1/5] 创建必要目录...${NC}"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/media"
mkdir -p "$PROJECT_DIR/downloads"
mkdir -p "$DOCKER_DIR/license_data"
mkdir -p "$DOCKER_DIR/config/qbittorrent"
echo -e "${GREEN}✓ 目录创建完成${NC}"

# 检查 .env 文件
echo -e "${YELLOW}[2/5] 检查配置文件...${NC}"
if [ ! -f "$DOCKER_DIR/.env" ]; then
    if [ -f "$DOCKER_DIR/.env.template" ]; then
        echo -e "${YELLOW}未找到 .env 文件，正在从模板创建...${NC}"
        cp "$DOCKER_DIR/.env.template" "$DOCKER_DIR/.env"
        echo -e "${RED}请编辑 $DOCKER_DIR/.env 文件配置必填项！${NC}"
        echo -e "${YELLOW}必填项:${NC}"
        echo "  - APP_SECRET_KEY"
        echo "  - TMDB_API_KEY"
        echo "  - LICENSE_ADMIN_API_KEY"
        echo "  - LICENSE_HMAC_SECRET"
        exit 1
    else
        echo -e "${RED}错误: 未找到 .env.template${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ 配置文件检查完成${NC}"

# 生成随机密钥（如果需要）
echo -e "${YELLOW}[3/5] 检查安全密钥...${NC}"
cd "$DOCKER_DIR"

# 检查并生成 APP_SECRET_KEY
if grep -q "change-me-to" .env 2>/dev/null; then
    echo -e "${YELLOW}检测到未配置的安全密钥，正在生成...${NC}"
    
    if command -v openssl &> /dev/null; then
        NEW_SECRET=$(openssl rand -hex 32)
        sed -i "s/APP_SECRET_KEY=change-me-to-a-random-secret-key-min-32-chars/APP_SECRET_KEY=$NEW_SECRET/" .env
        echo -e "${GREEN}✓ APP_SECRET_KEY 已生成${NC}"
    fi
    
    if grep -q "LICENSE_ADMIN_API_KEY=change-me" .env 2>/dev/null; then
        NEW_ADMIN_KEY=$(openssl rand -hex 32)
        sed -i "s/LICENSE_ADMIN_API_KEY=change-me-to-a-random-admin-key/LICENSE_ADMIN_API_KEY=$NEW_ADMIN_KEY/" .env
        echo -e "${GREEN}✓ LICENSE_ADMIN_API_KEY 已生成${NC}"
    fi
    
    if grep -q "LICENSE_HMAC_SECRET=change-me" .env 2>/dev/null; then
        NEW_HMAC=$(openssl rand -hex 32)
        sed -i "s/LICENSE_HMAC_SECRET=change-me-to-a-random-hmac-secret/LICENSE_HMAC_SECRET=$NEW_HMAC/" .env
        echo -e "${GREEN}✓ LICENSE_HMAC_SECRET 已生成${NC}"
    fi
fi

# 构建并启动
echo -e "${YELLOW}[4/5] 构建并启动容器...${NC}"
if [ "$1" == "fast" ]; then
    echo -e "${YELLOW}快速模式：跳过镜像构建${NC}"
else
    echo -e "${YELLOW}正在构建镜像 (可能需要几分钟)...${NC}"
    $DOCKER_COMPOSE build
fi

echo -e "${YELLOW}正在启动容器...${NC}"
$DOCKER_COMPOSE up -d
echo -e "${GREEN}✓ 容器启动完成${NC}"

# 等待服务就绪
echo -e "${YELLOW}[5/5] 检查服务状态...${NC}"
sleep 5

echo
echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}   部署完成！${NC}"
echo -e "${BLUE}===========================================${NC}"
echo
echo -e "服务地址:"
echo -e "  ${GREEN}后端 API${NC}:   http://localhost:3002"
echo -e "  ${GREEN}授权服务${NC}:   http://localhost:3001"
echo -e "  ${GREEN}qBittorrent${NC}: http://localhost:8080"
echo
echo -e "管理命令:"
echo -e "  ${YELLOW}查看日志${NC}:   $DOCKER_COMPOSE logs -f"
echo -e "  ${YELLOW}停止服务${NC}:   $DOCKER_COMPOSE down"
echo -e "  ${YELLOW}重启服务${NC}:   $DOCKER_COMPOSE restart"
echo -e "  ${YELLOW}更新部署${NC}:   ./deploy-docker.sh"
echo
echo -e "${YELLOW}请访问 http://localhost:3002 开始使用！${NC}"
