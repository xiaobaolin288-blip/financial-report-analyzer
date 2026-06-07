# Start Stock Finance desktop app (Python 3.10+)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    python -m venv .venv
    if (-not $?) {
        Write-Error "Python not found. Install from https://www.python.org/downloads/ and enable Add to PATH."
        exit 1
    }
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
if (-not $?) { exit 1 }

& $Python main.py
