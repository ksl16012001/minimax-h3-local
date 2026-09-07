# vidforge — MiniMax-H3 local video server (RTX 3070 8GB)

## Verified runs (2026-09-07, sd.cpp master-845-80bac2d, DiT UD-Q2_K_XL, TE Q2_K_M on CPU)

| Test | Size | Frames | Steps | Sampling | VAE decode | Total (incl. HDD load) | VRAM peak |
|---|---|---|---|---|---|---|---|
| test1 | 640x384 | 22 (0.9s) | 8 | 121s | 84s | 402s | ~7.5GB |
| test2 | 384x672 (9:16) | 56 (2.3s) | 8 | 152s | 113s | 438s | ~7.5GB |

Compute-only (models resident in sd-server): ~4.5 min per 2.3s 9:16 clip.
Frame grid 17k+5 (5,22,39,56,73,90,107,124), dims multiple of 32, 24fps fixed, cfg must be 1.0.

## Files
- bin/: sd-cli.exe, sd-server.exe (CUDA12), docs: minimax_h3.md, sd-server-README.md, sd-server-api.md
- models/: minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf, qwen3vl_32b_minimax_h3-Q2_K_M.gguf, vae/*
- run_t2v.ps1: one-shot CLI runner
- outputs/: test clips + logs

## sd-server batch (10 samples, 9:16 384x672, 56 frames, 8 steps) — 2026-09-07

Models resident in sd-server (start_server.ps1, port 1234), submitted via POST /sdcpp/v1/vid_gen (batch_gen.py):
- job 1: 433s (includes model load into resident state)
- jobs 2-10: **93-100s each** (median 94s) — ~4.6x faster than sd-cli per-clip (438s)
- 10 clips = 20 min wall. Projected: ~38 clips/hour, ~300 clips overnight at this size.
- Outputs: samples/*.mp4, samples/results.csv, samples/contact_sheet.png

## Quality matrix (384x672, 56f, seed 7, sd-server resident) — 2026-09-07

| config | apply_loras | sampling | decode | total/job | quality |
|---|---|---|---|---|---|
| Q2 base 8 steps | - | 78s | 20s | ~117s | soft, weak prompt adherence |
| Q3 base 8 steps | - | ~80s* | ~23s* | ~120s* | better detail, still soft |
| Q3 + turbo LoRA 8-step, euler | 50s | 81s | 23s | 171s | sharp, best jump |
| Q3 + turbo LoRA 8-step, er_sde | 50s | 79s | 23s | 158s | sharp + best prompt adherence (particles animate) |
| Q3 + turbo LoRA 8-step, euler, cache=spectrum | 51s | 61s | 23s | 140s | same as euler, -20s |

*first job after restart measured 152s/125s because weights were still paging from HDD; steady-state ≈ Q2.
LoRA is re-applied per request (quantized weights -> at_runtime mode): fixed 50s tax per job.
Recommended HQ: DiT UD-Q3_K_XL + loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16 (mult 1.0) + er_sde + 8 steps; add cache_mode=spectrum for speed.
Server: start_server.ps1 (now defaults to Q3 + --lora-model-dir). Matrix script: hq_gen.py. Outputs: samples_hq/.

### LoRA apply mode
- `--lora-apply-mode immediately` CRASHES sd-server with quantized GGUF + offload (ggml assert: pre-allocated tensor in CUDA0 buffer cannot run CPY). Log: outputs/server_immediately_crash.err.log. Keep `auto` (=at_runtime): 50s apply per job.
- Only way to remove the 50s tax: bake LoRA into a bf16 DiT then re-quantize with `sd-cli -M convert` (needs Comfy-Org minimax_h3_fl2va_pruned_bf16.safetensors, 37GB) — not done yet.

## MAX quality (sd-cli, time no object) — 2026-09-07

Setup: DiT Q8_0 (unsloth), TE Q4_K_M, 768x1344 native, 56 frames, er_sde, cfg 1.0, --params-backend te=disk (added after run #1).
sd-server must be stopped first (VRAM+RAM). Logs from Tee-Object are UTF-16 -> read with iconv -f UTF-16LE.

| run | config | TE encode | sampling | decode | total | notes |
|---|---|---|---|---|---|---|
| base25_q8_768_s7 | base, 25 steps | 252s | 1277s (~45 s/step) | 148s | 1710s | photoreal glass/silk, sharp; lost golden particles; RAM hit 0.8GB free (TE Q4 stayed resident, pinned-mem fallbacks, ~5.9GB pagefile) but completed |

VRAM at 768x1344x56: compute budget ~5.27GB, per-step warning "need 750MB, available 245MB" but ggml copes. 1080p impossible.
