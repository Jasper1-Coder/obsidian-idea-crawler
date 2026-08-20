@echo off
chcp 65001 >nul
REM ============================================================
REM  setup.bat —— obsidian-idea-crawler 一键安装（Windows）
REM  建 .venv + 装依赖 + 下载 ffmpeg 到 bin/
REM ============================================================
setlocal
set "SKILL_DIR=%~dp0"
cd /d "%SKILL_DIR%"

REM ---- 1. 选 python ----
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
echo [1/4] 使用 Python: %PY%

REM ---- 2. 建 venv ----
if not exist ".venv\" (
  %PY% -m venv .venv || (echo 创建 venv 失败，请确认已安装 Python 3.10+ & exit /b 1)
)
echo [2/4] venv 已就绪: .venv

REM ---- 3. 装依赖 ----
.venv\Scripts\python.exe -m pip install -U pip >nul 2>&1
.venv\Scripts\python.exe -m pip install -U yt-dlp httpx requests || (echo 依赖安装失败（检查网络）& exit /b 1)
echo [3/4] 依赖已装: yt-dlp / httpx / requests

REM ---- 4. 下载 ffmpeg ----
if not exist "bin\" mkdir bin
if exist "bin\ffmpeg.exe" (
  echo [4/4] ffmpeg 已存在，跳过下载
  goto DONE
)
echo [4/4] 下载 ffmpeg (gyan.dev) ...
curl -L -s -o bin\ffmpeg.zip "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
if exist "bin\ffmpeg.zip" (
  tar -xf bin\ffmpeg.zip -C bin >nul 2>&1
  for /r "bin" %%f in (ffmpeg.exe) do copy /Y "%%f" "bin\ffmpeg.exe" >nul 2>&1
  del /q bin\ffmpeg.zip >nul 2>&1
)
if exist "bin\ffmpeg.exe" (
  echo [4/4] ffmpeg 已就位: bin\ffmpeg.exe
) else (
  echo [4/4] ffmpeg 自动下载失败，请手动到 https://www.gyan.dev/ffmpeg/builds/ 下载，把 ffmpeg.exe 放到 bin\ 目录
)

:DONE
if not exist "cookies\" mkdir cookies
echo.
echo ============ 安装完成 ============
echo 下一步：把 cookie 放进 cookies/ 目录
echo   - cookies\xiaohongshu.txt  (小红书图文抓取必需)
echo   - cookies\douyin.txt       (抖音视频转写必需，B站不需要)
echo 再新建 .venv\.env 写入：SILICONFLOW_API_KEY=sk-你的key   （仅视频转写需要）
echo 然后直接在 WorkBuddy 里把链接发给我即可。
endlocal
