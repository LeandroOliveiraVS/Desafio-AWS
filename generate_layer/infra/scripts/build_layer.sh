#!/usr/bin/env bash
# Gera infra/build/layer.zip com as dependências da Lambda para o runtime da AWS.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQUIREMENTS="$INFRA_DIR/../app/requirements.txt"
BUILD_DIR="$INFRA_DIR/build"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
PLATFORM="${PLATFORM:-manylinux2014_x86_64}"

rm -rf "$BUILD_DIR/layer" "$BUILD_DIR/layer.zip"
mkdir -p "$BUILD_DIR/layer/python"

python3 -m pip install \
  --quiet \
  --requirement "$REQUIREMENTS" \
  --target "$BUILD_DIR/layer/python" \
  --platform "$PLATFORM" \
  --implementation cp \
  --python-version "$PYTHON_VERSION" \
  --only-binary=:all:

find "$BUILD_DIR/layer/python" -type d -name "__pycache__" -prune -exec rm -rf {} +

(cd "$BUILD_DIR/layer" && zip -qr9 "$BUILD_DIR/layer.zip" python)
rm -rf "$BUILD_DIR/layer"

echo "Layer gerada em $BUILD_DIR/layer.zip ($(du -h "$BUILD_DIR/layer.zip" | cut -f1))"
