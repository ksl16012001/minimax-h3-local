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
| lora8_q8_768_s7 | turbo LoRA baked into Q8_0, 8 steps, te=disk | 240s | 515s (~42 s/step) | 150s | 932s | better prompt adherence (particles, golden rim light, faceted crystal), advertising look; RAM free 3.3GB with te=disk |
| human_cafe_lora8_768_s11 | baked LoRA 8 steps, te=disk, human portrait | 182s | 511s | 147s | 865s | photoreal face/skin, correct 5-finger hand tucking hair, both-hands cup, consistent identity, Vietnamese street bokeh |

VRAM at 768x1344x56: compute budget ~5.27GB, per-step warning "need 750MB, available 245MB" but ggml copes. 1080p impossible.

Decision 2026-09-07: storyboard FL2VA shots use the baked LoRA (USE_LORA flag); Ref2VA shots use base 25 steps.

### Ref2VA VRAM (2026-09-07)
Ref2VA at 512x896x124 FAILED on 8 GB ("segment 3/51 failed during weight preparation"): needed budget 5.45-5.87 GB vs ~5.3 GB practical ceiling.
FL2VA at the same size needs 5.20 GB and works. Reference-image tokens add ~0.5 GB. Fix: Ref2VA shots at 448x800 (~10.9k tokens, ~4.5 GB) and upscale to 512x896 at assembly (story15.ps1).
Storyboard shot1 (FL2VA baked LoRA, 8 steps, 512x896x124): 938s total (sampling 502s, decode 163s).

### I2V VRAM (2026-09-07)
I2V (first-frame) at 768x1344x56 FAILED: needed budget 5.85-6.25 GB (T2V same size: 5.27 GB). Init-image conditioning adds ~0.6-1 GB.
Expect I2V/FLF2V ceiling on 8 GB around 640x1152x56 (~10.8k tokens). test_suite.py t04/t05 ladders extended accordingly.
Empirical budget ceiling on RTX 3070 8 GB ≈ 5.3 GB (FL2VA 768x1344x56 passes at 5.27; anything ≥5.45 fails).

### Storyboard shot 2 — Ref2VA product identity (2026-09-07)
Ref2VA Q8, 25 steps, 448x800x124, 1 reference (768p perfume frame): product identity preserved almost exactly (bottle shape, cap, label, liquid color) in a new scene with hand + spray mist. 3370s total because RAM thrashed (sd-cli private 26.9 GB, WS 8.2 GB, pagefile peak 24 GB; League client also running). Ref2VA keeps more in RAM than FL2VA (vision tower + ref latents) even with te=disk.
-> R2V is the right pipeline for "product photo -> ad video". For speed on 32 GB RAM: close other apps, or use Ref2VA Q6_K (15.4 GB) instead of Q8 (20 GB).

### Storyboard 15s — DONE (2026-09-07)
outputs_max/story15/story15_final.mp4 (15.5 s, 512x896, 3 shots). shot1 FL2VA baked LoRA 8 steps 512x896x124 (938s); shot2 Ref2VA 25 steps 448x800x124 (3370s, RAM thrash); shot3 Ref2VA 2 refs 448x800x124 (1614s, sampling 1090s).
Assembly gotcha: scaled shots carry SAR 49:50 -> concat fails ("Could not open encoder before EOF"); fixed with setsar=1 (story15.ps1).

## Test suite (test_suite.py) — partial results, clean machine after reboot 2026-09-08

| test | passed at | tokens | TE | sampling | decode | wall | failed rungs (need MB) |
|---|---|---|---|---|---|---|---|
| t01 T2V 768p long | 768x1344x56 (8 st) | 15120 | 209s | 524s | 141s | 900s | 124f (11806), 90f (8947), 73f (7518) |
| t02 T2V 15 s single shot | 384x672x243 = 10 s (8 st) | 14868 | | | | 988s | 384x672x362 (9152), 352x640x362 (8192), 320x576x362 (fail, other) |
| t03 T2V base 40 steps + text | 768x1344x56 (40 st) | 15120 | | | | 2350s | - |
| t04 I2V long | 768x1344x56 (8 st) | 15120 | | | | 1114s | 124f (12367), 90f (9510), 73f (8081) |
| t05 FLF2V | 640x1152x56 (8 st) | 10800 | | | | 1014s | 768x1344x56 (7211) |
| t06 R2V 1 ref | 768x1344x56 (25 st) | 15120 | | | | 2018s | - |
| t07 R2V 2 refs | (running) | | | | | | 768x1344x56 (6838) |

Calibration: need_MB ≈ 0.38 x tokens at 768p (T2V); I2V ≈ +5%, FLF2V ≈ +37%, R2V 2 refs ≈ +30% vs T2V at the same size.
IMPORTANT: the 2026-09-07 I2V/R2V failures at 768x1344x56 were caused by League of Legends holding VRAM, not by the model — on a clean GPU both pass. The server's VRAM planner must read live free VRAM (nvidia-smi) rather than assume 8 GB.
15 s in one shot does not fit on 8 GB at any resolution >= 320x576; 10 s at 384x672 works (988s).

### Suite t07-t09 (2026-09-08)
- t07 R2V 2 refs (character + product): OK at 640x1152x56, 25 steps, 1564s; 768p needs 6838 MB -> fail. Identity of both preserved.
- t08 R2V + Ref2V turbo 4-step LoRA v0.1 (runtime): technically OK at 576x1024x56 (720s) but QUALITY COLLAPSE — product correct for ~1 s, then camera drifts into silk and the last frames become abstract light swirls. Runtime LoRA also adds ~1.1 GB VRAM (768p 7043 MB, 640x1152 5385 MB -> fail). Do NOT use this LoRA for product clips; use base Ref2VA 25 steps.
- t09 V2V (--ref-video): fails in <10 s at ANY output size with "vae encode compute failed" — the reference video is VAE-encoded untiled; 512x896x56 ref needs 10150 MB. Ladder now varies the reference size (320x576, 256x448). Rule: ref-video VRAM ≈ 10.1 GB x (ref pixels x frames)/(512x896x56).
- t10 speech + lip-sync (Vietnamese line): OK at 768x1344x56, 8 steps, 859s; 73f needs 7521 MB -> fail. Visually convincing showroom presenter (even a lavalier mic), clear changing mouth shapes; waveform shows ~10 syllable bursts (mean -13 dB, peak 0 dB). Intelligibility to be judged by ear.
- t09 V2V root cause (2026-09-08): the reference-video VAE *encode* graph stages the whole video VAE on the GPU as one segment — constant need 10149 MB regardless of reference size, tile size (--vae-tile-size 16x16/8x8) or frame count (22). Only workaround on 8 GB: `--backend te=cpu,vae=cpu` (VAE on CPU; slow encode/decode). Being tested.
