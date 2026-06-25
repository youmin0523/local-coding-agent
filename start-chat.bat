@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   lca - 터미널 채팅 시작
echo   (먼저 LM Studio 서버를 켜 두세요)
echo   종료: exit 입력 또는 Ctrl-C
echo ============================================
echo.
set /p PROJ="작업할 프로젝트 폴더 경로 (그냥 Enter = 이 폴더): "
if "%PROJ%"=="" set "PROJ=%~dp0"
echo.
uv run lca chat -C "%PROJ%"
pause
