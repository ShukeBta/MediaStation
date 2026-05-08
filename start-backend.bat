@echo off
REM MediaStation 后端启动脚本 for Windows
setlocal enabledelayedexpansion

set BACKEND_DIR=%~dp0backend
set LOG_FILE=%BACKEND_DIR%\logs\backend.log
set ERR_FILE=%BACKEND_DIR%\logs\backend.err
set PID_FILE=%BACKEND_DIR%\.backend.pid

REM 确保日志目录存在
if not exist "%BACKEND_DIR%\logs" mkdir "%BACKEND_DIR%\logs"

:print_info
echo [INFO] %~1
goto :eof

:print_warn
echo [WARN] %~1
goto :eof

:print_error
echo [ERROR] %~1
goto :eof

:stop_backend
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    if defined PID (
        tasklist /fi "PID eq !PID!" 2>nul | find "!PID!" >nul
        if !errorlevel! equ 0 (
            call :print_info "停止后端进程 (PID: !PID!)..."
            taskkill /F /PID !PID! >nul 2>&1
            timeout /t 2 /nobreak >nul
            call :print_info "后端已停止"
        )
    )
    del "%PID_FILE%" 2>nul
) else (
    REM 尝试查找并杀死占用 3001 端口的进程
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
        call :print_warn "发现端口 3001 被进程 %%a 占用，正在终止..."
        taskkill /F /PID %%a >nul 2>&1
    )
)
goto :eof

:start_backend
call :print_info "正在启动 MediaStation 后端..."
call :print_info "工作目录: %BACKEND_DIR%"

cd /d "%BACKEND_DIR%"

REM 检查 Python 是否可用
where python >nul 2>&1
if !errorlevel! neq 0 (
    call :print_error "Python 未找到！请检查 Python 安装"
    exit /b 1
)

REM 启动 uvicorn（后台运行）
start /b "" python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload > "%LOG_FILE%" 2> "%ERR_FILE%"

REM 等待获取进程 PID
timeout /t 2 /nobreak >nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
    set PID=%%a
    echo !PID! > "%PID_FILE%"
    call :print_info "后端已启动 (PID: !PID!)"
    call :print_info "日志文件: %LOG_FILE%"
    call :print_info "错误日志: %ERR_FILE%"
    goto :check_port
)

call :print_error "后端启动失败！查看错误日志:"
type "%ERR_FILE%" | more
exit /b 1

:check_port
REM 验证端口监听
timeout /t 3 /nobreak >nul
netstat -ano | findstr ":3001" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    call :print_info "✅ 后端启动成功！监听端口 3001"
    exit /b 0
) else (
    call :print_warn "⚠️  进程已启动但端口未监听，请检查日志"
    exit /b 1
)

:restart_backend
call :print_info "重启后端..."
call :stop_backend
timeout /t 1 /nobreak >nul
call :start_backend
goto :eof

:status_backend
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /fi "PID eq !PID!" 2>nul | find "!PID!" >nul
    if !errorlevel! equ 0 (
        call :print_info "✅ 后端正在运行 (PID: !PID!)"
        goto :eof
    ) else (
        call :print_warn "⚠️  PID 文件存在但进程未运行"
        del "%PID_FILE%" 2>nul
    )
)

netstat -ano | findstr ":3001" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    call :print_info "✅ 端口 3001 正在监听（但 PID 文件缺失）"
    goto :eof
)

call :print_error "❌ 后端未运行"
exit /b 1

:view_logs
if exist "%LOG_FILE%" (
    call :print_info "显示最近 50 行日志:"
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 50"
)
if exist "%ERR_FILE%" (
    call :print_warn "显示最近 20 行错误日志:"
    powershell -Command "Get-Content '%ERR_FILE%' -Tail 20"
)
goto :eof

:daemon_mode
call :print_info "进入守护模式（自动重启）..."
call :print_info "按 Ctrl+C 退出"

:daemon_loop
call :status_backend >nul 2>&1
if !errorlevel! neq 0 (
    call :print_warn "检测到后端未运行，正在重启..."
    call :start_backend
    timeout /t 5 /nobreak >nul
)
timeout /t 10 /nobreak >nul
goto :daemon_loop

:main
if "%~1"=="" goto :usage

if /i "%~1"=="start" (
    call :start_backend
) else if /i "%~1"=="stop" (
    call :stop_backend
) else if /i "%~1"=="restart" (
    call :restart_backend
) else if /i "%~1"=="status" (
    call :status_backend
) else if /i "%~1"=="logs" (
    call :view_logs
) else if /i "%~1"=="daemon" (
    call :daemon_mode
) else (
    goto :usage
)

goto :eof

:usage
echo 用法: %~nx0 {start^|stop^|restart^|status^|logs^|daemon}
echo.
echo 命令说明:
echo   start   - 启动后端服务
echo   stop    - 停止后端服务
echo   restart - 重启后端服务
echo   status  - 查看运行状态
echo   logs    - 查看最新日志
echo   daemon  - 守护模式（自动重启）
exit /b 1

:end
endlocal
