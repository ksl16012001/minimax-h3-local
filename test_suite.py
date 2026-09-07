"""MiniMax-H3 max-quality use-case test suite with automatic step-down.

Each task starts at its highest config; if sd-cli fails (VRAM / crash / no output) the next rung of the
ladder is tried. Results: outputs_max/suite/<task>/..., outputs_max/suite/results.json + RESULTS.md.

Usage: python test_suite.py [--only t01 t05 ...] [--no-wait]
"""
import argparse, json, os, re, subprocess, sys, time

ROOT = r"G:\minimax-h3"; M = os.path.join(ROOT, "models"); BIN = os.path.join(ROOT, "bin", "sd-cli.exe")
OUT = os.path.join(ROOT, "outputs_max", "suite"); INP = os.path.join(ROOT, "inputs")
FL2_LORA = "minimax_h3_fl2va_pruned_turbo8-Q8_0.gguf"; FL2_BASE = "minimax_h3_fl2va_pruned-Q8_0.gguf"
REF = "minimax_h3_ref2va_pruned-Q8_0.gguf"; TE = "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"
VAE = os.path.join(M, "vae", "minimax_h3_video_vae_fp16.safetensors"); AVAE = os.path.join(M, "vae", "minimax_h3_audio_vae_fp32.safetensors")
REF2V_LORA_TAG = "<lora:minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16:1>"

HUMAN_WEBM = os.path.join(ROOT, "outputs_max", "human_cafe_lora8_768_s11.webm")
PERF_WEBM = os.path.join(ROOT, "outputs_max", "base25_q8_768_s7.webm")
SHOT1_WEBM = os.path.join(ROOT, "outputs_max", "story15", "shot1.webm")
HUMAN0 = os.path.join(INP, "suite_human_f0.png"); HUMAN55 = os.path.join(INP, "suite_human_f55.png")
PROD_REF = os.path.join(INP, "perfume_768_ref.png"); CHAR_REF = os.path.join(ROOT, "outputs_max", "story15", "char_ref.png")
REFVID_DIR = os.path.join(INP, "refvideo_shot1")

def R(w, h, f, steps=None): return {"w": w, "h": h, "frames": f, **({"steps": steps} if steps else {})}

TASKS = [
    dict(id="t01_t2v_native_long", dit=FL2_LORA, steps=8, seed=101,
         prompt="Vertical cinematic shot: a barista in a sunlit specialty coffee bar pours latte art into a white cup, steam rising, slow push-in from the counter to a close-up of the rosetta, warm wood tones, shallow depth of field, film grain. Sound: espresso machine hiss, milk steaming, quiet indie music.",
         ladder=[R(768,1344,124), R(768,1344,90), R(768,1344,73), R(768,1344,56)]),
    dict(id="t02_t2v_15s", dit=FL2_LORA, steps=8, seed=102,
         prompt="Vertical, one continuous 15-second shot: a golden retriever puppy runs across a sunny beach toward the camera, splashes through shallow waves, shakes off water in slow motion, then sits and tilts its head, sea and blue sky behind. Handheld follow, natural light. Sound: waves, seagulls, the puppy panting, a soft ukulele tune.",
         ladder=[R(384,672,362), R(352,640,362), R(320,576,362), R(384,672,243)]),
    dict(id="t03_t2v_base40_text", dit=FL2_BASE, steps=40, seed=103,
         prompt="Vertical cinematic street scene at dusk in Hanoi old quarter: a neon sign reading MINIMAX glows above a small cafe, motorbikes pass with light trails, a vendor arranges flowers, lanterns sway. Slow dolly forward, shallow depth of field, rain-wet pavement reflections. Sound: street bustle, motorbike engines, distant music.",
         ladder=[R(768,1344,56,40), R(768,1344,56,30), R(768,1344,56,25)]),
    dict(id="t04_i2v_long", dit=FL2_LORA, steps=8, seed=104, init=HUMAN0,
         prompt="Continue from the first frame: the same young Vietnamese woman in the white linen shirt at the cafe window. She takes a sip of coffee, sets the cup down, then looks out the window and smiles as a friend waves from outside; she waves back. Keep her face, hair and clothes consistent. Static camera, slow push-in, realistic hands. Sound: cafe ambience, cup on saucer, soft laugh.",
         ladder=[R(768,1344,124), R(768,1344,90), R(768,1344,73), R(768,1344,56)]),
    dict(id="t05_flf2v", dit=FL2_LORA, steps=8, seed=105, init=HUMAN0, end=HUMAN55,
         prompt="The same young Vietnamese woman at the cafe window moves naturally from the first frame to the last frame: she lifts her hand and tucks her hair behind her ear while smiling. Smooth realistic motion, consistent identity and lighting. Sound: cafe ambience, soft acoustic guitar.",
         ladder=[R(768,1344,56), R(640,1152,56)]),
    dict(id="t06_r2v_product", dit=REF, steps=25, seed=106, refs=[PROD_REF],
         prompt="Use the perfume bottle from <Picture 1> as the product, keeping its crystal shape, cap and liquid color exactly consistent. Vertical luxury commercial: the bottle stands on a rain-wet black marble ledge at night, city neon bokeh behind, slow orbit, droplets on glass catching colored light, premium advertising look. Sound: soft rain, distant city, cinematic synth pad.",
         ladder=[R(768,1344,56), R(640,1152,56), R(576,1024,56), R(512,896,56)]),
    dict(id="t07_r2v_char_product", dit=REF, steps=25, seed=107, refs=[CHAR_REF, PROD_REF],
         prompt="Use the woman from <Picture 1> as the main character (same face, hair, champagne silk dress) and the perfume bottle from <Picture 2> as the product. Vertical cinematic shot: she sits at a vanity mirror in warm light, lifts the bottle, sprays once at her neck and closes her eyes with a soft smile; mist glitters. Slow dolly-in, shallow depth of field. Sound: spray hiss, soft piano.",
         ladder=[R(768,1344,56), R(640,1152,56), R(576,1024,56), R(512,896,56)]),
    dict(id="t08_r2v_turbo4", dit=REF, steps=4, seed=108, refs=[PROD_REF], lora_tag=REF2V_LORA_TAG,
         prompt="Use the perfume bottle from <Picture 1> as the product, keeping it exactly consistent. Vertical commercial: the bottle on flowing black silk, warm golden rim light, tiny golden particles drifting, slow dolly-in, premium look. Sound: soft orchestral ambience.",
         ladder=[R(768,1344,56), R(640,1152,56), R(576,1024,56), R(512,896,56)]),
    dict(id="t09_v2v_refvideo", dit=REF, steps=25, seed=109, ref_video=REFVID_DIR,
         prompt="Use the motion and framing of <Video 1>: the same woman walking toward the camera on a rooftop terrace, but restyled as a rainy cyberpunk night — neon signs, holographic billboards, wet reflective floor, cyan and magenta rim light, her dress now dark metallic. Keep the camera movement and timing of the reference. Sound: rain, synthwave music, distant hover-car hum.",
         ladder=[R(512,896,56), R(448,800,56), R(384,672,56)]),
    dict(id="t10_speech_lipsync", dit=FL2_LORA, steps=8, seed=110,
         prompt="Vertical talking-head shot: a friendly young Vietnamese woman in a beige blazer stands in a bright modern showroom, looks into the camera and speaks clearly in Vietnamese: \"Chào mừng bạn đến với bộ sưu tập mới của chúng tôi.\" Natural lip movement matching the words, subtle hand gesture, soft studio light, shallow depth of field. Sound: her clear Vietnamese voice, quiet room tone.",
         ladder=[R(768,1344,73), R(768,1344,56)]),
]

