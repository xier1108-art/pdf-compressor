@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo  PDF 압축기 - 폴더형 빌드 (즉시 실행 / Ghostscript 포함)
echo ================================================
echo.

pip install pyinstaller --quiet

:: 이전 빌드 결과를 지우고 깨끗하게 다시 만든다 (안 지우면 결과 폴더가 계속 불어남)
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: 빌드 설정(Ghostscript 포함, 필요 없는 패키지 제외)은 PDF압축기.spec 에 있다
pyinstaller --noconfirm --clean "PDF압축기.spec"

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
