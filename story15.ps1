# 15-second storyboard: 3 x 5s (124 frames) shots at 512x896, Ref2VA for product/character consistency, ffmpeg concat.
# Queues after the bake chain and the R2V test. DiT choice at run time: if outputs_max\USE_LORA exists -> baked turbo LoRA 8 steps, else base 25 steps.
$root = "G:\minimax-h3"; $m = "$root\models"; $out = "$root\outputs_max\story15"
New-Item -ItemType Directory -Force -Path $out | Out-Null
function Log($s) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $s) }
$ff = python -c "import imageio_ffmpeg as f;print(f.get_ffmpeg_exe())"

# ---- wait for queue ahead (chain + r2v test) and any sd-cli
while (-not (Select-String -Path "$root\outputs\bake_chain.log" -Pattern "CHAIN DONE|BAKE FAILED|CONVERT FAILED" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting: bake chain"; Start-Sleep -Seconds 60 }
while (-not (Select-String -Path "$root\outputs\max_r2v.log" -Pattern "R2V DONE" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting: r2v test"; Start-Sleep -Seconds 60 }
if (Test-Path "$root\outputs\max_i2v.log") { while (-not (Select-String -Path "$root\outputs\max_i2v.log" -Pattern "I2V QUEUE DONE" -Quiet -ErrorAction SilentlyContinue)) { Log "waiting: i2v queue"; Start-Sleep -Seconds 60 } }
while (Get-Process sd-cli -ErrorAction SilentlyContinue) { Log "waiting: sd-cli busy"; Start-Sleep -Seconds 60 }

$useLora = Test-Path "$root\outputs_max\USE_LORA"
if ($useLora -and (Test-Path "$m\minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf")) { $fl2Dit = "minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf"; $fl2Steps = 8 } else { $fl2Dit = "minimax_h3_fl2va_pruned-Q8_0.gguf"; $fl2Steps = 25 }
$refDit = "minimax_h3_ref2va_pruned-Q8_0.gguf"; $refSteps = 25
$W = 512; $H = 896; $F = 124; $seed = 21
# Ref2VA needs ~0.5 GB more VRAM than FL2VA at the same size (reference tokens): 512x896x124 fails on 8 GB,
# so Ref2VA shots render at 448x800 (same 9:16) and are upscaled to 512x896 at assembly.
$RW = 448; $RH = 800
Log "FL2VA=$fl2Dit steps=$fl2Steps ${W}x${H} | Ref2VA=$refDit steps=$refSteps ${RW}x${RH} | $F frames"

# product reference: crisp 768p frame from the max-quality base render
$prodRef = "$root\inputs\perfume_768_ref.png"
if (-not (Test-Path $prodRef)) { & $ff -hide_banner -loglevel error -y -i "$root\outputs_max\base25_q8_768_s7.webm" -vf "select='eq(n\,30)'" -frames:v 1 $prodRef }

Set-Location $root

# ---- Shot 1: T2V (establishing + character)
$p1 = "Vertical cinematic commercial, golden hour dawn. A rooftop terrace high above a modern city, warm sunrise flare from behind the skyline. An elegant woman in a flowing champagne silk dress walks slowly toward the camera along the terrace edge, wind moving her hair and dress, confident calm expression. Slow dolly back keeping her centered, shallow depth of field, city bokeh, lens flare, film grain. Sound: soft wind, distant city hum, a gentle orchestral intro with strings beginning to swell."
if (-not (Test-Path "$out\shot1.webm")) {
  Log "shot1 T2V"
  & .\run_max.ps1 -Dit $fl2Dit -Steps $fl2Steps -Sampler er_sde -W $W -H $H -Frames $F -Seed $seed -Prompt $p1 -Out "story15\shot1.webm"
}
if (-not (Test-Path "$out\shot1.webm")) { Log "SHOT1 FAILED"; exit 1 }
# character reference from shot1 (late frame, she is closest to camera)
$charRef = "$out\char_ref.png"
& $ff -hide_banner -loglevel error -y -i "$out\shot1.webm" -vf "select='eq(n\,110)'" -frames:v 1 $charRef
Log "shot1 done, char ref extracted"

# ---- Shot 2: Ref2VA (product macro)
$p2 = "Use the perfume bottle from <Picture 1> as the product. Keep its crystal shape, faceted cap and golden liquid exactly consistent. Vertical cinematic macro shot at golden hour on a rooftop terrace: the bottle stands on a white marble balustrade, city skyline soft in the background. A woman's hand with a delicate gold bracelet enters, lifts the bottle and presses the sprayer once; a fine mist catches the low sun and glitters like tiny golden particles drifting in the air. Slow orbit and push-in, shallow depth of field, realistic glass refractions. Sound: a soft spray hiss, wind, strings continuing to build."
if (-not (Test-Path "$out\shot2.webm")) {
  Log "shot2 Ref2VA (product)"
  & .\run_max.ps1 -Dit $refDit -Steps $refSteps -Sampler er_sde -W $RW -H $RH -Frames $F -Seed ($seed+1) -Prompt $p2 -RefImg @($prodRef) -Out "story15\shot2.webm"
}
if (-not (Test-Path "$out\shot2.webm")) { Log "SHOT2 FAILED"; exit 1 }
Log "shot2 done"

# ---- Shot 3: Ref2VA (character + product)
$p3 = "Use the woman from <Picture 1> as the main character, keeping her face, hair and champagne silk dress consistent, and the perfume bottle from <Picture 2> as the product. Vertical cinematic shot, golden hour rooftop: she stands at the terrace edge holding the bottle near her collarbone, turns her head toward the camera and gives a slow confident smile, wind in her hair, sunrise flare and city bokeh behind her. Slow dolly-in ending on a held medium close-up, shallow depth of field, premium luxury advertising look, film grain. Sound: orchestral swell reaching its peak then settling, soft wind."
if (-not (Test-Path "$out\shot3.webm")) {
  Log "shot3 Ref2VA (character + product)"
  & .\run_max.ps1 -Dit $refDit -Steps $refSteps -Sampler er_sde -W $RW -H $RH -Frames $F -Seed ($seed+2) -Prompt $p3 -RefImg @($charRef, $prodRef) -Out "story15\shot3.webm"
}
if (-not (Test-Path "$out\shot3.webm")) { Log "SHOT3 FAILED"; exit 1 }
Log "shot3 done"

# ---- assemble: uniform encode, hard cuts, 0.4s audio crossfade between shots
Log "assembling"
foreach ($i in 1..3) { & $ff -hide_banner -loglevel error -y -i "$out\shot$i.webm" -vf "scale=${W}:${H}:flags=lanczos" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -r 24 -c:a aac -b:a 192k -ar 32000 "$out\shot$i.mp4" }
& $ff -hide_banner -loglevel error -y -i "$out\shot1.mp4" -i "$out\shot2.mp4" -i "$out\shot3.mp4" -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[0:a][1:a]acrossfade=d=0.4:c1=tri:c2=tri[a01];[a01][2:a]acrossfade=d=0.4:c1=tri:c2=tri[a]" -map "[v]" -map "[a]" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$out\story15_final.mp4"
if (Test-Path "$out\story15_final.mp4") { Log "STORY DONE -> $out\story15_final.mp4" } else { Log "ASSEMBLE FAILED" }