FAIL_PAT = re.compile(r"sampling failed|compute failed|failed during weight preparation|generate failed|out of memory|OOM", re.I)
NEED_PAT = re.compile(r"need ([\d.]+) MB device / ([\d.]+) MB budget")
TIME_PAT = {"te_s": r"get_learned_condition completed, taking ([\d.]+)s", "sample_s": r"sampling completed, taking ([\d.]+)s", "decode_s": r"decode_first_stage completed, taking ([\d.]+)s"}


def ffmpeg():
    import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()


def prep_inputs(ff):
    os.makedirs(INP, exist_ok=True)
    if not os.path.exists(HUMAN0): subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", HUMAN_WEBM, "-vf", "select='eq(n\\,0)'", "-frames:v", "1", HUMAN0])
    if not os.path.exists(HUMAN55): subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", HUMAN_WEBM, "-vf", "select='eq(n\\,55)'", "-frames:v", "1", HUMAN55])
    if not os.path.exists(PROD_REF): subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", PERF_WEBM, "-vf", "select='eq(n\\,30)'", "-frames:v", "1", PROD_REF])
    if not os.path.isdir(REFVID_DIR) or not os.listdir(REFVID_DIR):
        os.makedirs(REFVID_DIR, exist_ok=True)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", SHOT1_WEBM, "-vf", "select='lt(n\\,56)'", "-vsync", "0", os.path.join(REFVID_DIR, "f%04d.png")])


