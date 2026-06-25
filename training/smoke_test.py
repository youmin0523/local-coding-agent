"""WSL2 QLoRA smoke test — run THIS before building any training pipeline.

The single biggest risk on this exact box is the training toolchain, not the
training math: bitsandbytes NF4 must actually load on the Blackwell (sm_120) GPU.
The supported path is WSL2 + a cu128/cu129 torch build + bitsandbytes 0.49.x
(NOT a cu130 build, and NOT native Windows with CUDA 13.x — that combo fails).

If this script prints "SMOKE OK", QLoRA fine-tuning is viable; if it errors with
"no kernel image is available", stay on the weight-free experience memory (which
already delivers most of the self-improvement benefit) and do not proceed.

Run inside WSL2 Ubuntu after following docs/runbook-training-wsl2.md.
"""

from __future__ import annotations


def main() -> None:
    import torch

    print("torch:", torch.__version__, "cuda runtime:", torch.version.cuda)
    print("cuda available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available inside WSL2 — check the NVIDIA WSL driver.")
    print("device:", torch.cuda.get_device_name(0))

    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-Coder-7B-Instruct",
        max_seq_length=512,
        load_in_4bit=True,  # this is the bitsandbytes NF4 path under test
    )
    model = FastLanguageModel.get_peft_model(
        model, r=8, lora_alpha=16, use_gradient_checkpointing="unsloth"
    )

    batch = tokenizer("def add(a, b):\n    return a + b\n", return_tensors="pt").to("cuda")
    out = model(**batch, labels=batch["input_ids"])
    out.loss.backward()  # one backward step exercises the optimizer kernels
    print(f"SMOKE OK — one training step ran. loss={float(out.loss):.4f}")


if __name__ == "__main__":
    main()
