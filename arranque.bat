@echo off
setlocal EnableExtensions

set "ROOT="
set "TRY=%~dp0"
if exist "%TRY%frontend\package.json" if exist "%TRY%backend\requirements.txt" set "ROOT=%TRY%"

if not defined ROOT (
  set "TRY=%CD%\"
  if exist "%TRY%frontend\package.json" if exist "%TRY%backend\requirements.txt" set "ROOT=%TRY%"
)

if not defined ROOT (
  for %%I in ("%CD%\..") do set "TRY=%%~fI\"
  if exist "%TRY%frontend\package.json" if exist "%TRY%backend\requirements.txt" set "ROOT=%TRY%"
)

if not defined ROOT (
  echo [ERROR] No se encontro la estructura del proyecto.
  echo [INFO] Debe existir:
  echo        frontend\package.json
  echo        backend\requirements.txt
  echo [INFO] Ruta del script: %~dp0
  echo [INFO] Carpeta actual:  %CD%
  exit /b 1
)

set "FRONTEND_DIR=%ROOT%frontend"
set "BACKEND_DIR=%ROOT%backend"
set "BACKEND_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "PREPARE_ONLY=0"

if /I "%~1"=="--check" (
  echo [OK] Raiz detectada: %ROOT%
  echo [OK] Frontend: %FRONTEND_DIR%
  echo [OK] Backend:  %BACKEND_DIR%
  exit /b 0
)

if /I "%~1"=="--prepare-only" (
  set "PREPARE_ONLY=1"
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm no esta disponible en PATH.
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] python no esta disponible en PATH.
  exit /b 1
)

echo [OK] Raiz detectada: %ROOT%
echo [INFO] Frontend: %FRONTEND_DIR%
echo [INFO] Backend:  %BACKEND_DIR%

echo [1/3] Analizando dependencias de frontend...
pushd "%FRONTEND_DIR%"
set "FRONTEND_NEEDS_INSTALL=0"
if not exist "node_modules" (
  set "FRONTEND_NEEDS_INSTALL=1"
) else (
  call npm ls --depth=0 >nul 2>&1
  if errorlevel 1 set "FRONTEND_NEEDS_INSTALL=1"
)

if "%FRONTEND_NEEDS_INSTALL%"=="1" (
  echo [INFO] Instalando/actualizando dependencias de frontend...
  call npm install
  if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de frontend.
    popd
    exit /b 1
  )
) else (
  echo [OK] Frontend sin dependencias faltantes.
)
popd

echo [2/3] Analizando dependencias de backend...
if not exist "%BACKEND_PY%" (
  echo [INFO] Creando entorno virtual de backend...
  python -m venv "%BACKEND_DIR%\.venv"
  if errorlevel 1 (
    echo [ERROR] No se pudo crear .venv para backend.
    exit /b 1
  )
)

set "BACKEND_NEEDS_INSTALL=0"
if not exist "%BACKEND_DIR%\.deps.stamp" (
  set "BACKEND_NEEDS_INSTALL=1"
)

if "%BACKEND_NEEDS_INSTALL%"=="0" (
  call "%BACKEND_PY%" -c "import importlib.util,sys;mods=['fastapi','uvicorn','pydantic','multipart','numpy','requests','faiss'];missing=[m for m in mods if importlib.util.find_spec(m) is None];sys.exit(1 if missing else 0)" >nul 2>&1
  if errorlevel 1 set "BACKEND_NEEDS_INSTALL=1"
)

if "%BACKEND_NEEDS_INSTALL%"=="0" (
  for %%A in ("%BACKEND_DIR%\requirements.txt") do set "REQ_TIME=%%~tA"
  set "STAMP_TIME="
  set /p STAMP_TIME=<"%BACKEND_DIR%\.deps.stamp"
  if not "%REQ_TIME%"=="%STAMP_TIME%" set "BACKEND_NEEDS_INSTALL=1"
)

if "%BACKEND_NEEDS_INSTALL%"=="1" (
  echo [INFO] Instalando/actualizando dependencias de backend...
  call "%BACKEND_PY%" -m pip install --upgrade pip >nul
  call "%BACKEND_PY%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
  if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de backend.
    exit /b 1
  )
  for %%A in ("%BACKEND_DIR%\requirements.txt") do >"%BACKEND_DIR%\.deps.stamp" echo %%~tA
) else (
  echo [OK] Backend sin dependencias faltantes.
)

echo [3/3] Dependencias listas.

if "%PREPARE_ONLY%"=="1" (
  echo [OK] Modo prepare-only completado.
  exit /b 0
)

echo [INFO] Iniciando backend en una ventana nueva...
start "Backend CE ICCD" cmd /k "cd /d ""%BACKEND_DIR%"" && call "".venv\Scripts\activate.bat"" && uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload"

echo [INFO] Iniciando frontend en una ventana nueva...
start "Frontend CE ICCD" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

echo [OK] Servicios lanzados.
echo [INFO] Frontend: http://localhost:4321
echo [INFO] Backend:  http://localhost:8000
exit /b 0
