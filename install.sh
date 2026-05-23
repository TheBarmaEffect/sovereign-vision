#!/usr/bin/env bash
# Sovereign Vision - one-line installer for Apple Silicon.
#
# Run with:
#   curl -sSL https://raw.githubusercontent.com/TheBarmaEffect/sovereign-vision/main/install.sh | sh

set -euo pipefail

ROOT_DIR="${SOVEREIGN_DIR:-$HOME/sovereign-vision}"
PY_BIN="${PYTHON_BIN:-python3}"
REPO_URL="https://github.com/TheBarmaEffect/sovereign-vision.git"
YOLO_MLX_URL="https://github.com/thewebAI/yolo-mlx.git"

color() { printf "\033[%sm%s\033[0m" "$1" "$2"; }
log()   { printf "%s %s\n" "$(color 36 "==>")" "$*"; }
warn()  { printf "%s %s\n" "$(color 33 "!!!")" "$*"; }
die()   { printf "%s %s\n" "$(color 31 "xxx")" "$*"; exit 1; }

# -- Preflight ---------------------------------------------------------------

uname_s=$(uname -s)
uname_m=$(uname -m)
if [[ "$uname_s" != "Darwin" || "$uname_m" != "arm64" ]]; then
  warn "Detected $uname_s/$uname_m. MLX is Apple Silicon only; the simulation backend will be used."
fi

if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  die "Python 3 not found. Install Python 3.10+ first (e.g. brew install python@3.12)."
fi

if ! command -v git >/dev/null 2>&1; then
  die "git not found. Install Xcode command-line tools first."
fi

# -- Clone -------------------------------------------------------------------

if [[ ! -d "$ROOT_DIR" ]]; then
  log "Cloning Sovereign Vision into $ROOT_DIR"
  git clone --depth 1 "$REPO_URL" "$ROOT_DIR"
else
  log "$ROOT_DIR already exists; pulling latest"
  (cd "$ROOT_DIR" && git pull --ff-only)
fi

cd "$ROOT_DIR"

# -- Venv --------------------------------------------------------------------

if [[ ! -d .venv ]]; then
  log "Creating Python venv (.venv)"
  "$PY_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

log "Installing Sovereign Vision dependencies"
pip install --upgrade pip >/dev/null
pip install -e . >/dev/null

# -- Optional YOLO26 MLX -----------------------------------------------------

if [[ ! -d "$ROOT_DIR/yolo-mlx" ]]; then
  log "Cloning YOLO26 MLX (this enables real inference)"
  git clone --depth 1 "$YOLO_MLX_URL" "$ROOT_DIR/yolo-mlx" || warn "yolo-mlx clone failed; demo will use simulation backend"
fi

if [[ -d "$ROOT_DIR/yolo-mlx" ]]; then
  log "Installing yolo-mlx (this can take a minute)"
  pip install -e "$ROOT_DIR/yolo-mlx" >/dev/null 2>&1 || warn "yolo-mlx install failed; demo will use simulation backend"
fi

# -- Doctor ------------------------------------------------------------------

log "Running sovereign doctor"
sovereign doctor || true

# -- Done --------------------------------------------------------------------

cat <<EOF

$(color 32 "Sovereign Vision is installed.")
Next steps:
  cd $ROOT_DIR
  source .venv/bin/activate
  sovereign demo                    # run the live dashboard
  sovereign demo --production       # production mode (suppresses raw panel)
  pytest tests/ -m constitutional   # run the zero-PII proofs

Built by Karthik Barma  ·  https://github.com/TheBarmaEffect
EOF
