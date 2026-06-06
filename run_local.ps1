# Okeder — lance toute la stack en local pour test temps reel.
# DB = Supabase (cloud), Redis = Upstash (cloud). Pas besoin de Docker.
# Usage : depuis okeder/  ->  ./run_local.ps1
# Ctrl+C dans chaque fenetre pour arreter. Ou ./run_local.ps1 -Stop

param([switch]$Stop)

$root    = $PSScriptRoot
$backend = Join-Path $root "backend"
$bot     = Join-Path $root "bot"
$py      = Join-Path $backend ".venv\Scripts\python.exe"
$cf      = Join-Path $backend "cloudflared.exe"

if ($Stop) {
    Write-Host "Arret des process Okeder..." -ForegroundColor Yellow
    Get-Process python, cloudflared -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "*Okeder*" -or $_.ProcessName -eq "cloudflared" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "OK." -ForegroundColor Green
    return
}

$env:PYTHONIOENCODING = "utf-8"

# 1) Tunnel Cloudflare -> backend:8000 (URL publique HTTPS, sans interstitiel)
Write-Host "1/4 Demarrage du tunnel Cloudflare..." -ForegroundColor Cyan
$cfLog = Join-Path $backend "cloudflared.log"
if (Test-Path $cfLog) { Remove-Item $cfLog -Force }
Start-Process -FilePath $cf -ArgumentList "tunnel --url http://localhost:8000 --no-autoupdate" `
    -RedirectStandardOutput $cfLog -RedirectStandardError (Join-Path $backend "cloudflared.err.log") -WindowStyle Hidden

# Attendre l'URL publique
$public = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $cfLog) {
        $m = Select-String -Path $cfLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m) { $public = $m.Matches[0].Value; break }
    }
}
if (-not $public) { Write-Host "Echec: pas d'URL Cloudflare. Voir $cfLog" -ForegroundColor Red; return }
Write-Host "    URL publique : $public" -ForegroundColor Green
$env:PUBLIC_URL = $public

# 2) Backend FastAPI
Write-Host "2/4 Demarrage du backend (uvicorn :8000)..." -ForegroundColor Cyan
Start-Process -FilePath $py -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" `
    -WorkingDirectory $backend -WindowStyle Minimized

# 3) Worker arq
Write-Host "3/4 Demarrage du worker arq..." -ForegroundColor Cyan
Start-Process -FilePath $py -ArgumentList "-m arq app.workers.arq_settings.WorkerSettings" `
    -WorkingDirectory $backend -WindowStyle Minimized

# 4) Bot Telegram (polling)
Write-Host "4/4 Demarrage du bot Telegram..." -ForegroundColor Cyan
$env:PYTHONPATH = $bot
Start-Process -FilePath $py -ArgumentList "-m bot.main" `
    -WorkingDirectory $bot -WindowStyle Minimized

Write-Host ""
Write-Host "Okeder est lance !" -ForegroundColor Green
Write-Host "  Backend local : http://localhost:8000  (docs: /docs)"
Write-Host "  Public HTTPS  : $public"
Write-Host "  Mini-app      : $public/mini-app/<event_id>"
Write-Host "  Bot Telegram  : @OkederBot"
Write-Host ""
Write-Host "Pour arreter : ./run_local.ps1 -Stop" -ForegroundColor Yellow
