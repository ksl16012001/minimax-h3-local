# Start sd-server with MiniMax-H3 resident (RTX 3070 8GB profile). API: http://127.0.0.1:1234
param(
  [int]$Port = 1234,
  [string]$Dit = "minimax_h3_fl2va_pruned-UD-Q3_K_XL.gguf",  # or minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf (faster, lower quality)
  [string]$LoraApplyMode = "auto"                             # auto (=at_runtime for quantized, ~50s/job) | immediately (merge once, faster)
)

$root   = "G:\minimax-h3"
$bin    = "$root\bin\sd-server.exe"
$models = "$root\models"

& $bin `
  --listen-ip 127.0.0.1 --listen-port $Port `
  --diffusion-model "$models\$Dit" `
  --lora-model-dir "$models\loras" --lora-apply-mode $LoraApplyMode `
  --llm "$models\qwen3vl_32b_minimax_h3-Q2_K_M.gguf" `
  --vae "$models\vae\minimax_h3_video_vae_fp16.safetensors" `
  --audio-vae "$models\vae\minimax_h3_audio_vae_fp32.safetensors" `
  --diffusion-fa --offload-to-cpu --backend te=cpu `
  --cfg-scale 1.0 --rng cpu `
  --log-level info
