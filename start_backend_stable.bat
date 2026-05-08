@echo off
chcp 65001 >nul
echo ================================================
echo    MediaStation 后端服务启动脚本
echo ================================================
echo.

cd /d "%~dp0backend"

echo [%time%] 正在启动后端服务...
start "MediaStation-Backend" python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --log-level info

echo [%time%] 等待服务启动...
timeout /t 5 /nobreak >nul

echo [%time%] 验证服务状态...
netstat -ano | findstr ":3001" | findstr "LISTENING"
if %errorlevel%==0 (
    echo.
    echo ================================================
    echo    ✅ 服务启动成功！
    echo    访问地址: http://localhost:3001
    echo ================================================
) else (
    echo.
    echo ================================================
    echo    ❌ 服务启动失败，请检查日志
    echo ================================================
)
echo.
pause
