# Start the Edezee API for local development on Windows (PowerShell).
#
# Mirror of run.sh: creates the venv on first use, installs dependencies, then
# serves on $env:PORT (default 8000). Set $env:DEMO_MODE="true" first to serve
# sample slides with no API key.
#
#   $env:DEMO_MODE = "true"; .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Windows venvs put the interpreter in Scripts\, POSIX ones in bin\. Detect
# rather than branch on the OS, so this also works under pwsh on macOS/Linux
# and under PowerShell 5.1, where $IsWindows is not defined.
function Find-VenvPython([string] $Venv) {
    foreach ($rel in @("Scripts\python.exe", "bin\python")) {
        $candidate = Join-Path $Venv $rel
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

$venv = Join-Path $PSScriptRoot ".venv"
$python = Find-VenvPython $venv

if (-not $python) {
    # The `py` launcher ships with python.org installs; fall back to `python`.
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 -m venv $venv
    } else {
        python -m venv $venv
    }
    $python = Find-VenvPython $venv
    if (-not $python) { throw "venv creation failed: no interpreter found under $venv" }
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $PSScriptRoot "requirements.txt")
}

$port = if ($env:PORT) { $env:PORT } else { "8000" }
& $python -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload
