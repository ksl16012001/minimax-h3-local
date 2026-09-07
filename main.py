
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error


# ============================================================
# CONFIG
# ============================================================

HTTP_TIMEOUT = 2 * 60 * 60
GENERATION_TIMEOUT = 4 * 60 * 60
POLL_INTERVAL = 10

NAME = "perfume_cinematic_hq"
DEFAULT_SEED = 106


PROMPT = """
Luxury cinematic vertical commercial for a premium crystal perfume bottle.

A beautifully crafted transparent crystal perfume bottle stands on flowing
black silk in an elegant dark studio.

Warm golden rim lighting creates realistic reflections and refractions through
the glass. Tiny golden dust particles slowly float through the air.

The camera performs an extremely smooth and slow cinematic dolly-in toward
the perfume bottle with subtle natural parallax.

The black silk moves gently from a soft breeze.

Realistic transparent glass material, physically accurate reflections,
detailed highlights, rich blacks, high dynamic range, shallow depth of field,
soft cinematic background bokeh.

Premium luxury fragrance advertising aesthetic.

Photorealistic, extremely detailed product photography, professional studio
lighting, clean composition, stable geometry, consistent bottle shape across
every frame, realistic motion, strong temporal consistency, sharp product
details.

No text.
No logo.
No watermark.
No distortion.
No flickering.
No duplicated objects.
No deformed bottle.
No camera shake.

Soft luxurious atmospheric orchestral ambience.
""".strip()


# ============================================================
# HTTP
# ============================================================

def http(method, url, body=None, timeout=HTTP_TIMEOUT):
    """
    Send JSON HTTP request.

    Default timeout is intentionally very large because video generation
    servers may take a long time to answer under heavy load.
    """

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")

            if not raw:
                payload = None
            else:
                payload = json.loads(raw)

            return r.status, payload

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            error_body = ""

        raise RuntimeError(
            f"HTTP {e.code} {e.reason}\n"
            f"URL: {url}\n"
            f"BODY: {error_body}"
        ) from e

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Connection error: {e}\n"
            f"URL: {url}"
        ) from e


# ============================================================
# SERVER READY
# ============================================================

def wait_ready(base, max_wait=7200):
    print(
        "[server] waiting for sd-server...",
        flush=True,
    )

    t0 = time.time()

    while time.time() - t0 < max_wait:

        try:
            status, caps = http(
                "GET",
                f"{base}/sdcpp/v1/capabilities",
                timeout=60,
            )

            if status == 200:

                elapsed = time.time() - t0

                print(
                    f"[ready] server up after {elapsed:.1f}s",
                    flush=True,
                )

                print(
                    "[ready] supported modes:",
                    caps.get("supported_modes"),
                    flush=True,
                )

                return caps

        except Exception as e:
            print(
                f"[server] not ready: {e}",
                flush=True,
            )

        time.sleep(5)

    sys.exit(
        f"ERROR: server did not become ready after "
        f"{max_wait / 60:.0f} minutes."
    )


# ============================================================
# FFMPEG
# ============================================================

def get_ffmpeg():
    """
    Prefer imageio-ffmpeg if installed.
    Otherwise use system ffmpeg.
    """

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()

    except ImportError:
        return "ffmpeg"


# ============================================================
# SAVE JSON
# ============================================================

def save_json(path, data):
    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# FORMAT TIME
# ============================================================

