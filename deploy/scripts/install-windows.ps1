# ============================================================
#  MediaStation — Windows 一键安装脚本
#  支持: Windows 10/11, Windows Server 2019+
#  用法: 以管理员身份运行 PowerShell
#  Invoke-WebRequest -Uri "https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-windows.ps1" -OutFile install-mediasation.ps1
#  .\install-mediasation.ps1
# ============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── 配置 ──
$ErrorActionPreference = "Stop"
$INSTALL_DIR = "$env:ProgramData\MediaStation"
$DATA_DIR = "$env:USERPROFILE\MediaStation"
$VERSION = "latest"
$PORT = 3001

# ── 颜色输出 ──
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ── 检查管理员权限 ──
function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ── 安装 Docker Desktop ──
function Install-Docker {
    Write-Info "检查 Docker..."

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Warn "Docker 未安装，正在安装 Docker Desktop..."

        # 下载 Docker Desktop 安装包
        $installerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        $installerPath = "$env:TEMP\DockerDesktopInstaller.exe"

        Write-Info "下载 Docker Desktop..."
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath

        Write-Info "安装 Docker Desktop (需要管理员权限)..."
        Start-Process -FilePath $installerPath -ArgumentList "install", "--quiet", "--accept-license" -Wait

        Write-Info "请重启计算机后重新运行此脚本"
        exit 1
    }

    # 检查 Docker 服务
    $dockerService = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($dockerService.Status -ne "Running") {
        Write-Info "启动 Docker 服务..."
        Start-Service Docker
    }

    Write-Success "Docker 已就绪"
}

# ── 创建目录 ──
function New-Directories {
    Write-Info "创建目录..."

    New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
    New-Item -ItemType Directory -Force -Path "$DATA_DIR\media\movies" | Out-Null
    New-Item -ItemType Directory -Force -Path "$DATA_DIR\media\tv" | Out-Null
    New-Item -ItemType Directory -Force -Path "$DATA_DIR\media\anime" | Out-Null
    New-Item -ItemType Directory -Force -Path "$DATA_DIR\downloads" | Out-Null
    New-Item -ItemType Directory -Force -Path "$DATA_DIR\logs" | Out-Null

    Write-Success "目录创建完成: $DATA_DIR"
}

# ── 下载配置 ──
function Initialize-Configs {
    Write-Info "下载配置文件..."

    # 下载 docker-compose.yml
    $composeUrl = "https://raw.githubusercontent.com/your-repo/mediastation/main/docker-compose.example.yml"
    $composePath = "$INSTALL_DIR\docker-compose.yml"

    if (-not (Test-Path $composePath)) {
        Invoke-WebRequest -Uri $composeUrl -OutFile $composePath
    }

    # 下载 .env.example 并创建 .env
    $envPath = "$INSTALL_DIR\.env"
    if (-not (Test-Path $envPath)) {
        $envExampleUrl = "https://raw.githubusercontent.com/your-repo/mediastation/main/.env.example"
        Invoke-WebRequest -Uri $envExampleUrl -OutFile "$INSTALL_DIR\.env.example"
        Copy-Item "$INSTALL_DIR\.env.example" $envPath
    }

    Write-Success "配置文件已准备"
}

# ── 配置环境变量 ──
function Set-Environment {
    Write-Info "配置环境变量..."

    # 读取现有 .env
    $envPath = "$INSTALL_DIR\.env"
    $envContent = Get-Content $envPath -Raw

    # TMDb API Key
    Write-Host ""
    $tmdbKey = Read-Host "请输入 TMDb API Key (必填，获取地址: https://www.themoviedb.org/settings/api)"
    if ($tmdbKey) {
        $envContent = $envContent -replace "TMDB_API_KEY=", "TMDB_API_KEY=$tmdbKey"
    }

    # JWT 密钥
    $secretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 64 | ForEach-Object {[char]$_})
    $envContent = $envContent -replace "APP_SECRET_KEY=.*", "APP_SECRET_KEY=$secretKey"

    # 数据目录
    $envContent = $envContent -replace "DATA_DIR=.*", "DATA_DIR=$DATA_DIR"

    # 端口
    $envContent = $envContent -replace "APP_PORT=.*", "APP_PORT=$PORT"

    # 写回 .env
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8

    Write-Success "环境变量配置完成"
}

