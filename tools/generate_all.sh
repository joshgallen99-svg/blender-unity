#!/usr/bin/env bash
# Regenerate every generated asset: Blender models + terrain data/textures.
# Usage: tools/generate_all.sh [python]   (python must have bpy, numpy, scipy, pillow)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${1:-python3}"
"$PY" blender/vehicles/ridgeback.py
"$PY" blender/props/desert_props.py
"$PY" tools/terrain/generate_desert.py
echo "All assets regenerated."
