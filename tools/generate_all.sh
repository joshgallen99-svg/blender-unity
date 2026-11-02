#!/usr/bin/env bash
# Regenerate every generated asset: Blender models + terrain data/textures, all regions.
# Usage: tools/generate_all.sh [python]   (python must have bpy, numpy, scipy, pillow, scikit-image)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${1:-python3}"
"$PY" tools/art/generate_foliage_textures.py
"$PY" tools/art/generate_material_textures.py
"$PY" tools/art/generate_terrain_textures.py
"$PY" tools/art/generate_forest_textures.py
"$PY" tools/art/generate_alpine_textures.py
"$PY" blender/vehicles/fleet.py
"$PY" blender/props/desert_props.py
"$PY" blender/props/forest_props.py
"$PY" blender/props/alpine_props.py
"$PY" blender/landmarks/desert_landmarks.py
"$PY" blender/landmarks/forest_landmarks.py
"$PY" blender/landmarks/alpine_landmarks.py
"$PY" blender/formations/sandstone_formations.py
"$PY" blender/formations/granite_formations.py
"$PY" blender/formations/alpine_formations.py
"$PY" tools/terrain/generate_desert.py
"$PY" tools/terrain/generate_forest.py
"$PY" tools/terrain/generate_alpine.py
echo "All assets regenerated."
