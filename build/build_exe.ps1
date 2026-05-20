$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$StaticDir = Join-Path $ProjectRoot "static"
$StaticAssetsDir = Join-Path $StaticDir "assets"
$SpecPath = Join-Path $ProjectRoot "build\SystemMonitor.spec"
$WorkPath = Join-Path $ProjectRoot "build\pyinstaller-work"
$DistPath = Join-Path $ProjectRoot "dist"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Command,
        [Parameter(Mandatory = $true)]
        [string] $ErrorMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Не найдено backend\.venv. Создайте окружение и установите зависимости из backend\requirements.txt."
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    throw "Не найдено frontend\node_modules. Выполните npm install в папке frontend."
}

Push-Location $FrontendDir
try {
    Invoke-CheckedCommand { npm.cmd run build } "Не удалось собрать frontend через npm run build."
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $StaticAssetsDir | Out-Null
Get-ChildItem -Path $StaticAssetsDir -File -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -Path (Join-Path $FrontendDir "dist\index.html") -Destination (Join-Path $StaticDir "index.html") -Force
Copy-Item -Path (Join-Path $FrontendDir "dist\assets\*") -Destination $StaticAssetsDir -Force

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PythonExe -m pip show pyinstaller 1>$null 2>$null
$PyInstallerCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference

if ($PyInstallerCheckExitCode -ne 0) {
    Invoke-CheckedCommand { & $PythonExe -m pip install pyinstaller } "Не удалось установить PyInstaller."
}

Invoke-CheckedCommand {
    & $PythonExe -m PyInstaller $SpecPath --noconfirm --clean --distpath $DistPath --workpath $WorkPath
} "Не удалось собрать exe через PyInstaller."

$ExeDir = Join-Path $DistPath "SystemMonitor"
$ExeStaticDir = Join-Path $ExeDir "static"
$ExeDatabaseDir = Join-Path $ExeDir "database"

Copy-Item -Path (Join-Path $ProjectRoot "config.json") -Destination (Join-Path $ExeDir "config.json") -Force
New-Item -ItemType Directory -Force -Path $ExeStaticDir | Out-Null
Get-ChildItem -Path $ExeStaticDir -File -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -Path (Join-Path $StaticDir "*") -Destination $ExeStaticDir -Recurse -Force
New-Item -ItemType Directory -Force -Path $ExeDatabaseDir | Out-Null
Copy-Item -Path (Join-Path $ProjectRoot "database\.gitkeep") -Destination (Join-Path $ExeDatabaseDir ".gitkeep") -Force

Write-Host ""
Write-Host "Сборка завершена: $DistPath\SystemMonitor\SystemMonitor.exe"
Write-Host "config.json, static и database подготовлены рядом с exe."
