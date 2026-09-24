param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$buildPath = Join-Path $projectRoot "build"
$distPath = Join-Path $projectRoot "dist"
$specPath = Join-Path $buildPath "spec"
$iconPath = Join-Path $projectRoot "assets\microled.ico"

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $buildPath, $distPath
}

if (-not (Test-Path $iconPath)) {
    uv run python (Join-Path $projectRoot "assets\generate_microled_icon.py")
}

uv run pyinstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "MicroLED-Lightbox-Generator" `
    --icon $iconPath `
    --paths $projectRoot `
    --distpath $distPath `
    --workpath $buildPath `
    --specpath $specPath `
    --exclude-module pyvista `
    --exclude-module vtk `
    --exclude-module matplotlib `
    --exclude-module pandas `
    --exclude-module scipy `
    --exclude-module jupyter `
    --exclude-module IPython `
    --exclude-module ansys.tools.visualization_interface `
    --copy-metadata ansys-tools-common `
    --copy-metadata ansys-speos-core `
    (Join-Path $projectRoot "main.py")

Write-Host "Created $distPath\MicroLED-Lightbox-Generator.exe"