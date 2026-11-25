@echo off
setlocal
cd /d "%~dp0.."
echo ================================================
echo  HORIZON VOICE - PUBLICACAO NO GITHUB
echo ================================================
echo.
where git >nul 2>nul
if errorlevel 1 (
  echo ERRO: Git nao foi encontrado. Instale Git for Windows.
  echo https://git-scm.com/downloads
  pause
  exit /b 1
)
where gh >nul 2>nul
if errorlevel 1 (
  echo ERRO: GitHub CLI nao foi encontrado. Instale GitHub CLI.
  echo https://cli.github.com/
  pause
  exit /b 1
)

echo Pasta do projeto: %CD%
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish-to-github.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo A publicacao nao foi concluida. Codigo: %RESULT%
) else (
  echo Processo finalizado. Confira a mensagem acima e o repositorio no GitHub.
)
echo.
pause
exit /b %RESULT%
