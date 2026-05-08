#!/bin/bash
# ===========================================
# Docker 镜像安全检查
# 确保没有敏感信息被打包进镜像
# ===========================================

set -e

IMAGE_NAME=$1
if [ -z "$IMAGE_NAME" ]; then
    echo "Usage: $0 <image-name>"
    echo "Example: $0 mediastation-backend:latest"
    exit 1
fi

echo "=========================================="
echo "🔍 检查 Docker 镜像: $IMAGE_NAME"
echo "=========================================="

# 1. 检查环境变量
echo -e "\n[1] 检查环境变量..."
docker run --rm --entrypoint printenv "$IMAGE_NAME" 2>/dev/null | \
    grep -i -E "(key|secret|password|token|cookie)" || echo "  ✅ 无敏感环境变量"

# 2. 检查文件系统
echo -e "\n[2] 检查文件系统..."
docker run --rm --entrypoint find "$IMAGE_NAME" /app -type f -name ".env" 2>/dev/null || true
docker run --rm --entrypoint find "$IMAGE_NAME" /app -type f -name "*.env" 2>/dev/null || true
docker run --rm --entrypoint find "$IMAGE_NAME" /app -type f -name "cookies.txt" 2>/dev/null || true
docker run --rm --entrypoint find "$IMAGE_NAME" /app -type f -name "*.db" 2>/dev/null || true

# 3. 检查特定目录
echo -e "\n[3] 检查敏感目录..."
for dir in data cache downloads; do
    if docker run --rm --entrypoint ls "$IMAGE_NAME" /app/$dir 2>/dev/null; then
        echo "  ⚠️  $dir 目录存在（可能包含数据）"
    else
        echo "  ✅ $dir 目录不存在"
    fi
done

# 4. 检查历史命令
echo -e "\n[4] 检查镜像历史..."
docker history --no-trunc "$IMAGE_NAME" | \
    grep -i -E "(password|secret|key|token)" || echo "  ✅ 历史记录无敏感信息"

# 5. 检查镜像大小
echo -e "\n[5] 镜像信息..."
docker inspect "$IMAGE_NAME" --format='{{.Size}}' | \
    awk '{printf "  📦 镜像大小: %.2f MB\n", $1/1024/1024}'

echo -e "\n=========================================="
echo "✅ 检查完成！"
echo "=========================================="
echo -e "\n⚠️  重要提醒："
echo "1. 所有敏感配置必须通过环境变量注入"
echo "2. 用户应在 docker-compose.yml 中配置"
echo "3. 数据库文件不应在镜像中"

# 生成安全报告
cat > security-report.txt << EOF
# Docker 镜像安全检查报告
镜像: $IMAGE_NAME
检查时间: $(date)

## 检查结果
- [x] 环境变量检查
- [x] 文件系统检查
- [x] 敏感目录检查
- [x] 历史记录检查

## 安全建议
1. 使用环境变量注入所有敏感配置
2. 在 docker-compose.yml 中配置所有密码和 API Keys
3. 确保 .dockerignore 排除所有 .env 和 *.db 文件
4. 用户安装后通过 Web UI 配置站点信息
EOF

echo -e "\n📄 已生成安全报告: security-report.txt"
