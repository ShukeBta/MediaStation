#!/bin/bash
# ============================================================
#  MediaStation — 群晖 SPK 套件打包脚本
#  用法: ./build-spk.sh
# ============================================================

set -e

VERSION="1.0.0"
PKG_NAME="MediaStation"
SPK_NAME="${PKG_NAME}-${VERSION}.spk"
BUILD_DIR="build-spk"

# 创建构建目录
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# ── 创建包结构 ──
echo "创建包结构..."

# 创建 INFO 文件（兼容 DSM 7.x 权限模型）
cat > INFO.json << 'EOF'
{
    "package": "MediaStation",
    "version": "1.0.0",
    "arch": ["noarch", "x86_64", "aarch64", "armv7l"],
    "description": "Lightweight Home Media Server",
    "maintainer": "MediaStation",
    "vendor": "MediaStation",
    "support_url": "https://github.com/your-repo/mediastation",
    "dsm_ui_compatibility": "7.0-",
    "distributor": "MediaStation",
    "distributor_url": "https://github.com/your-repo/mediastation",
    "startstop_priority": "100",
    "run_as": "package",
    "os_min_ver": "7.0-40000",
    "size": 500000000,
    "install_deprecated_packages": false,
    "install_conflict_packages": [],
    "install_required_packages": [],
    "install_recommended_packages": [],
    "install_suggested_packages": [],
    "dependencies": {},
    "conflicts": {},
    "thirdparty": false,
    "thumbnail": "images/INFO.png",
    "license": "MIT"
}
EOF

# 创建 PACKAGE_ICON 目录
mkdir -p PACKAGE_ICON
mkdir -p images
mkdir -p scripts
mkdir -p wizard

# ── 创建安装脚本 ──
cat > scripts/install << 'INSTALL_EOF'
#!/bin/bash

PACKAGE_NAME="MediaStation"
PACKAGE_DIR="/var/packages/${PACKAGE_NAME}"
SYNOPKG_PKGDEST="/var/packages/${PACKAGE_NAME}/target"

# 停止服务
service_stop () {
    /var/packages/${PACKAGE_NAME}/scripts/service-stop.sh
}

# 安装前
preinst () {
    exit 0
}

# 安装后
postinst () {
    # 创建符号链接
    mkdir -p ${SYNOPKG_PKGDEST}
    mkdir -p /var/packages/${PACKAGE_NAME}/target

    # 提取文件
    cd ${SYNOPKG_PKGDEST}
    tar -xzf ${SYNOPKG_PKGVOL}/package.tgz

    # 设置权限（DSM 7.x 必须使用 package 用户，禁止 root:root）
    chown -R MediaStation:MediaStation ${SYNOPKG_PKGDEST}
    chmod 755 ${SYNOPKG_PKGDEST}
    [ -d "${SYNOPKG_PKGDEST}/bin" ] && chmod +x ${SYNOPKG_PKGDEST}/bin/*

    # 创建数据目录（使用 package 用户权限）
    mkdir -p /var/packages/${PACKAGE_NAME}/var
    chown -R MediaStation:MediaStation /var/packages/${PACKAGE_NAME}/var
    chmod 755 /var/packages/${PACKAGE_NAME}/var

    # 启动 Docker
    /usr/syno/bin/synopkg start Docker

    exit 0
}
INSTALL_EOF

# ── 创建卸载脚本 ──
cat > scripts/delete << 'DELETE_EOF'
#!/bin/bash

PACKAGE_NAME="MediaStation"
PACKAGE_DIR="/var/packages/${PACKAGE_NAME}"

# 停止服务
service_stop () {
    /var/packages/${PACKAGE_NAME}/scripts/service-stop.sh
}

# 卸载前
preuninst () {
    service_stop
    exit 0
}

# 卸载后
postuninst () {
    # 保留数据目录
    exit 0
}
DELETE_EOF

# ── 创建服务脚本 ──
cat > scripts/service-stop.sh << 'STOP_EOF'
#!/bin/bash
PACKAGE_NAME="MediaStation"
cd /var/packages/${PACKAGE_NAME}/target
docker compose down 2>/dev/null || true
exit 0
STOP_EOF

cat > scripts/service-start.sh << 'START_EOF'
#!/bin/bash
PACKAGE_NAME="MediaStation"
cd /var/packages/${PACKAGE_NAME}/target
docker compose up -d
exit 0
START_EOF

cat > scripts/service-status.sh << 'STATUS_EOF'
#!/bin/bash
PACKAGE_NAME="MediaStation"
if docker ps --format '{{.Names}}' | grep -q "^${PACKAGE_NAME}"; then
    exit 0
else
    exit 1
fi
STATUS_EOF

chmod +x scripts/*

# ── 创建向导脚本 ──
cat > wizard/install_uiform << 'WIZARD_EOF'
#!/bin/bash

echo "package"
echo "1"

echo "dsm_version"
echo "7"

echo "section"
echo "TMDb Settings"

echo "TMDB_API_KEY"
echo ""
echo "TMDb API Key (必填)"
echo "Get from: https://www.themoviedb.org/settings/api"

echo "section"
echo "Storage"

echo "MEDIA_DIR"
echo "/volume1/media"
echo "Media Directory"

echo "DOWNLOAD_DIR"
echo "/volume1/downloads"
echo "Download Directory"
WIZARD_EOF

# ── 复制 Dockerfile 和配置 ──
cp ../docker-compose.example.yml docker-compose.yml
cp ../.env.example .env

# ── 打包 ──
echo "打包 SPK..."
tar -czf package.tgz \
    INFO.json \
    scripts/ \
    wizard/ \
    docker-compose.yml \
    .env \
    package/

# 清理
rm -rf INFO.json scripts wizard docker-compose.yml .env

echo "SPK 打包完成: $SPK_NAME"
