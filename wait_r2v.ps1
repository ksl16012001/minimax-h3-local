# Wait for Ref2VA Q8_0 + TE Q4 + the bake chain to finish, then render a reference-to-video (R2V) max-quality clip.
$root = "G:\minimax-h3"; $m = "$root\models"
$dit = "$m\minimax_h3_ref2va_pruned-Q8_0.gguf"
$te  = "$m\qwen3vl_32b_minimax_h3-Q4_K_M.gguf"
$ref = "$root\inputs\perfume_ref.png"
function Log($s) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $s) }

Log "waiting for $dit"
while (-not ((Test-Path $dit) -and (Test-Path $te))) { Start-Sleep -Seconds 30 }
Start-Sleep -Seconds 10
Log "ref2va present ($([math]::Round((Get-Item $dit).Length/1GB,2)) GB)"
while (-not (Select-String -Path "$root\outputs\bake_chain.log" -Pattern "CHAIN DONE|BAKE FAILED|CONVERT FAILED" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting for bake chain to finish"; Start-Sleep -Seconds 60 }
while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "sd-cli running, waiting..."; Start-Sleep -Seconds 60 }

Set-Location $root
$prompt = "Use the perfume bottle from <Picture 1> as the main product. Keep its shape, crystal facets, gold cap and liquid color exactly consistent with the reference. Vertical cinematic advertising shot: the bottle stands on flowing black silk, warm golden rim light, tiny golden particles drifting, slow smooth orbit and dolly-in, shallow depth of field, photorealistic glass refractions, premium luxury look. Soft orchestral ambience."
Log "rendering R2V base Ref2VA Q8_0, 25 steps, er_sde, 768x1344x56, seed 7, ref=$ref"
& .\run_max.ps1 -Dit "minimax_h3_ref2va_pruned-Q8_0.gguf" -Te "qwen3vl_32b_minimax_h3-Q4_K_M.gguf" -Steps 25 -Sampler er_sde -W 768 -H 1344 -Frames 56 -Seed 7 -RefImg $ref -Prompt $prompt -Out "r2v25_q8_768_s7.webm"
Log "R2V DONE"
