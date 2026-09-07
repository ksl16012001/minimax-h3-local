"""Submit a batch of MiniMax-H3 video jobs to sd-server and collect results.

Usage: python batch_gen.py [--base http://127.0.0.1:1234] [--out samples] [--w 384] [--h 672] [--frames 56] [--steps 8]
"""
import argparse, base64, csv, json, os, subprocess, sys, time, urllib.request, urllib.error

PROMPTS = [
    ("skincare_serum",  101, "Vertical product shot: a glass skincare serum bottle standing on wet black stone, water droplets, soft spa light, slow tilt up, calm ambient spa music"),
    ("sneaker_turntable", 102, "Vertical product shot: a white running sneaker rotating on a turntable in a dark studio, neon blue and pink rim light, light hip-hop beat"),
    ("matcha_latte",    103, "Vertical: a young woman holds an iced matcha latte in a bright cafe, smiles at the camera, soft cafe chatter and clinking cups"),
    ("earbuds_unbox",   104, "Vertical close-up: hands open a white wireless earbuds case on a wooden desk, satisfying click, earbuds glow, quiet room tone"),
    ("ceramic_vase",    105, "Vertical: a ceramic vase with dried pampas grass on a windowsill, linen curtains move in a breeze, morning birdsong"),
    ("perfume_silk",    106, "Vertical cinematic push-in: a crystal perfume bottle on black silk, golden particles floating in the air, soft orchestral swell"),
    ("strawberry_splash", 107, "Vertical macro slow motion: fresh strawberries fall into clear water, splash and bubbles, bright studio light, water splash sound"),
    ("linen_shirt_walk", 108, "Vertical handheld follow shot: a man in a beige linen shirt walks down a sunlit European street, city ambience, footsteps"),
    ("smartwatch_wrist", 109, "Vertical: a smartwatch on a wrist lights up with a notification, dark background, subtle chime sound, slow orbit"),
    ("night_market_grill", 110, "Vertical: a street food vendor grills skewers at a night market, smoke and sparks, neon signs, sizzling sound and crowd noise"),
]


def http(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode() or "null")


def wait_ready(base, max_wait=1200):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            st, caps = http("GET", f"{base}/sdcpp/v1/capabilities")
            if st == 200:
                print(f"[ready] server up after {time.time()-t0:.0f}s; modes={caps.get('supported_modes')}", flush=True)
                return caps
        except Exception as e:  # noqa: BLE001
            pass
        time.sleep(10)
    sys.exit("server did not become ready in time")


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:1234")
    ap.add_argument("--out", default="samples")
    ap.add_argument("--w", type=int, default=384)
    ap.add_argument("--h", type=int, default=672)
    ap.add_argument("--frames", type=int, default=56)
    ap.add_argument("--steps", type=int, default=8)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    caps = wait_ready(a.base)
    with open(os.path.join(a.out, "capabilities.json"), "w") as f:
        json.dump(caps, f, indent=2)

    ff = ffmpeg()
    rows = []
    for name, seed, prompt in PROMPTS:
        body = {
            "prompt": prompt,
            "width": a.w, "height": a.h,
            "video_frames": a.frames, "fps": 24,
            "seed": seed,
            "sample_params": {"sample_steps": a.steps, "guidance": {"txt_cfg": 1.0, "img_cfg": 1.0}},
            "vae_tiling_params": {"enabled": True, "temporal_tiling": True},
            "output_format": "webm",
        }
        t_submit = time.time()
        st, job = http("POST", f"{a.base}/sdcpp/v1/vid_gen", body)
        jid = job["id"]
        print(f"[submit] {name} seed={seed} -> {jid} ({st})", flush=True)

        last = None
        while True:
            st, j = http("GET", f"{a.base}/sdcpp/v1/jobs/{jid}")
            if j["status"] != last:
                print(f"  [{name}] {j['status']} q={j.get('queue_position')}", flush=True)
                last = j["status"]
            if j["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(5)

        t_done = time.time()
        if j["status"] != "completed":
            print(f"  [{name}] FAILED: {j.get('error')}", flush=True)
            rows.append([name, seed, j["status"], "", "", json.dumps(j.get("error"))])
            continue

        res = j["result"]
        webm = os.path.join(a.out, f"{name}.webm")
        with open(webm, "wb") as f:
            f.write(base64.b64decode(res["b64_json"]))
        mp4 = os.path.join(a.out, f"{name}.mp4")
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", webm,
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", mp4], check=False)
        gen_s = (j.get("completed") or 0) - (j.get("started") or 0)
        print(f"  [{name}] done: frames={res.get('frame_count')} gen={gen_s}s wall={t_done-t_submit:.0f}s -> {mp4}", flush=True)
        rows.append([name, seed, "completed", gen_s, f"{t_done-t_submit:.0f}", prompt])

    with open(os.path.join(a.out, "results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "seed", "status", "gen_seconds", "wall_seconds", "prompt_or_error"])
        w.writerows(rows)
    print("[batch] finished", flush=True)


if __name__ == "__main__":
    main()
