"""Quality matrix for MiniMax-H3 on sd-server: same prompt/seed across configs.

Usage: python hq_gen.py [--out samples_hq] [--seeds 7] [--w 384 --h 672 --frames 56]
Configs: base8 | lora8_euler | lora8_er_sde | lora8_spectrum
"""
import argparse, base64, csv, json, os, subprocess, sys, time, urllib.request

B = "http://127.0.0.1:1234"
ROOT = r"G:\minimax-h3"
LORA_FILE = os.path.join(ROOT, "models", "loras", "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors")
LORA = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"  # relative to server --lora-model-dir
PROMPT = ("Vertical cinematic product shot: a crystal perfume bottle on flowing black silk, warm golden rim light, "
          "realistic glass refractions, tiny golden particles drifting, slow smooth dolly-in, shallow depth of field, "
          "premium advertising look, soft orchestral ambience")

CONFIGS = {
    "base8":         dict(steps=8,  lora=False, method="euler",  cache=None),
    "lora8_euler":   dict(steps=8,  lora=True,  method="euler",  cache=None),
    "lora8_er_sde":  dict(steps=8,  lora=True,  method="er_sde", cache=None),
    "lora8_spectrum": dict(steps=8, lora=True,  method="euler",  cache="spectrum"),
}


def http(m, u, b=None):
    r = urllib.request.Request(u, data=json.dumps(b).encode() if b is not None else None, method=m,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return json.loads(x.read())


def wait(cond, what, max_s=1800):
    t0 = time.time()
    while not cond():
        if time.time() - t0 > max_s:
            sys.exit(f"timeout waiting for {what}")
        time.sleep(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="samples_hq")
    ap.add_argument("--seeds", type=int, nargs="+", default=[7])
    ap.add_argument("--w", type=int, default=384)
    ap.add_argument("--h", type=int, default=672)
    ap.add_argument("--frames", type=int, default=56)
    ap.add_argument("--only", nargs="*", default=None, help="subset of config names")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    wait(lambda: os.path.exists(LORA_FILE) and os.path.getsize(LORA_FILE) > 1.8e9, "turbo LoRA download")
    def ready():
        try: http("GET", f"{B}/sdcpp/v1/capabilities"); return True
        except Exception: return False
    wait(ready, "sd-server")
    print("[ready] lora + server ok", flush=True)

    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    rows = []
    names = a.only or list(CONFIGS)
    for seed in a.seeds:
        for name in names:
            c = CONFIGS[name]
            body = {
                "prompt": PROMPT, "width": a.w, "height": a.h, "video_frames": a.frames, "fps": 24, "seed": seed,
                "sample_params": {"sample_steps": c["steps"], "sample_method": c["method"],
                                  "guidance": {"txt_cfg": 1.0, "img_cfg": 1.0}},
                "vae_tiling_params": {"enabled": True, "temporal_tiling": True},
                "output_format": "webm",
            }
            if c["lora"]:
                body["lora"] = [{"path": LORA, "multiplier": 1.0, "is_high_noise": False}]
            if c["cache"]:
                body["cache_mode"] = c["cache"]
            tag = f"{name}_s{seed}"
            t0 = time.time()
            try:
                j = http("POST", f"{B}/sdcpp/v1/vid_gen", body)
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                print(f"[{tag}] SUBMIT ERROR {e.code}: {msg}", flush=True)
                rows.append([tag, seed, "submit_error", "", msg]); continue
            jid = j["id"]; print(f"[submit] {tag} -> {jid}", flush=True)
            while True:
                j = http("GET", f"{B}/sdcpp/v1/jobs/{jid}")
                if j["status"] in ("completed", "failed", "cancelled"): break
                time.sleep(5)
            gen = (j.get("completed") or 0) - (j.get("started") or 0)
            if j["status"] != "completed":
                print(f"[{tag}] FAILED gen={gen}s err={j.get('error')}", flush=True)
                rows.append([tag, seed, j["status"], gen, json.dumps(j.get("error"))]); continue
            webm = os.path.join(a.out, f"{tag}.webm"); mp4 = os.path.join(a.out, f"{tag}.mp4")
            open(webm, "wb").write(base64.b64decode(j["result"]["b64_json"]))
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", webm, "-c:v", "libx264", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", mp4])
            print(f"[{tag}] done: gen={gen}s wall={time.time()-t0:.0f}s -> {mp4}", flush=True)
            rows.append([tag, seed, "completed", gen, ""])

    with open(os.path.join(a.out, "results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["tag", "seed", "status", "gen_seconds", "error"]); w.writerows(rows)
    print("[hq] finished", flush=True)


if __name__ == "__main__":
    main()
