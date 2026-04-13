@echo off
echo ================================================
echo  PDF 압축기 - 단일 .exe 빌드
echo ================================================
echo.

pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [오류] PyInstaller 설치 실패
    pause
    exit /b 1
)

pyinstaller --onefile --windowed ^
    --name "PDF압축기" ^
    --collect-all pymupdf ^
    --collect-all pikepdf ^
    --collect-data tkinterdnd2 ^
    --collect-binaries tkinterdnd2 ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import pikepdf._qpdf ^
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
