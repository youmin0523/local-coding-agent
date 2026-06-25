"""QLoRA rejection-sampling fine-tune of the 7B on verified experiences (WSL2).

Trains ONLY the 7B fallback model (the 30B-A3B MoE is not locally trainable:
4-bit QLoRA of MoE is unsupported and 16-bit LoRA needs ~63 GB). The corpus is the
execution-verified experience set exported by export_dataset.py — so we only ever
learn from things that actually worked (STaR/RFT).

After training, promote the adapter ONLY if it beats the incumbent on a frozen eval
set (champion/challenger — never auto-promote). Serve via merge→F16→Q4_K_M (see
docs/runbook-training-wsl2.md).

Run inside WSL2 Ubuntu; see the runbook for the exact pinned toolchain.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MODEL = "unsloth/Qwen2.5-Coder-7B-Instruct"
CHAT = "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n{response}<|im_end|>"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/sft.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("outputs/lca-7b-lora"))
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--seq-len", type=int, default=2048)
    parser.add_argument("--rank", type=int, default=16)
    args = parser.parse_args()

    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL, max_seq_length=args.seq_len, load_in_4bit=True
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
    )

    dataset = load_dataset("json", data_files=str(args.data))["train"]
    dataset = dataset.map(lambda ex: {"text": CHAT.format(**ex)})

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            warmup_steps=5,
            max_steps=args.max_steps,
            learning_rate=2e-4,
            optim="paged_adamw_8bit",  # paged optimizer keeps 8GB feasible
            logging_steps=1,
            output_dir=str(args.out),
            seed=42,
        ),
    )
    trainer.train()

    model.save_pretrained(str(args.out))  # LoRA adapter
    tokenizer.save_pretrained(str(args.out))
    # For serving, also export a merged GGUF (see runbook):
    #   model.save_pretrained_merged("outputs/merged-16bit", tokenizer, save_method="merged_16bit")
    #   then: llama-quantize merged.f16.gguf model-q4_k_m.gguf Q4_K_M
    print(f"saved LoRA adapter to {args.out}")


if __name__ == "__main__":
    main()