def tokens(w, h, f):
    k = max(0, (f - 5 + 16) // 17); return (w // 32) * (h // 32) * (4 * k + 3)


def run_attempt(task, cfg, tdir, ff):
    tag = f"{cfg['w']}x{cfg['h']}x{cfg['frames']}_s{cfg.get('steps', task['steps'])}"
    out = os.path.join(tdir, f"{task['id']}_{tag}.webm"); log = out + ".log"
    prompt = task["prompt"] + (" " + task["lora_tag"] if task.get("lora_tag") else "")
    args = [BIN, "-M", "vid_gen", "--diffusion-model", os.path.join(M, task["dit"]), "--llm", os.path.join(M, TE), "--vae", VAE, "--audio-vae", AVAE,
            "-p", prompt, "-W", str(cfg["w"]), "-H", str(cfg["h"]), "--video-frames", str(cfg["frames"]), "--fps", "24",
            "--steps", str(cfg.get("steps", task["steps"])), "--sampling-method", "er_sde", "--cfg-scale", "1.0", "--seed", str(task["seed"]),
            "--diffusion-fa", "--offload-to-cpu", "--backend", "te=cpu", "--params-backend", "te=disk", "--vae-tiling", "--temporal-tiling", "--rng", "cpu",
            "-o", out, "-v"]
    if task.get("init"): args += ["-i", task["init"]]
    if task.get("end"): args += ["--end-img", task["end"]]
    for r in task.get("refs", []): args += ["--ref-image", r]
    if task.get("ref_video"): args += ["--ref-video", task["ref_video"]]
    if task.get("lora_tag"): args += ["--lora-model-dir", os.path.join(M, "loras")]
    t0 = time.time()
    with open(log, "wb") as lf:
        p = subprocess.run(args, stdout=lf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    txt = open(log, "rb").read().decode("utf-8", errors="replace").replace("\r", "\n")
    ok = p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 10000 and not FAIL_PAT.search(txt)
    need = NEED_PAT.findall(txt); need_mb = max((float(a) for a, b in need), default=None); budget_mb = max((float(b) for a, b in need), default=None)
    times = {k: float(m.group(1)) for k, pat in TIME_PAT.items() if (m := re.search(pat, txt))}
    res = dict(config=tag, ok=ok, rc=p.returncode, wall_s=round(wall), tokens=tokens(cfg["w"], cfg["h"], cfg["frames"]), need_mb=need_mb, budget_mb=budget_mb, **times, log=os.path.basename(log))
    if ok:
        mp4 = out[:-5] + ".mp4"
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", out, "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", mp4])
        n = cfg["frames"]; sel = "+".join(f"eq(n\\,{i})" for i in (0, n // 3, 2 * n // 3, n - 1))
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", out, "-vf", f"select='{sel}',scale=300:-1,tile=4x1:padding=4:color=white", "-frames:v", "1", out[:-5] + "_frames.png"])
        res["mp4"] = os.path.basename(mp4)
    else:
        err = [l for l in txt.splitlines() if "[ERROR" in l][-3:]; res["error"] = " | ".join(err)[:300]
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", nargs="*"); ap.add_argument("--no-wait", action="store_true"); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True); ff = ffmpeg()
    if not a.no_wait:
        slog = os.path.join(ROOT, "outputs", "story15.log")
        while not (os.path.exists(slog) and re.search(r"STORY DONE|ASSEMBLE FAILED|SHOT[123] FAILED", open(slog, errors="replace").read())):
            print("[suite] waiting: storyboard", flush=True); time.sleep(60)
        while subprocess.run(["tasklist", "/FI", "IMAGENAME eq sd-cli.exe"], capture_output=True, text=True).stdout.find("sd-cli") >= 0:
            print("[suite] waiting: sd-cli busy", flush=True); time.sleep(60)
    prep_inputs(ff)
    rpath = os.path.join(OUT, "results.json")
    results = json.load(open(rpath)) if os.path.exists(rpath) else {}
    for task in TASKS:
        if a.only and task["id"] not in a.only: continue
        if results.get(task["id"], {}).get("final", {}).get("ok"): print(f"[suite] {task['id']} already done, skip", flush=True); continue
        tdir = os.path.join(OUT, task["id"]); os.makedirs(tdir, exist_ok=True)
        attempts = []
        for cfg in task["ladder"]:
            print(f"[suite] {task['id']} try {cfg}", flush=True)
            r = run_attempt(task, cfg, tdir, ff); attempts.append(r)
            print(f"[suite] {task['id']} {r['config']} -> {'OK' if r['ok'] else 'FAIL'} wall={r['wall_s']}s need={r.get('need_mb')}MB {r.get('error','')}", flush=True)
            results[task["id"]] = dict(attempts=attempts, final=r if r["ok"] else None)
            json.dump(results, open(rpath, "w"), indent=2)
            if r["ok"]: break
        else:
            print(f"[suite] {task['id']} EXHAUSTED ladder", flush=True)
    # markdown summary
    lines = ["| task | passed at | tokens | need/budget MB | TE | sampling | decode | wall | failed rungs |", "|---|---|---|---|---|---|---|---|---|"]
    for tid, rres in results.items():
        f = rres.get("final"); fails = ", ".join(x["config"] for x in rres["attempts"] if not x["ok"]) or "-"
        if f: lines.append(f"| {tid} | {f['config']} | {f['tokens']} | {f.get('need_mb')}/{f.get('budget_mb')} | {f.get('te_s','')} | {f.get('sample_s','')} | {f.get('decode_s','')} | {f['wall_s']}s | {fails} |")
        else: lines.append(f"| {tid} | NONE | | | | | | | {fails} |")
    open(os.path.join(OUT, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("[suite] SUITE DONE", flush=True)


if __name__ == "__main__":
    main()
