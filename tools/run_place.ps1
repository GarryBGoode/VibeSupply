# Runs tools/place.py (floor plan + placement) and tools/snapshot.py (out/placement_<board>.png) with KiCad's Python.
# Usage:  .\tools\run_place.ps1            # both boards (power first: J971 follows J951)
#         .\tools\run_place.ps1 control    # one board
# Locked footprints (or footprints in a locked group) are not moved; everything else is re-placed.
param([string[]]$Boards)

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

Push-Location $Root
try {
    & "$KiBin\python.exe" "$Root\tools\place.py" @Boards
    if ($LASTEXITCODE -ne 0) { throw "place.py failed (exit $LASTEXITCODE)" }
    & "$KiBin\python.exe" "$Root\tools\snapshot.py" @Boards
    if ($LASTEXITCODE -ne 0) { throw "snapshot.py failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
