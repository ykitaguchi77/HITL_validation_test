# =============================================================================
#  HITL annotation experiment - server launcher (Plan A: shared-password auth)
#
#  How to use:
#    1) Edit $Pass below to your production password (shared with the annotators)
#    2) Run this file (double-click run_server.bat, or in a terminal: .\run_server.ps1)
#    3) A new window starts the API server (uvicorn); this window shows the public
#       URL  https://xxxxx.trycloudflare.com
#    4) Make each annotator's personal link and send it ONLY to that person:
#         python scripts\make_annotator_links.py --base-url https://xxxxx.trycloudflare.com
#       (+ username/password). Annotators never pick their ID: the link decides it.
#
#  Requirements (no GPU / torch needed: proposals are precomputed):
#    scripts/webapp/config/experiment.json   (python scripts/prepare_experiment.py)
#    outputs/proposals/proposals.json        (Eyelid_few_shot_HITL/scripts/eval/export_study_proposals.py)
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

# Wait for the server to start (loads experiment.json + proposals.json, verifies every item)
Start-Sleep -Seconds 4

# ---- 2) Start the Cloudflare tunnel (publishes the public URL) --------------
Write-Host "[*] Starting Cloudflare tunnel. Share the URL printed below" -ForegroundColor Cyan
Write-Host "    (https://xxxxx.trycloudflare.com) with the annotators." -ForegroundColor Cyan
Write-Host "    Username: $User   Password: (the value you set)" -ForegroundColor Green
Write-Host ""
cloudflared tunnel --url http://localhost:8000
