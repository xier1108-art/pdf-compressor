@echo off
echo ================================================
echo  PDF 압축기 - 폴더형 빌드 (즉시 실행 / Ghostscript 포함)
echo ================================================
echo.

pip install pyinstaller --quiet

:: Ghostscript 경로 자동 탐지
set GS_DIR=
for /d %%G in ("C:\Program Files\gs\gs*") do set GS_DIR=%%G
if "%GS_DIR%"=="" (
    echo [경고] Ghostscript를 찾을 수 없습니다.
    echo       Ghostscript 없이 빌드합니다 (PyMuPDF fallback 모드).
    echo.
    set ADD_GS=
) else (
    echo Ghostscript 감지: %GS_DIR%
    set ADD_GS=--add-data "%GS_DIR%;gs"
)

:: --onedir 로 빌드 (--onefile 대비 실행 시작 속도가 10배 이상 빠름)
:: --contents-directory=_internal 로 런타임 파일을 한 폴더에 모아 배포 용이
pyinstaller --onedir --windowed ^
    --name "PDF압축기" ^
    --icon "assets\icon.ico" ^
    --contents-directory "_internal" ^
    --collect-all pymupdf ^
    --collect-all pikepdf ^
    --collect-all PyQt6 ^
    %ADD_GS% ^
    app.py

if %errorlevel% neq 0 (
    echo.
    echo [오류] 빌드 실패
    pause
    exit /b 1
)

echo.
echo ================================================
echo  빌드 완료!
echo  실행 폴더: dist\PDF압축기\
echo  실행 파일: dist\PDF압축기\PDF압축기.exe
echo.
echo  배포 시: dist\PDF압축기 폴더 전체를 ZIP으로 묶어 배포
echo ================================================
pause
