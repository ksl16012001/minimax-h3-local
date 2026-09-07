# MiniMax-H3 MAX-QUALITY render via sd-cli (models reloaded each run; sd-cli frees the text encoder after
# encoding, so Q8_0 DiT + Q4 text encoder fit in 32GB RAM). Expect 10-30+ min per clip.
# Usage: .\run_max.ps1 -Prompt "..." [-Dit <gguf>] [-Steps 25] [-Sampler er_sde] [-W 768 -H 1344] [-Frames 56] [-Seed 7] [-Out max1.webm] [-InitImg path] [-Cache spectrum]
param(
  [string]$Prompt = "Vertical cinematic product shot: a crystal perfume bottle on flowing black silk, warm golden rim light, realistic glass refractions, tiny golden particles drifting, slow smooth dolly-in, shallow depth of field, premium advertising look, soft orchestral ambience",
  [string]$Dit = "minimax_h3_fl2va_pruned-Q8_0.gguf",              # base Q8_0; or minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf (LoRA baked -> use -Steps 8)
  [string]$Te  = "qwen3vl_32b_minimax_h3-Q4_K_M.gguf",
  [int]$Steps = 25,
  [string]$Sampler = "er_sde",
  [int]$W = 768, [int]$H = 1344,                                   # native H3 768p short edge; 9:16
  [int]$Frames = 56,                                               # 17k+5 grid
  [int]$Seed = 7,
  [string]$Out = "max1.webm",
  [string]$InitImg = "",
  [string[]]$RefImg = @(),                                         # Ref2VA: one or more reference images (use a ref2va DiT)
  [string]$Cache = "",                                             # "" or "spectrum"
  [switch]$TeInRam                                                 # default: --params-backend te=disk (TE Q4 17GB otherwise stays resident -> RAM exhaustion with Q8 DiT)
)
$root = "G:\minimax-h3"; $m = "$root\models"
$bin = "$root\bin\sd-cli.exe"
$dit = "$m\$Dit"; $te = "$m\$Te"
$vae = "$m\vae\minimax_h3_video_vae_fp16.safetensors"; $avae = "$m\vae\minimax_h3_audio_vae_fp32.safetensors"
foreach ($f in @($bin,$dit,$te,$vae,$avae)) { if (-not (Test-Path $f)) { Write-Error "Missing: $f"; exit 1 } }
New-Item -ItemType Directory -Force -Path "$root\outputs_max" | Out-Null
$outPath = "$root\outputs_max\$Out"

$cli = @("-M","vid_gen","--diffusion-model",$dit,"--llm",$te,"--vae",$vae,"--audio-vae",$avae,
  "-p",$Prompt,"-W","$W","-H","$H","--video-frames","$Frames","--fps","24",
  "--steps","$Steps","--sampling-method",$Sampler,"--cfg-scale","1.0","--seed","$Seed",
  "--diffusion-fa","--offload-to-cpu","--backend","te=cpu","--vae-tiling","--temporal-tiling","--rng","cpu",
  "-o",$outPath,"-v")
if (-not $TeInRam) { $cli += @("--params-backend","te=disk") }
if ($InitImg) { $cli += @("-i",$InitImg) }
foreach ($r in $RefImg) { if ($r) { $cli += @("--ref-image",$r) } }
if ($Cache)   { $cli += @("--cache-mode",$Cache) }

Write-Host "DiT=$Dit TE=$Te steps=$Steps sampler=$Sampler ${W}x${H} frames=$Frames seed=$Seed -> $outPath"
$sw = [Diagnostics.Stopwatch]::StartNew()
& $bin @cli 2>&1 | Tee-Object -FilePath "$outPath.log"
$sw.Stop(); Write-Host ("Done in {0:N0}s" -f $sw.Elapsed.TotalSeconds)
