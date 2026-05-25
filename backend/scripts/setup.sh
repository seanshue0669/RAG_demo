#!/usr/bin/env bash
# setup.sh — Initialize the Cloud RAG Security Demo backend environment.
#
# Usage:
#   chmod +x backend/scripts/setup.sh     # one-time, run manually
#   bash backend/scripts/setup.sh
#
# What it does:
#   1. Verifies conda is installed.
#   2. Creates the `cloud-rag-security` env (Python 3.10) if missing.
#   3. Installs requirements.txt into that env.
#   4. Attempts `pip install tenseal`. On ARM64 there may be no wheel; if the
#      install fails this script prints source-build guidance and exits 0
#      (letting the user decide whether to build).
#
# Target platform: ARM64 (NVIDIA DGX GB10), Python 3.10.

set -uo pipefail

ENV_NAME="cloud-rag-security"
PY_VERSION="3.10"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQ_FILE="${BACKEND_DIR}/requirements.txt"

echo "==> Cloud RAG Security Demo — backend setup"
echo "    backend dir : ${BACKEND_DIR}"
echo "    env name    : ${ENV_NAME}"
echo "    python      : ${PY_VERSION}"
echo

# ---------------------------------------------------------------------------
# 1. Check conda
# ---------------------------------------------------------------------------
if ! command -v conda >/dev/null 2>&1; then
    echo "ERROR: conda is not installed or not on PATH."
    echo "Please install Miniconda first:"
    echo "  https://docs.conda.io/projects/miniconda/en/latest/"
    echo "For ARM64 Linux, use the aarch64 installer:"
    echo "  https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
    exit 1
fi

# shellcheck disable=SC1091
CONDA_BASE="$(conda info --base)"
source "${CONDA_BASE}/etc/profile.d/conda.sh"

# ---------------------------------------------------------------------------
# 2. Create env if missing
# ---------------------------------------------------------------------------
if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    echo "==> Conda env '${ENV_NAME}' already exists, skipping creation."
else
    echo "==> Creating conda env '${ENV_NAME}' with python=${PY_VERSION}..."
    conda create -y -n "${ENV_NAME}" "python=${PY_VERSION}"
fi

# ---------------------------------------------------------------------------
# 3. Activate and install requirements
# ---------------------------------------------------------------------------
echo "==> Activating env '${ENV_NAME}'..."
conda activate "${ENV_NAME}"

if [[ ! -f "${REQ_FILE}" ]]; then
    echo "ERROR: requirements file not found: ${REQ_FILE}"
    exit 1
fi

echo "==> Upgrading pip..."
python -m pip install --upgrade pip

echo "==> Installing backend requirements..."
# Install everything except tenseal first; we handle tenseal separately so
# that an ARM64 wheel failure does not block the rest of the install.
grep -v -i '^tenseal' "${REQ_FILE}" > /tmp/requirements.no-tenseal.txt
pip install -r /tmp/requirements.no-tenseal.txt
rm -f /tmp/requirements.no-tenseal.txt

# ---------------------------------------------------------------------------
# 4. TenSEAL — best-effort install
# ---------------------------------------------------------------------------
echo "==> Attempting to install TenSEAL via pip..."
if pip install tenseal; then
    echo "==> TenSEAL installed successfully."
else
    cat <<'EOF'

------------------------------------------------------------------
WARNING: `pip install tenseal` failed.

This commonly happens on ARM64 / aarch64 because there is no
pre-built wheel for TenSEAL on this architecture. You have two
options:

  (a) Build TenSEAL from source. See:
        https://github.com/OpenMined/TenSEAL#installation
      Quick start:
        sudo apt-get install -y build-essential cmake git
        git clone https://github.com/OpenMined/TenSEAL.git
        cd TenSEAL
        git submodule update --init --recursive
        pip install .

  (b) Skip the homomorphic-encryption demo. Act 4 (HE search)
      will be unavailable, but Acts 1–3 will still run.

This setup script will now exit cleanly (code 0). Re-run after
TenSEAL is available, or proceed without it.
------------------------------------------------------------------
EOF
    exit 0
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
echo "==> Setup complete."
echo "    Activate the env with:"
echo "        conda activate ${ENV_NAME}"
echo "    Then start the backend with:"
echo "        cd ${BACKEND_DIR%/backend}"
echo "        python -m backend.main"
echo "    or:"
echo "        uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
