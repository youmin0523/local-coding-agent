@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   lca - 웹 UI 시작
echo   (먼저 LM Studio 서버를 켜 두세요)
echo ============================================
echo.
set /p PROJ="작업할 프로젝트 폴더 경로 (그냥 Enter = 이 폴더): "
if "%PROJ%"=="" set "PROJ=%~dp0"
echo.
echo 브라우저가 자동으로 열립니다... (창을 닫으면 종료)
uv run lca web -C "%PROJ%"
pause
