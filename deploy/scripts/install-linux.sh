#!/bin/bash
# ============================================================
#  MediaStation — Linux 一键安装脚本
#  支持: Ubuntu / Debian / CentOS / Fedora / Arch
#  用法: curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install.sh | bash
# ============================================================

set -e

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── 日志函数 ──
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 配置变量 ──
INSTALL_DIR="/opt/mediastation"
DATA_DIR="/data/mediastation"
SERVICE_NAME="mediastation"
PORT=3001
VERSION="latest"

# ── 检测系统 ──
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION_ID=${VERSION_ID%%.*}
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    elif [ -f /etc/arch-release ]; then
        OS="arch"
    else
        OS="unknown"
    fi
    log_info "检测到操作系统: $OS"
}

# ── 检查依赖 ──
check_dependencies() {
    log_info "检查依赖..."

    local missing=()

    # Docker
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi

    # Docker Compose
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        missing+=("docker-compose")
    fi

    # curl
    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_warn "缺少以下依赖: ${missing[*]}"
        install_dependencies
    fi

    log_success "依赖检查完成"
}

# ── 安装依赖 ──
install_dependencies() {
    log_info "安装系统依赖..."

    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y curl ca-certificates gnupg lsb-release
            ;;
        fedora|rhel|centos)
            yum install -y curl ca-certificates
            ;;
        arch)
            pacman -Sy --noconfirm curl ca-certificates
            ;;
        *)
            log_warn "不支持的操作系统，请手动安装 Docker 和 Docker Compose"
            ;;
    esac

    # 安装 Docker
    if ! command -v docker &> /dev/null; then
        log_info "安装 Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl --user enable --now docker 2>/dev/null || systemctl enable --now docker
        usermod -aG docker $USER
    fi

    # 安装 Docker Compose
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        log_info "安装 Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi

    log_success "依赖安装完成"
}

# ── 创建目录 ──
create_directories() {
    log_info "创建目录..."

    sudo mkdir -p "$INSTALL_DIR"
    sudo mkdir -p "$DATA_DIR"
    sudo mkdir -p "$DATA_DIR/media/movies"
    sudo mkdir -p "$DATA_DIR/media/tv"
    sudo mkdir -p "$DATA_DIR/media/anime"
    sudo mkdir -p "$DATA_DIR/downloads"
    sudo mkdir -p "$DATA_DIR/logs"

    sudo chown -R $USER:$USER "$INSTALL_DIR" 2>/dev/null || true
    sudo chown -R $USER:$USER "$DATA_DIR"

    log_success "目录创建完成"
}

# ── 下载配置 ──
download_configs() {
    log_info "下载配置文件..."

    cd "$INSTALL_DIR"

    # 下载 docker-compose.yml
    if [ ! -f docker-compose.yml ]; then
        curl -fsSL "https://raw.githubusercontent.com/your-repo/mediastation/main/docker-compose.example.yml" -o docker-compose.yml
    fi

    # 下载 .env
    if [ ! -f .env ]; then
        curl -fsSL "https://raw.githubusercontent.com/your-repo/mediastation/main/.env.example" -o .env.example
        cp .env.example .env
    fi

    log_success "配置文件下载完成"
}

# ── 配置服务 ──
configure_service() {
    log_info "配置服务..."

    cd "$INSTALL_DIR"

    # 编辑 .env 文件
    echo ""
    echo "============================================"
    echo "  请配置以下环境变量:"
    echo "============================================"
    echo ""

    read -p "TMDb API Key (必填，获取地址: https://www.themoviedb.org/settings/api): " TMDB_KEY
    if [ -n "$TMDB_KEY" ]; then
        sed -i "s|TMDB_API_KEY=|TMDB_API_KEY=$TMDB_KEY|" .env
    fi

    read -p "JWT 密钥 (留空自动生成): " SECRET_KEY
    if [ -z "$SECRET_KEY" ]; then
        SECRET_KEY=$(openssl rand -hex 32)
    fi
    sed -i "s|APP_SECRET_KEY=.*|APP_SECRET_KEY=$SECRET_KEY|" .env

    # 设置数据目录
    sed -i "s|DATA_DIR=.*|DATA_DIR=$DATA_DIR|" .env

    # 设置端口
    sed -i "s|APP_PORT=.*|APP_PORT=$PORT|" .env

    log_success "服务配置完成"
}

# ── 启动服务 ──
start_service() {
    log_info "启动 MediaStation..."

    cd "$INSTALL_DIR"

    # 构建并启动
    docker compose up -d --build

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10

    # 检查健康状态
    for i in {1..30}; do
        if curl -sf http://localhost:$PORT/api/system/health > /dev/null 2>&1; then
            log_success "服务启动成功!"
            return 0
        fi
        sleep 2
    done

    log_error "服务启动超时，请检查日志: docker compose logs"
    return 1
}

# ── 创建 systemd 服务 ──
create_systemd_service() {
    log_info "创建 systemd 服务..."

    cat > /tmp/mediastation.service << EOF
[Unit]
Description=MediaStation Media Server
Requires=docker.service
After=docker.service
Requires=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    sudo mv /tmp/mediastation.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable mediastation

    log_success "systemd 服务创建完成"
}

# ── 防火墙配置 ──
configure_firewall() {
    if command -v ufw &> /dev/null; then
        log_info "配置 UFW 防火墙..."
        sudo ufw allow $PORT/tcp comment "MediaStation"
        sudo ufw reload
    elif command -v firewall-cmd &> /dev/null; then
        log_info "配置 firewalld..."
        sudo firewall-cmd --permanent --add-port=$PORT/tcp
        sudo firewall-cmd --reload
    fi
}

# ── 打印完成信息 ──
print_completion() {
    echo ""
    echo "============================================"
    echo "  MediaStation 安装完成!"
    echo "============================================"
    echo ""
    echo "访问地址: http://$(hostname -I | awk '{print $1}'):$PORT"
    echo "默认账号: admin / admin123"
    echo ""
    echo "常用命令:"
    echo "  查看状态: cd $INSTALL_DIR && docker compose ps"
    echo "  查看日志: cd $INSTALL_DIR && docker compose logs -f"
    echo "  停止服务: cd $INSTALL_DIR && docker compose down"
    echo "  重启服务: cd $INSTALL_DIR && docker compose restart"
    echo ""
    echo "配置文件: $INSTALL_DIR/docker-compose.yml"
    echo "数据目录: $DATA_DIR"
    echo ""
    echo "请登录后立即修改默认密码!"
    echo "============================================"
    echo ""
}

# ── 主函数 ──
main() {
    echo ""
    echo "============================================"
    echo "  MediaStation Linux 安装脚本"
    echo "  版本: $VERSION"
    echo "============================================"
    echo ""

    detect_os
    check_dependencies
    create_directories
    download_configs
    configure_service
    start_service

    # 可选: systemd 服务
    if command -v systemctl &> /dev/null; then
        read -p "是否创建 systemd 服务以便开机自启? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_systemd_service
            configure_firewall
        fi
    fi

    print_completion
}

main "$@"
