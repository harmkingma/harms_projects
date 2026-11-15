@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venvs\esphome\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Shared ESPHome environment is missing. Run tools\setup.cmd esphome.
    exit /b 1
)
if not defined ESPHOME_ESP_IDF_PREFIX set "ESPHOME_ESP_IDF_PREFIX=C:\esphome-idf"
if exist "%USERPROFILE%\.certs\ca-bundle.pem" (
    set "REQUESTS_CA_BUNDLE=%USERPROFILE%\.certs\ca-bundle.pem"
    set "SSL_CERT_FILE=%USERPROFILE%\.certs\ca-bundle.pem"
)
"%PYTHON%" -m esphome %*
exit /b %ERRORLEVEL%
