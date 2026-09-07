"""Bake a PEFT/ComfyUI LoRA into a bf16 safetensors DiT, streaming tensor-by-tensor (fits in <4GB RAM).

W' = W + multiplier * (alpha / rank) * (B @ A)

Usage:
  python bake_lora.py --base models/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors ^
                      --lora models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors ^
                      --out  models/diffusion_models/minimax_h3_fl2va_pruned_turbo8_bf16.safetensors [--mult 1.0] [--device cpu]
"""
import argparse, json, os, struct, time
import torch
from safetensors import safe_open

DTYPE_MAP = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32}
DTYPE_SIZE = {"BF16": 2, "F16": 2, "F32": 4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--lora", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mult", type=float, default=1.0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--prefix", default="diffusion_model.", help="LoRA key prefix to strip")
    ap.add_argument("--allow-missing", action="store_true", help="skip LoRA modules absent from base (testing)")
    a = ap.parse_args()

    # --- read base header (dtype/shape/order) without loading data
    with open(a.base, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
    meta = header.pop("__metadata__", None)
    keys = list(header.keys())  # keep original order

    # --- index LoRA modules
    lora = safe_open(a.lora, "pt")
    mods = {}
    for k in lora.keys():
        if k.endswith(".lora_A.weight"):
            mods.setdefault(k[: -len(".lora_A.weight")], {})["A"] = k
        elif k.endswith(".lora_B.weight"):
            mods.setdefault(k[: -len(".lora_B.weight")], {})["B"] = k
        elif k.endswith(".alpha"):
            mods.setdefault(k[: -len(".alpha")], {})["alpha"] = k
    target = {}
    for m, parts in mods.items():
        base_key = (m[len(a.prefix):] if m.startswith(a.prefix) else m) + ".weight"
        if base_key not in header:
            if a.allow_missing:
                continue
            raise SystemExit(f"LoRA module {m} -> {base_key} not found in base")
        target[base_key] = parts
    print(f"base tensors={len(keys)}  lora modules={len(mods)}  matched={len(target)}", flush=True)

    # --- build output header up-front (shapes/dtypes unchanged)
    out_header = {}
    off = 0
    for k in keys:
        info = header[k]
        size = DTYPE_SIZE[info["dtype"]]
        for d in info["shape"]:
            size *= d
        out_header[k] = {"dtype": info["dtype"], "shape": info["shape"], "data_offsets": [off, off + size]}
        off += size
    out_meta = dict(meta or {})
    out_meta.update({"baked_lora": os.path.basename(a.lora), "baked_multiplier": str(a.mult)})
    hb = json.dumps({"__metadata__": out_meta, **out_header}, separators=(",", ":")).encode()
    hb += b" " * ((8 - len(hb) % 8) % 8)

    dev = torch.device(a.device)
    t0 = time.time()
    merged = 0
    # plain seek/read instead of safetensors mmap: safe_open segfaults on this 37GB file on Windows
    data_start = 8 + n
    fin = open(a.base, "rb", buffering=0)

    def read_base(k):
        info = header[k]
        o0, o1 = info["data_offsets"]
        fin.seek(data_start + o0)
        buf = bytearray(o1 - o0)
        view = memoryview(buf); got = 0
        while got < len(buf):
            r = fin.readinto(view[got:])
            if not r:
                raise SystemExit(f"short read on {k}")
            got += r
        t = torch.frombuffer(buf, dtype=DTYPE_MAP[info["dtype"]])
        return t.reshape(info["shape"]) if info["shape"] else t.reshape(())

    with open(a.out, "wb") as out:
        out.write(struct.pack("<Q", len(hb)))
        out.write(hb)
        for i, k in enumerate(keys):
            t = read_base(k)
            if k in target:
                p = target[k]
                A = lora.get_tensor(p["A"]).to(dev, torch.float32)
                B = lora.get_tensor(p["B"]).to(dev, torch.float32)
                rank = A.shape[0]
                alpha = float(lora.get_tensor(p["alpha"])) if "alpha" in p else float(rank)
                scale = a.mult * alpha / rank
                delta = (B @ A) * scale
                if delta.shape != t.shape:
                    raise SystemExit(f"shape mismatch {k}: base {tuple(t.shape)} vs delta {tuple(delta.shape)}")
                t = (t.to(dev, torch.float32) + delta).to(DTYPE_MAP[header[k]["dtype"]]).cpu().contiguous()
                merged += 1
            else:
                t = t.contiguous()
            # raw little-endian bytes of the tensor (numpy has no bf16 -> reinterpret as int16)
            out.write(t.numpy().tobytes() if t.dtype != torch.bfloat16 else t.view(torch.int16).numpy().tobytes())
            if i % 50 == 0 or k in target and merged % 20 == 0:
                print(f"[{i+1}/{len(keys)}] merged={merged} {time.time()-t0:.0f}s", flush=True)
    fin.close()
    print(f"done: merged {merged}/{len(target)} modules -> {a.out} ({os.path.getsize(a.out)/1e9:.2f} GB) in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
