# =============================================================================
#  HITL annotation experiment - server launcher (Plan A: shared-password auth)
#
#  How to use:
#    1) Edit $Pass below to your production password (shared with the 3 annotators)
#    2) Run this file (double-click run_server.bat, or in a terminal: .\run_server.ps1)
#    3) A new window starts the API server (uvicorn); this window shows the public
#       URL  https://xxxxx.trycloudflare.com
#    4) Give that URL + username/password to the 3 annotators
#
#  Stop:
#    - Ctrl+C in this window      -> stop the tunnel (URL becomes invalid)
#    - Close the other window     -> stop the API server (uvicorn)
# =============================================================================

# ---- Credentials (CHANGE before sharing) -----------------------------------
$User = "annotator"
$Pass = "hitl"   # <- set your production password here

if ($Pass -eq "CHANGE_ME_BEFORE_SHARING") {
  Write-Host "[!] Password is still the default. Edit \$Pass before running." -ForegroundColor Yellow
  Read-Host "Press Enter to continue anyway (not recommended)"
}

# Export credentials as environment variables (inherited by the child uvicorn process)
$env:HITL_AUTH_USER = $User
$env:HITL_AUTH_PASS = $Pass

$Backend = Join-Path $PSScriptRoot "backend"

# ---- 1) Start the API server (uvicorn) in a new window ----------------------
Write-Host "[*] Starting API server (port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$Backend'; python -m uvicorn main:app --port 8000"
)

# Wait for the server to start and warm up the models
Start-Sleep -Seconds 8

# ---- 2) Start the Cloudflare tunnel (publishes the public URL) --------------
Write-Host "[*] Starting Cloudflare tunnel. Share the URL printed below" -ForegroundColor Cyan
Write-Host "    (https://xxxxx.trycloudflare.com) with the 3 annotators." -ForegroundColor Cyan
Write-Host "    Username: $User   Password: (the value you set)" -ForegroundColor Green
Write-Host ""
cloudflared tunnel --url http://localhost:8000
