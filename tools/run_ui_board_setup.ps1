# Runs tools/ui_board_setup.py (UI board outline, cutouts and panel-driven footprint placement from CAD_3D) and
# tools/snapshot.py (out/placement_ui.png) with KiCad's Python.
# Usage:  .\tools\run_ui_board_setup.ps1           # after every change of the panel design
#         .\tools\run_ui_board_setup.ps1 -Sync     # after every change of ui_design.py: first bring the board in line
#                                                  # with out/supply_ui.net (footprints, values, nets)
# The other footprints are arranged by  .\tools\run_place.ps1 ui
param([switch]$Sync)

$ErrorActionPreference = "Stop"
$KiBin = "C:\Program Files\KiCad\10.0\bin"
$Root = Split-Path $PSScriptRoot -Parent

# KiCad would overwrite the result when it saves -> refuse while pcbnew/kicad is open
$running = Get-Process -Name kicad, pcbnew -ErrorAction SilentlyContinue
if ($running) {
    Write-Error "KiCad is running ($($running.Name -join ', ')). Close it first."
}

# pcbnew's native module needs KiCad's bin dir on PATH to find its DLLs; drop any venv/user Python settings
$env:PATH = "$KiBin;$env:PATH"
Remove-Item Env:PYTHONPATH, Env:PYTHONHOME, Env:VIRTUAL_ENV -ErrorAction SilentlyContinue

$extra = @()
if ($Sync) { $extra += "sync" }

Push-Location $Root
try {
    & "$KiBin\python.exe" "$Root\tools\ui_board_setup.py" @extra
    if ($LASTEXITCODE -ne 0) { throw "ui_board_setup.py failed (exit $LASTEXITCODE)" }
    & "$KiBin\python.exe" "$Root\tools\snapshot.py" ui
    if ($LASTEXITCODE -ne 0) { throw "snapshot.py failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
