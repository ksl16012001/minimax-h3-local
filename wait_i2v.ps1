# Queue two I2V (first-frame conditioned) max-quality tests after the storyboard finishes.
$root = "G:\minimax-h3"; $out = "$root\outputs_max"
function Log($s) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $s) }
$ff = python -c "import imageio_ffmpeg as f;print(f.get_ffmpeg_exe())"

while (-not (Select-String -Path "$root\outputs\story15.log" -Pattern "STORY DONE|ASSEMBLE FAILED|SHOT[123] FAILED" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting: storyboard"; Start-Sleep -Seconds 60 }
while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "waiting: sd-cli busy"; Start-Sleep -Seconds 60 }
Set-Location $root

# init images at exactly 768x1344 (no resize needed)
$humanInit = "$root\inputs\i2v_human_init.png"
$prodInit  = "$root\inputs\i2v_product_init.png"
if (-not (Test-Path $humanInit)) { & $ff -hide_banner -loglevel error -y -i "$out\human_cafe_lora8_768_s11.webm" -vf "select='eq(n\,0)'" -frames:v 1 $humanInit }
if (-not (Test-Path $prodInit))  { & $ff -hide_banner -loglevel error -y -i "$out\base25_q8_768_s7.webm" -vf "select='eq(n\,30)'" -frames:v 1 $prodInit }

$p1 = "Continue from the first frame: the same young Vietnamese woman in the white linen shirt at the sunlit cafe window. She sets the ceramic cup down on the saucer, leans back in her chair, laughs softly and turns to look out the window at the street, hair catching the light. Keep her face, hair and clothing exactly consistent with the first frame. Static camera with a very slow push-in, shallow depth of field, realistic skin and hands. Sound: quiet cafe ambience, a cup set on a saucer, soft laugh, acoustic guitar."
Log "I2V #1 human"
& .\run_max.ps1 -Dit "minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf" -Te "qwen3vl_32b_minimax_h3-Q4_K_M.gguf" -Steps 8 -Sampler er_sde -W 768 -H 1344 -Frames 56 -Seed 31 -Prompt $p1 -InitImg $humanInit -Out "i2v_human_lora8_768_s31.webm"
if (Test-Path "$out\i2v_human_lora8_768_s31.webm") { Log "I2V #1 done" } else { Log "I2V #1 FAILED" }

$p2 = "Continue from the first frame: the same crystal perfume bottle on black silk with warm rim light. The bottle slowly rotates about thirty degrees on its base while tiny golden particles drift through the air; then an elegant hand with a thin gold bracelet enters from the right, lifts the bottle gently and holds it up to the light, glass refractions sparkling. Keep the bottle shape, cap and liquid color exactly consistent with the first frame. Slow dolly-in, shallow depth of field, premium advertising look. Sound: soft orchestral ambience, silk rustle."
Log "I2V #2 product"
& .\run_max.ps1 -Dit "minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf" -Te "qwen3vl_32b_minimax_h3-Q4_K_M.gguf" -Steps 8 -Sampler er_sde -W 768 -H 1344 -Frames 56 -Seed 32 -Prompt $p2 -InitImg $prodInit -Out "i2v_product_lora8_768_s32.webm"
if (Test-Path "$out\i2v_product_lora8_768_s32.webm") { Log "I2V #2 done" } else { Log "I2V #2 FAILED" }
Log "I2V QUEUE DONE"
