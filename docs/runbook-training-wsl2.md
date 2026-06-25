# Runbook — optional QLoRA self-improvement (WSL2)

This is the **stretch / optional** learning layer (M11). The agent already improves
without training via the verified **experience memory** (M9); fine-tuning bakes that
in but carries real toolchain risk on this exact box. **Build the smoke test first;
if it fails, stay on the memory and skip training — you lose almost nothing.**

> Only the **7B** (`Qwen2.5-Coder-7B-Instruct`) is trainable locally. The 30B-A3B
> MoE brain is **not** (4-bit QLoRA of MoE is unsupported; 16-bit LoRA ≈ 63 GB).

## Why WSL2 (the #1 gotcha)

bitsandbytes' NF4 kernels must load on the Blackwell (sm_120) GPU. The reliable
combo is **WSL2 Ubuntu + a cu128/cu129 PyTorch build + bitsandbytes 0.49.x**.
A **cu130** torch build breaks bitsandbytes, and native Windows + CUDA 13.x fails
with `no kernel image is available for execution on the device`. WSL2 works because
the Windows NVIDIA driver (CUDA 13.1) is forward-compatible with a cu128/cu129
runtime *inside* WSL2.

## Steps

1. **Open Ubuntu (WSL2)** — already installed (`wsl -d Ubuntu`).
2. **Install uv + Python 3.13** in WSL2 and create a venv.
3. **Install the pinned toolchain** (do NOT use cu130):
   ```bash
   # Unsloth's installer pulls Blackwell-tuned kernels the plain PyPI wheel lacks.
   curl -fsSL https://unsloth.ai/install.sh | sh
   # Ensure torch is cu128/cu129 and bitsandbytes is 0.49.x:
   pip install "bitsandbytes==0.49.*" "trl>=0.23" "datasets>=3" "transformers>=5"
   ```
4. **Smoke test (decisive gate):**
   ```bash
   python training/smoke_test.py
   ```
   - `SMOKE OK — one training step ran` → proceed.
   - `no kernel image is available` → **stop**; keep using experience memory only.
5. **Export the corpus** from verified experiences (run on Windows or WSL2):
   ```bash
   python training/export_dataset.py            # → data/sft.jsonl
   ```
   You need the agent to have accumulated verified successes first (use `lca ask
   --verify` for a while). Aim for at least a few dozen examples.
6. **Train (overnight is fine):**
   ```bash
   python training/train_qlora.py --max-steps 60   # → outputs/lca-7b-lora
   ```
7. **Champion/challenger — never auto-promote.** Evaluate the adapter against a
   frozen eval set and only adopt it if it beats the incumbent:
   ```bash
   # merge → F16 GGUF → quantize for serving
   #   model.save_pretrained_merged("outputs/merged-16bit", tokenizer, save_method="merged_16bit")
   #   python convert_hf_to_gguf.py outputs/merged-16bit --outfile lca-7b.f16.gguf
   #   llama-quantize lca-7b.f16.gguf lca-7b-q4_k_m.gguf Q4_K_M
   lca eval --no-verify   # compare pass-rate before/after; keep the winner
   ```
8. **Serve** the new GGUF by placing it in LM Studio's models dir and pointing
   `LCA_LLM__FAST_MODEL` at it. (Merging into F16 then quantizing preserves quality;
   don't ship an NF4-trained adapter applied to a Q4 base unverified.)

## Honest expectations

RFT *sharpens* existing ability on your recurring workload; it does not add
fundamentally new skills. Treat it as a distant 4th lever after (1) the execution
oracle + best-of-N, (2) the verified-write memory, and (3) calibrated abstention.
