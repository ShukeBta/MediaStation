#!/bin/bash
# MediaStation 后端启动脚本 - 带自动重启守护

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/backend" && pwd)"
PID_FILE="$BACKEND_DIR/.backend.pid"
LOG_FILE="$BACKEND_DIR/logs/backend.log"
ERR_FILE="$BACKEND_DIR/logs/backend.err"

# 确保日志目录存在
mkdir -p "$BACKEND_DIR/logs"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 停止后端
stop_backend() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止后端进程 (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null
            sleep 2
            # 如果还在运行，强制杀死
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "进程未响应，强制终止..."
                kill -9 "$pid" 2>/dev/null
            fi
            log_info "后端已停止"
        fi
        rm -f "$PID_FILE"
    else
        # 尝试查找并杀死占用 3001 端口的进程
        local port_pid=$(netstat -ano 2>/dev/null | grep ':3001' | grep 'LISTENING' | awk '{print $NF}' | head -1)
        if [ -n "$port_pid" ]; then
            log_warn "发现端口 3001 被进程 $port_pid 占用，正在终止..."
            taskkill //F //PID "$port_pid" 2>/dev/null
        fi
    fi
}

# 启动后端
start_backend() {
    log_info "正在启动 MediaStation 后端..."
    log_info "工作目录: $BACKEND_DIR"
    
    cd "$BACKEND_DIR"
    
    # 检查 Python 是否可用
    if ! command -v python &> /dev/null; then
        log_error "Python 未找到！请检查 Python 安装"
        exit 1
    fi
    
    # 检查依赖
    log_info "检查 Python 依赖..."
    python -c "import uvicorn, fastapi, sqlalchemy" 2>/dev/null
    if [ $? -ne 0 ]; then
        log_warn "部分依赖缺失，正在安装..."
        pip install -r requirements.txt
    fi
    
    # 启动 uvicorn（带 --reload 支持热重载）
    nohup python -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 3001 \
        --reload \
        > "$LOG_FILE" 2> "$ERR_FILE" &
    
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    log_info "后端已启动 (PID: $pid)"
    log_info "日志文件: $LOG_FILE"
    log_info "错误日志: $ERR_FILE"
    
    # 等待并验证启动
    sleep 3
    if kill -0 "$pid" 2>/dev/null; then
        # 检查端口是否监听
        local retries=0
        while [ $retries -lt 10 ]; do
            if netstat -ano 2>/dev/null | grep -q ':3001.*LISTENING'; then
                log_info "✅ 后端启动成功！监听端口 3001"
                return 0
            fi
            sleep 1
            retries=$((retries + 1))
        done
        log_warn "⚠️  进程已启动但端口未监听，请检查日志"
        tail -20 "$ERR_FILE"
    else
        log_error "❌ 后端启动失败！"
        tail -50 "$ERR_FILE"
        return 1
    fi
}

# 重启后端
restart_backend() {
    log_info "重启后端..."
    stop_backend
    sleep 1
    start_backend
}

# 查看状态
status_backend() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "✅ 后端正在运行 (PID: $pid)"
            log_info "端口监听: $(netstat -ano 2>/dev/null | grep ':3001' | grep 'LISTENING' | wc -l) 个"
            return 0
        else
            log_warn "⚠️  PID 文件存在但进程未运行"
            rm -f "$PID_FILE"
        fi
    fi
    
    # 检查端口
    if netstat -ano 2>/dev/null | grep -q ':3001.*LISTENING'; then
        log_info "✅ 端口 3001 正在监听（但 PID 文件缺失）"
        return 0
    fi
    
    log_error "❌ 后端未运行"
    return 1
}

# 查看日志
view_logs() {
    if [ -f "$LOG_FILE" ]; then
        log_info "显示最近 50 行日志:"
        tail -50 "$LOG_FILE"
    fi
    if [ -f "$ERR_FILE" ]; then
        log_warn "显示最近 20 行错误日志:"
        tail -20 "$ERR_FILE"
    fi
}

# 守护模式 - 自动重启
daemon_mode() {
    log_info "进入守护模式（自动重启）..."
    log_info "按 Ctrl+C 退出"
    
    while true; do
        if ! status_backend &> /dev/null; then
            log_warn "检测到后端未运行，正在重启..."
            start_backend
            
            # 等待 5 秒再检查，避免频繁重启
            sleep 5
        fi
        
        # 每 10 秒检查一次
        sleep 10
    done
}

# 主逻辑
case "$1" in
    start)
        start_backend
        ;;
    stop)
        stop_backend
        ;;
    restart)
        restart_backend
        ;;
    status)
        status_backend
        ;;
    logs)
        view_logs
        ;;
    daemon)
        daemon_mode
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs|daemon}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动后端服务"
        echo "  stop    - 停止后端服务"
        echo "  restart - 重启后端服务"
        echo "  status  - 查看运行状态"
        echo "  logs    - 查看最新日志"
        echo "  daemon  - 守护模式（自动重启）"
        exit 1
        ;;
esac

exit 0
