# Chain: wait for bf16 DiT download -> wait until no sd-cli render is running -> bake turbo LoRA -> convert to Q8_0 -> render baked (8 steps)
$root = "G:\minimax-h3"; $m = "$root\models"
$bf16   = "$m\diffusion_models\minimax_h3_fl2va_pruned_bf16.safetensors"
$lora   = "$m\loras\minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
$merged = "$m\diffusion_models\minimax_h3_fl2va_pruned_turbo8_bf16.safetensors"
$gguf   = "$m\minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf"
$te     = "$m\qwen3vl_32b_minimax_h3-Q4_K_M.gguf"

function Log($s) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $s) }

Log "waiting for bf16 download: $bf16"
while (-not (Test-Path $bf16)) { Start-Sleep -Seconds 30 }
Log "bf16 present ($([math]::Round((Get-Item $bf16).Length/1GB,2)) GB)"

while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "sd-cli render running, waiting..."; Start-Sleep -Seconds 60 }

Set-Location $root
if (-not (Test-Path $merged)) {
  Log "baking LoRA -> $merged"
  python -u bake_lora.py --base $bf16 --lora $lora --out $merged --mult 1.0
  if ($LASTEXITCODE -ne 0) { Log "BAKE FAILED"; exit 1 }
}
Log "bake done ($([math]::Round((Get-Item $merged).Length/1GB,2)) GB)"

if (-not (Test-Path $gguf)) {
  Log "converting -> $gguf (q8_0)"
  & "$root\bin\sd-cli.exe" -M convert --diffusion-model $merged -o $gguf --type q8_0 2>&1 | Where-Object { $_ -notmatch '^\s*\|' }
  if (-not (Test-Path $gguf)) { Log "CONVERT FAILED"; exit 1 }
}
Log "convert done ($([math]::Round((Get-Item $gguf).Length/1GB,2)) GB)"

while (-not (Test-Path $te)) { Log "waiting for TE Q4"; Start-Sleep -Seconds 30 }
while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "sd-cli render running, waiting..."; Start-Sleep -Seconds 60 }

Log "rendering baked LoRA 8-step 768x1344"
& .\run_max.ps1 -Dit "minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf" -Te "qwen3vl_32b_minimax_h3-Q4_K_M.gguf" -Steps 8 -Sampler er_sde -W 768 -H 1344 -Frames 56 -Seed 7 -Out "lora8_q8_768_s7.webm"
Log "CHAIN DONE"
