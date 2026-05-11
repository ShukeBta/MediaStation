# ===========================================
# MediaStation Docker 一键部署脚本 (Windows)
# ===========================================

$ErrorActionPreference = "Stop"

# 颜色定义
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    $colors = @{
        "Red" = [ConsoleColor]::Red
        "Green" = [ConsoleColor]::Green
        "Yellow" = [ConsoleColor]::Yellow
        "Blue" = [ConsoleColor]::Cyan
        "White" = [ConsoleColor]::White
    }
    Write-Host $Message -ForegroundColor $colors[$Color]
}

Write-ColorOutput "============================================" "Blue"
Write-ColorOutput "   MediaStation Docker 部署脚本" "Blue"
Write-ColorOutput "============================================" "Blue"
Write-Host ""

# 检查 Docker
Write-ColorOutput "[1/5] 检查 Docker..." "Yellow"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-ColorOutput "错误: Docker 未安装" "Red"
    exit 1
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-ColorOutput "错误: Docker 未运行" "Red"
    exit 1
}
Write-ColorOutput "✓ Docker 检查完成" "Green"

# 获取目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$DockerDir = $ScriptDir

# 创建必要目录
Write-ColorOutput "[2/5] 创建必要目录..." "Yellow"
$dirs = @("data", "media", "downloads", "$DockerDir\config")
foreach ($dir in $dirs) {
    $fullPath = Join-Path $ProjectDir $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-ColorOutput "✓ 目录创建完成" "Green"

# 检查 .env 文件
Write-ColorOutput "[3/5] 检查配置文件..." "Yellow"
$envFile = Join-Path $DockerDir ".env"
$envTemplate = Join-Path $DockerDir ".env.template"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envTemplate) {
        Write-ColorOutput "未找到 .env 文件，正在从模板创建..." "Yellow"
        Copy-Item $envTemplate $envFile
        Write-ColorOutput "请编辑 $envFile 文件配置必填项！" "Red"
        Write-ColorOutput "必填项:" "Yellow"
        Write-ColorOutput "  - APP_SECRET_KEY"
        Write-ColorOutput "  - TMDB_API_KEY"
        exit 1
    }
}
Write-ColorOutput "✓ 配置文件检查完成" "Green"

# 生成随机密钥（如果需要）
Write-ColorOutput "[4/5] 检查安全密钥..." "Yellow"

function Generate-RandomKey {
    return [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }) | Select-Object -First 32)
}

$envContent = Get-Content $envFile -Raw
if ($envContent -match "change-me") {
    Write-ColorOutput "检测到未配置的安全密钥，正在生成..." "Yellow"
    
    # 生成并替换密钥
    $newSecret = Generate-RandomKey
    $envContent = $envContent -replace "APP_SECRET_KEY=.*", "APP_SECRET_KEY=$newSecret"
    
    Set-Content -Path $envFile -Value $envContent
    Write-ColorOutput "✓ 安全密钥已生成" "Green"
}

# 构建并启动
Write-ColorOutput "[5/5] 构建并启动容器..." "Yellow"
Set-Location $DockerDir

# 检查 docker-compose 命令
$composeCmd = "docker-compose"
if (docker compose version 2>$null) {
    $composeCmd = "docker compose"
}

if ($args -contains "fast") {
    Write-ColorOutput "快速模式：跳过镜像构建" "Yellow"
} else {
    Write-ColorOutput "正在构建镜像 (可能需要几分钟)..." "Yellow"
    & $composeCmd build
}

Write-ColorOutput "正在启动容器..." "Yellow"
& $composeCmd up -d
Write-ColorOutput "✓ 容器启动完成" "Green"

# 等待服务就绪
Start-Sleep -Seconds 5

Write-Host ""
Write-ColorOutput "============================================" "Blue"
Write-ColorOutput "   部署完成！" "Blue"
Write-ColorOutput "============================================" "Blue"
Write-Host ""
Write-ColorOutput "服务地址:" "White"
Write-ColorOutput "  后端 API:   http://localhost:3002" "Green"
Write-ColorOutput "  qBittorrent: http://localhost:8080" "Green"
Write-Host ""
Write-ColorOutput "管理命令:" "White"
Write-ColorOutput "  查看日志:   docker compose logs -f" "Yellow"
Write-ColorOutput "  停止服务:   docker compose down" "Yellow"
Write-ColorOutput "  重启服务:   docker compose restart" "Yellow"
Write-Host ""
Write-ColorOutput "请访问 http://localhost:3002 开始使用！" "Yellow"
