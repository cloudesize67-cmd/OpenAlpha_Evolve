#!/data/data/com.termux/files/usr/bin/bash
# termux_local_model.sh — free, offline, unlimited local LLM on Android/Termux.
# This is the FINAL fallback in core/free_model_router.py ("local" provider).
# It runs llama.cpp's OpenAI-compatible server on http://127.0.0.1:8080/v1
#
# Why local: every cloud free tier can shrink or vanish (Cerebras cut its
# free catalog from ~12 models to 2 in one week). A local model on your own
# phone can never be rate-limited, never trains on your prompts, and never
# sends your evolution seeds/evaluators anywhere. That protects the core
# law: never leak seeds, tests, or reference implementations into prompts.
#
# Hardware reality check (be honest with yourself):
#   A phone runs 1B-4B parameter models at usable speed. These are WEAKER
#   than Groq/Gemini free tiers. Use local for batch/background work and as
#   outage insurance — use the cloud chain for elite refinement steps.
#
# Usage:  bash scripts/termux_local_model.sh        (install + download + run)
#         bash scripts/termux_local_model.sh run    (just start the server)

set -e

MODEL_REPO="unsloth/Qwen3-4B-GGUF"     # small, strong, free open weights
MODEL_FILE="Qwen3-4B-Q4_K_M.gguf"      # ~2.5 GB download, ~3 GB RAM at runtime
MODEL_DIR="$HOME/models"
PORT=8080

install_deps() {
    pkg update -y
    pkg install -y git cmake make clang wget
    # llama.cpp: build the server binary
    if [ ! -d "$HOME/llama.cpp" ]; then
        git clone --depth 1 https://github.com/ggml-org/llama.cpp "$HOME/llama.cpp"
    fi
    cd "$HOME/llama.cpp"
    cmake -B build -DGGML_NATIVE=OFF
    cmake --build build --config Release -j"$(nproc)" --target llama-server
    echo "llama-server built at $HOME/llama.cpp/build/bin/llama-server"
}

download_model() {
    mkdir -p "$MODEL_DIR"
    if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
        echo "Downloading $MODEL_FILE (~2.5 GB) — wifi recommended"
        wget -c "https://huggingface.co/$MODEL_REPO/resolve/main/$MODEL_FILE" \
             -O "$MODEL_DIR/$MODEL_FILE"
    fi
    echo "Model ready: $MODEL_DIR/$MODEL_FILE"
}

run_server() {
    echo "Starting local model on http://127.0.0.1:$PORT/v1 (OpenAI-compatible)"
    echo "Test it:  curl http://127.0.0.1:$PORT/v1/models"
    "$HOME/llama.cpp/build/bin/llama-server" \
        -m "$MODEL_DIR/$MODEL_FILE" \
        --host 127.0.0.1 --port "$PORT" \
        -c 4096 \
        -t "$(nproc)"
}

case "${1:-all}" in
    run) run_server ;;
    *)   install_deps && download_model && run_server ;;
esac
