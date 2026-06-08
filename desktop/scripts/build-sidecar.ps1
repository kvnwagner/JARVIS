param(
    [string]$TargetTriple = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$Entry = Join-Path $ScriptDir "jarvis-api-sidecar.py"
$Name = "jarvis-api-sidecar-$TargetTriple"

Set-Location $Root
py -m pip install --upgrade pyinstaller
py -m PyInstaller --onefile --name $Name $Entry

$Exe = Join-Path $Root "dist\$Name.exe"
$Destination = Join-Path $ScriptDir "$Name.exe"
Copy-Item -Force $Exe $Destination
Write-Host "Sidecar listo: $Destination"