# ── 启动服务 ──
function Start-Service {
    Write-Info "启动 MediaStation..."

    Set-Location $INSTALL_DIR

    # 检查并拉取镜像
    Write-Info "拉取 Docker 镜像 (首次可能需要几分钟)..."
    docker compose pull

    # 构建并启动
    Write-Info "构建并启动容器..."
    docker compose up -d --build

    # 等待服务启动
    Write-Info "等待服务启动..."
    $maxRetries = 30
    $retry = 0
    while ($retry -lt $maxRetries) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$PORT/api/system/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "服务启动成功!"
                return
            }
        } catch {}
        Start-Sleep -Seconds 2
        $retry++
    }

    Write-Error "服务启动超时，请检查日志: docker compose logs"
}

# ── 创建快捷方式 ──
function New-Shortcut {
    Write-Info "创建桌面快捷方式..."

    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\MediaStation.lnk")
    $Shortcut.TargetPath = "http://localhost:$PORT"
    $Shortcut.Description = "MediaStation Media Server"
    $Shortcut.Save()

    Write-Success "快捷方式已创建"
}

# ── 创建启动脚本 ──
function New-StartupScript {
    Write-Info "创建启动脚本..."

    $startupScript = "$INSTALL_DIR\start.bat"
    @"
@echo off
title MediaStation
cd /d "$INSTALL_DIR"
docker compose up -d
echo MediaStation 已启动，请访问 http://localhost:$PORT
pause
"@ | Out-File -FilePath $startupScript -Encoding ASCII

    $stopScript = "$INSTALL_DIR\stop.bat"
    @"
@echo off
title MediaStation
cd /d "$INSTALL_DIR"
docker compose down
echo MediaStation 已停止
pause
"@ | Out-File -FilePath $stopScript -Encoding ASCII

    Write-Success "启动脚本已创建: $INSTALL_DIR"
}

# ── 主函数 ──
function Main {
    Clear-Host
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  MediaStation Windows 安装脚本" -ForegroundColor Cyan
    Write-Host "  版本: $VERSION" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    # 检查管理员权限
    if (-not (Test-Admin)) {
        Write-Error "请以管理员身份运行此脚本!"
        Write-Host "右键点击 PowerShell，选择'以管理员身份运行'"
        exit 1
    }

    # 检查 Docker
    Install-Docker

    # 创建目录
    New-Directories

    # 下载配置
    Initialize-Configs

    # 配置环境变量
    Set-Environment

    # 启动服务
    Start-Service

    # 创建快捷方式
    New-Shortcut
    New-StartupScript

    # 完成信息
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  MediaStation 安装完成!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "访问地址: http://localhost:$PORT" -ForegroundColor Cyan
    Write-Host "默认账号: admin / admin123" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "配置文件: $INSTALL_DIR\docker-compose.yml" -ForegroundColor Gray
    Write-Host "数据目录: $DATA_DIR" -ForegroundColor Gray
    Write-Host ""
    Write-Host "常用命令:" -ForegroundColor Yellow
    Write-Host "  启动: $INSTALL_DIR\start.bat" -ForegroundColor Gray
    Write-Host "  停止: $INSTALL_DIR\stop.bat" -ForegroundColor Gray
    Write-Host "  日志: docker compose -f $INSTALL_DIR\docker-compose.yml logs -f" -ForegroundColor Gray
    Write-Host ""
    Write-Host "请登录后立即修改默认密码!" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""

    # 打开浏览器
    Start-Process "http://localhost:$PORT"
}

Main
