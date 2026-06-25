# Runbook — engine + GPU setup (M0)

Goal: get a Blackwell-accelerated local engine serving the two models, then prove
GPU offload actually works **before** trusting anything above it. The #1 failure on
this hardware is a CUDA/Blackwell mismatch silently falling back to CPU (5–10× too
slow) or an iGPU grabbing the workload.

## Hardware (this machine)

RTX 5070 Laptop (Blackwell sm_120, **8 GB VRAM**) · Ryzen 9 8940HX · 32 GB RAM ·
Windows 11 · CUDA 13.1 driver. Hybrid graphics (AMD Radeon 610M iGPU also present).

## Already done (by setup)

- ✅ LM Studio installed (`winget install ElementLabs.LMStudio`).
- ✅ Models downloaded to `%USERPROFILE%\.lmstudio\models\lmstudio-community\`:
  - `Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf` (~4.4 GB) — fast model, fully GPU-resident.
  - `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` (~17 GB) — brain (MoE, CPU-offload).

## 1. Force the discrete GPU (hybrid-graphics footgun)

- Windows Settings → System → Display → Graphics → add LM Studio → **High
  performance (NVIDIA)**.
- When launching a headless engine yourself, set `CUDA_VISIBLE_DEVICES=0`.
- Don't put both CUDA 12.x and 13.x runtime DLLs on PATH.

## 2. Serve the models

### Option A — LM Studio (simplest, Blackwell-ready)
1. Open LM Studio once; it selects the **CUDA 12.8 llama.cpp runtime** (handles sm_120).
2. Load **Qwen2.5-Coder-7B** first (it fits fully in 8 GB). Set context **8–16K**
   (not the model max). Enable GPU offload (all layers).
3. Start the local server (Developer tab → Start Server) on port **1234**.
4. Point lca at it:
   ```
   setx LCA_LLM__BASE_URL http://127.0.0.1:1234/v1
   setx LCA_PROFILE fast            # use the 7B until the 30B is tuned
   ```
   (LM Studio reports model ids; set `LCA_LLM__FAST_MODEL` to match if needed.)

### Option B — the 30B-A3B brain via `--n-cpu-moe` (more capable, ~12–15 tok/s)
The MoE needs expert offload to fit 8 GB. With a raw `llama-server` build:
```
llama-server -m Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf -c 16384 --n-cpu-moe 28 --port 8080 --jinja
```
Tune `--n-cpu-moe` down from a high value until it stops OOMing. `--jinja` enables
tool calling. Then `setx LCA_LLM__BASE_URL http://127.0.0.1:8080/v1` and
`setx LCA_PROFILE quality`.

## 3. Verify (the M0 gate)

```
uv run lca doctor
```
Expect: discrete GPU **present** (RTX 5070), engine **reachable**, context window
8–16K. If `doctor` says NOT READY, fix it before going further.

Then a real end-to-end check:
```
uv run lca index .
uv run lca ask "create hello.py that prints hi, then run it" --auto
uv run lca ask "what does add() do?" --route --verify
uv run lca web        # browser UI at http://127.0.0.1:8765
```

If tok/s feels like single digits with no VRAM used, you're on CPU fallback —
revisit steps 1–2 (this is the thing to catch early).

## 4. (Optional) Speculative decoding — make the 30B faster

The brain (30B-A3B, partly CPU-offloaded) runs ~12-15 tok/s. **Speculative decoding**
uses the small 7B as a *draft*: it proposes a few tokens, the 30B verifies them in
one batched pass, and accepted tokens are nearly free. Output is identical to the
30B alone, but throughput typically rises ~1.5-2x. That headroom is what makes the
router's best-of-N (up to 5 candidates on hard tasks) practical.

- **LM Studio**: in the model's load settings, enable *Speculative Decoding* and
  pick the 7B (`qwen2.5-coder-7b-instruct`) as the draft model for the 30B.
- **llama-server**: load a draft model alongside the main one, e.g.
  `llama-server -m qwen3-coder-30b-a3b.gguf -md qwen2.5-coder-7b.gguf --draft-max 16
  --draft-min 1 -ngl 99 --n-cpu-moe ...`. The draft should be small and share the
  tokenizer family (Qwen <-> Qwen here).

Trade-off: both models occupy memory at once. On 8 GB, keep the 7B draft on GPU and
the 30B experts on CPU (`--n-cpu-moe`); watch VRAM with `lca doctor`. If it doesn't
fit, skip it — it's a speed optimization, not a correctness requirement.
