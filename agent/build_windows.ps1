$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$AgentDir = Join-Path $ProjectRoot "agent"
$OutputDir = Join-Path $ProjectRoot "backend\downloads\agents"
$BuildDir = Join-Path $ProjectRoot "build\agent-windows"
$DistDir = Join-Path $ProjectRoot "dist\agent-build-windows"
$PythonExe = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "py"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

Push-Location $AgentDir
try {
    & $PythonExe -m pip show pyinstaller 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $PythonExe -m pip install pyinstaller
    }

    & $PythonExe -m PyInstaller `
        --onefile `
        --clean `
        --name agent-windows `
        --distpath $DistDir `
        --workpath $BuildDir `
        --specpath $BuildDir `
        agent.py

    $BuiltExe = Join-Path $DistDir "agent-windows.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "PyInstaller did not create $BuiltExe"
    }

    Copy-Item -Path $BuiltExe -Destination (Join-Path $OutputDir "agent-windows.exe") -Force
    Copy-Item -Path $BuiltExe -Destination (Join-Path $OutputDir "agent-windows-server.exe") -Force

    Write-Host "Built:"
    Get-ChildItem -Path $OutputDir -Filter "agent-windows*.exe" | Select-Object FullName,Length
}
finally {
    Pop-Location
}
