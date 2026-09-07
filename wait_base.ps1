# Wait for Q8_0 DiT + Q4 text encoder downloads, then render the base (no-LoRA) max-quality clip.
$root = "G:\minimax-h3"; $m = "$root\models"
$q8 = "$m\minimax_h3_fl2va_pruned-Q8_0.gguf"
$te = "$m\qwen3vl_32b_minimax_h3-Q4_K_M.gguf"
function Log($s) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $s) }

Log "waiting for $q8 and $te"
while (-not ((Test-Path $q8) -and (Test-Path $te))) { Start-Sleep -Seconds 30 }
Start-Sleep -Seconds 10
Log "downloads present: Q8=$([math]::Round((Get-Item $q8).Length/1GB,2)) GB, TE=$([math]::Round((Get-Item $te).Length/1GB,2)) GB"
# run strictly after the bake+convert (both HDD-bound) to avoid disk thrash
while (-not (Select-String -Path "$root\outputs\bake_chain.log" -Pattern "convert done|BAKE FAILED|CONVERT FAILED" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting for bake+convert to finish"; Start-Sleep -Seconds 60 }
while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "another sd-cli running, waiting..."; Start-Sleep -Seconds 60 }

Set-Location $root
Log "rendering base Q8_0, 25 steps, er_sde, 768x1344x56, seed 7"
& .\run_max.ps1 -Dit "minimax_h3_fl2va_pruned-Q8_0.gguf" -Te "qwen3vl_32b_minimax_h3-Q4_K_M.gguf" -Steps 25 -Sampler er_sde -W 768 -H 1344 -Frames 56 -Seed 7 -Out "base25_q8_768_s7.webm"
Log "BASE DONE"
