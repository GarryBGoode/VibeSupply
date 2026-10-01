# Runs tools/board_setup.py with KiCad's bundled Python.
# Usage:  .\tools\run_board_setup.ps1            # both boards
#         .\tools\run_board_setup.ps1 power      # one board
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
    & "$KiBin\python.exe" "$Root\tools\board_setup.py" @Boards
    if ($LASTEXITCODE -ne 0) { throw "board_setup.py failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
