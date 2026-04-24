@echo off
echo ================================================
echo  PDF 압축기 - 단일 .exe 빌드 (Ghostscript 포함)
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

pyinstaller --onefile --windowed ^
    --name "PDF압축기" ^
    --icon "assets\icon.ico" ^
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
echo  실행 파일: dist\PDF압축기.exe
echo ================================================
pause