def fmt_seconds(seconds):
    seconds = int(seconds)

    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate one high-quality MiniMax-H3 "
            "video through sd-server."
        )
    )

    parser.add_argument(
        "--base",
        default="http://127.0.0.1:1234",
        help="sd-server base URL",
    )

    parser.add_argument(
        "--out",
        default="hq_test",
        help="Output directory",
    )

    parser.add_argument(
        "--w",
        type=int,
        default=720,
        help="Generation width",
    )

    parser.add_argument(
        "--h",
        type=int,
        default=1280,
        help="Generation height",
    )

    parser.add_argument(
        "--frames",
        type=int,
        default=120,
        help="Number of video frames",
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=24,
        help="Video FPS",
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=40,
        help="Sampling steps",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed",
    )

    parser.add_argument(
        "--txt-cfg",
        type=float,
        default=1.0,
        help="Text CFG",
    )

    parser.add_argument(
        "--img-cfg",
        type=float,
        default=1.0,
        help="Image CFG",
    )

    parser.add_argument(
        "--generation-timeout",
        type=int,
        default=GENERATION_TIMEOUT,
        help="Total generation timeout in seconds",
    )

    args = parser.parse_args()


    # ========================================================
    # VALIDATION
    # ========================================================

    if args.w <= 0 or args.h <= 0:
        sys.exit("ERROR: invalid resolution.")

    if args.frames <= 0:
        sys.exit("ERROR: frames must be > 0.")

    if args.fps <= 0:
        sys.exit("ERROR: fps must be > 0.")

    if args.steps <= 0:
        sys.exit("ERROR: steps must be > 0.")


    # ========================================================
    # OUTPUT DIRECTORY
    # ========================================================

    os.makedirs(
        args.out,
        exist_ok=True,
    )


    # ========================================================
    # WAIT FOR SERVER
    # ========================================================

    caps = wait_ready(args.base)

    save_json(
        os.path.join(
            args.out,
            "capabilities.json",
        ),
        caps,
    )


    # ========================================================
    # DISPLAY SETTINGS
    # ========================================================

    duration = args.frames / args.fps

    print()
    print("=" * 72)
    print(" MINIMAX-H3 HIGH QUALITY VIDEO TEST")
    print("=" * 72)

    print(
        f" Resolution          : "
        f"{args.w} x {args.h}"
    )

    print(
        f" Frames              : "
        f"{args.frames}"
    )

    print(
        f" FPS                 : "
        f"{args.fps}"
    )

    print(
        f" Duration            : "
        f"{duration:.2f} sec"
    )

    print(
        f" Steps               : "
        f"{args.steps}"
    )

    print(
        f" Seed                : "
        f"{args.seed}"
    )

    print(
        f" txt_cfg             : "
        f"{args.txt_cfg}"
    )

    print(
        f" img_cfg             : "
        f"{args.img_cfg}"
    )

    print(
        f" HTTP timeout        : "
        f"{HTTP_TIMEOUT / 3600:.1f} hours"
    )

    print(
        f" Generation timeout  : "
        f"{args.generation_timeout / 3600:.1f} hours"
    )

    print("=" * 72)
    print()


    # ========================================================
    # REQUEST BODY
    # ========================================================

    body = {

        "prompt": PROMPT,

        "width": args.w,

        "height": args.h,

        "video_frames": args.frames,

        "fps": args.fps,

        "seed": args.seed,

        "sample_params": {

            "sample_steps": args.steps,

            "guidance": {

                "txt_cfg": args.txt_cfg,

                "img_cfg": args.img_cfg,
            },
        },

        "vae_tiling_params": {

            "enabled": True,

            "temporal_tiling": True,
        },

        "output_format": "webm",
    }


    # ========================================================
    # SAVE REQUEST
    # ========================================================

    request_path = os.path.join(
        args.out,
        "request.json",
    )

    save_json(
        request_path,
        body,
    )

    print(
        f"[request] saved: {request_path}",
        flush=True,
    )


    # ========================================================
    # SUBMIT
    # ========================================================

    print()
    print(
        "[submit] submitting generation...",
        flush=True,
    )

    submit_time = time.time()

    try:

        status, job = http(
            "POST",
            f"{args.base}/sdcpp/v1/vid_gen",
            body,
            timeout=HTTP_TIMEOUT,
        )

    except Exception as e:

        sys.exit(
            "\n"
            "ERROR submitting generation:\n"
            f"{e}"
        )


    if not isinstance(job, dict):

        sys.exit(
            f"ERROR: invalid server response:\n{job}"
        )


    jid = job.get("id")

    if not jid:

        sys.exit(
            "ERROR: server returned no job id.\n"
            f"{json.dumps(job, indent=2)}"
        )


    print(
        f"[submit] job id: {jid}",
        flush=True,
    )

    print(
        f"[submit] HTTP: {status}",
        flush=True,
    )

    print()


    # ========================================================
    # POLLING
    # ========================================================

    last_status = None
    last_queue = None

    poll_start = time.time()

    job = None


    while True:

        elapsed = time.time() - poll_start


        # ----------------------------------------------------
        # TOTAL GENERATION TIMEOUT
        # ----------------------------------------------------

        if elapsed > args.generation_timeout:

            sys.exit(
                "\n"
                "ERROR: generation exceeded maximum time.\n"
                f"Elapsed: {fmt_seconds(elapsed)}\n"
                f"Limit  : "
                f"{fmt_seconds(args.generation_timeout)}"
            )


        # ----------------------------------------------------
        # GET JOB
        # ----------------------------------------------------

        try:

            status, job = http(
                "GET",
                f"{args.base}/sdcpp/v1/jobs/{jid}",
                timeout=HTTP_TIMEOUT,
            )

        except Exception as e:

            print(
                f"[poll] temporary error: {e}",
                flush=True,
            )

            time.sleep(POLL_INTERVAL)

            continue


        if not isinstance(job, dict):

            print(
                f"[poll] invalid response: {job}",
                flush=True,
            )

            time.sleep(POLL_INTERVAL)

            continue


        job_status = job.get(
            "status",
            "unknown",
        )

        queue_position = job.get(
            "queue_position"
        )


        # ----------------------------------------------------
        # STATUS CHANGE
        # ----------------------------------------------------

        if (
            job_status != last_status
            or queue_position != last_queue
        ):

            print(
                f"[job] "
                f"status={job_status} "
                f"queue={queue_position} "
                f"elapsed={fmt_seconds(elapsed)}",
                flush=True,
            )

            last_status = job_status
            last_queue = queue_position


        # ----------------------------------------------------
        # FINISHED
        # ----------------------------------------------------

        if job_status in (
            "completed",
            "failed",
            "cancelled",
        ):
            break


        time.sleep(POLL_INTERVAL)


    done_time = time.time()


    # ========================================================
    # SAVE FINAL JOB RESPONSE
    # ========================================================

    job_json_path = os.path.join(
        args.out,
        "job_result.json",
    )

    save_json(
        job_json_path,
        job,
    )


    # ========================================================
    # FAILED
    # ========================================================

    if job.get("status") != "completed":

        print()
        print("=" * 72)
        print(" GENERATION FAILED")
        print("=" * 72)

        error = job.get("error")

        if error:

            print(
                json.dumps(
                    error,
                    indent=2,
                    ensure_ascii=False,
                )
            )

        else:

            print(
                json.dumps(
                    job,
                    indent=2,
                    ensure_ascii=False,
                )
            )


        print()
        print(
            f"Full job response saved to:\n"
            f"{job_json_path}"
        )

        print()
        print(
            "IMPORTANT:"
        )

        print(
            "If the error is:"
        )

        print(
            '  "generate_video returned no results"'
        )

        print(
            "then the backend generation itself failed."
        )

        print(
            "That is normally NOT an HTTP timeout."
        )

        print()
        print(
            "Try lowering one variable at a time:"
        )

        print(
            "  720x1280 / 120 frames / 40 steps"
        )

        print(
            "  720x1280 / 81 frames  / 40 steps"
        )

        print(
            "  720x1280 / 81 frames  / 30 steps"
        )

        sys.exit(1)


    # ========================================================
    # RESULT
    # ========================================================

    result = job.get("result")

    if not isinstance(result, dict):

        sys.exit(
            "ERROR: completed job has no result dictionary."
        )


    b64_data = result.get("b64_json")

    if not b64_data:

        sys.exit(
            "ERROR: completed job contains no b64_json video."
        )


    # ========================================================
    # DECODE WEBM
    # ========================================================

    print()
    print(
        "[result] decoding original video...",
        flush=True,
    )

    webm_path = os.path.join(
        args.out,
        f"{NAME}_ORIGINAL.webm",
    )


    try:

        video_bytes = base64.b64decode(
            b64_data
        )

    except Exception as e:

        sys.exit(
            f"ERROR decoding base64 video: {e}"
        )


    with open(
        webm_path,
        "wb",
    ) as f:

        f.write(
            video_bytes
        )


    original_mb = (
        len(video_bytes)
        / 1024
        / 1024
    )


    print(
        f"[result] original saved: {webm_path}",
        flush=True,
    )

    print(
        f"[result] original size: "
        f"{original_mb:.2f} MB",
        flush=True,
    )


    # ========================================================
    # FFMPEG
    # ========================================================

    ffmpeg_bin = get_ffmpeg()

    mp4_path = os.path.join(
        args.out,
        f"{NAME}_HQ.mp4",
    )

    print()
    print(
        "[ffmpeg] encoding HQ MP4...",
        flush=True,
    )


    cmd = [

        ffmpeg_bin,

        "-hide_banner",

        "-loglevel",
        "warning",

        "-y",

        "-i",
        webm_path,


        # --------------------------------------------
        # VIDEO
        # --------------------------------------------

        "-c:v",
        "libx264",

        "-preset",
        "slow",

        "-crf",
        "14",

        "-pix_fmt",
        "yuv420p",


        # Keep FPS
        "-r",
        str(args.fps),


        # --------------------------------------------
        # AUDIO
        # --------------------------------------------

        "-c:a",
        "aac",

        "-b:a",
        "256k",


        # --------------------------------------------
        # MP4 optimization
        # --------------------------------------------

        "-movflags",
        "+faststart",


        mp4_path,
    ]


    try:

        proc = subprocess.run(
            cmd,
            check=False,
        )

    except FileNotFoundError:

        proc = None

        print(
            "[ffmpeg] ERROR: ffmpeg not found.",
            flush=True,
        )


    if proc is None or proc.returncode != 0:

        print()
        print(
            "[ffmpeg] MP4 conversion failed."
        )

        print(
            "Original WebM is still available:"
        )

        print(
            webm_path
        )

    else:

        print(
            f"[ffmpeg] HQ MP4 saved: {mp4_path}",
            flush=True,
        )


    # ========================================================
    # GENERATION STATISTICS
    # ========================================================

    started = job.get("started")
    completed = job.get("completed")


    gen_seconds = None


    if (
        isinstance(started, (int, float))
        and isinstance(completed, (int, float))
    ):

        gen_seconds = (
            completed - started
        )


    wall_seconds = (
        done_time - submit_time
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 72)
    print(" COMPLETE")
    print("=" * 72)

    print(
        f"Resolution        : "
        f"{args.w} x {args.h}"
    )

    print(
        f"Requested frames  : "
        f"{args.frames}"
    )

    print(
        f"Returned frames   : "
        f"{result.get('frame_count', 'unknown')}"
    )

    print(
        f"FPS               : "
        f"{args.fps}"
    )

    print(
        f"Steps             : "
        f"{args.steps}"
    )

    print(
        f"Seed              : "
        f"{args.seed}"
    )


    if gen_seconds is not None:

        print(
            f"Generation time   : "
            f"{fmt_seconds(gen_seconds)}"
        )


    print(
        f"Total wall time   : "
        f"{fmt_seconds(wall_seconds)}"
    )

    print(
        f"Original WebM     : "
        f"{webm_path}"
    )


    if os.path.exists(mp4_path):

        print(
            f"HQ MP4            : "
            f"{mp4_path}"
        )


    print(
        f"Request JSON      : "
        f"{request_path}"
    )

    print(
        f"Job JSON          : "
        f"{job_json_path}"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()

