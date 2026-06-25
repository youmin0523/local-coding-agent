# ADR 0001 — Inference engine: llama.cpp via LM Studio, Ollama as fallback

## Status
Accepted.

## Context
8 GB VRAM Blackwell (sm_120) laptop on Windows 11 with CUDA 13.1. Raw llama.cpp
prebuilts didn't ship sm_120 in the default arch list; building is fragile.

## Decision
Use **llama.cpp `llama-server`** as the engine, installed/managed via **LM Studio**
(its bundled CUDA-12.8 runtime supports Blackwell with no compiling). Keep **Ollama**
as a swappable fallback. The agent depends only on the `LLMProvider` interface, so
the engine is a config choice.

## Consequences
- Get GBNF grammar constraints + OpenAI-compatible API without build pain.
- LM Studio's OpenAI server doesn't expose raw `grammar` for every path; where grammar
  matters (judges) we degrade gracefully to native tool calling + Pydantic validation.
- Brain model (30B-A3B MoE) needs `--n-cpu-moe` expert offload to fit 8 GB.
