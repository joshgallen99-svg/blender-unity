using System;
using Offroad.Vehicles;
using UnityEngine;

namespace Offroad.World
{
    /// <summary>Maps a terrain's paint layers (and any other collider) to tyre surface properties.</summary>
    [RequireComponent(typeof(Terrain))]
    public class TerrainSurfaces : MonoBehaviour, ISurfaceProvider
    {
        [Serializable]
        public struct LayerSurface
        {
            public string name;
            public float grip, traction, drag, dust;
            public Color dustColor;
            [Tooltip("How far a tyre settles into this ground (m).")]
            public float sink;
            [Tooltip("Which tyre rating applies here: 0 sand, 1 gravel, 2 soil/dirt, 3 rock.")]
            public int tyreClass;

            public LayerSurface(string name, float grip, float traction, float drag, float dust, Color dustColor, float sink = 0f, int tyreClass = -1)
            {
                this.name = name; this.grip = grip; this.traction = traction; this.drag = drag;
                this.dust = dust; this.dustColor = dustColor; this.sink = sink; this.tyreClass = tyreClass;
            }
        }

        public LayerSurface[] layers =
        {
            new LayerSurface("Sand", 0.84f, 0.8f, 0.55f, 1.0f, new Color(0.86f, 0.62f, 0.42f), 0.035f, 0),
            new LayerSurface("Gravel", 0.93f, 0.95f, 0.08f, 0.7f, new Color(0.64f, 0.54f, 0.45f), 0.008f, 1),
            new LayerSurface("CrackedSoil", 1.0f, 1.0f, 0.03f, 0.85f, new Color(0.80f, 0.66f, 0.52f), 0.012f, 2),
            new LayerSurface("RedRock", 1.12f, 1.0f, 0.0f, 0.25f, new Color(0.62f, 0.38f, 0.27f), 0f, 3),
        };
        public LayerSurface objects = new LayerSurface("Rock", 1.1f, 1.0f, 0f, 0.15f, new Color(0.6f, 0.4f, 0.3f));

        [Header("Hazards")]
        [Tooltip("Readable RGBA map over the terrain: R wet mud, G quicksand, B washboard, A standing water.")]
        public Texture2D hazardMap;
        public LayerSurface mud = new LayerSurface("Mud", 0.62f, 0.62f, 0.75f, 1.0f, new Color(0.30f, 0.21f, 0.15f));
        public LayerSurface quicksand = new LayerSurface("Quicksand", 0.55f, 0.4f, 1.2f, 0.6f, new Color(0.62f, 0.5f, 0.38f));
        [Tooltip("Hazard map green = water depth / 2.5 m (rivers) instead of quicksand.")]
        public bool greenIsWater;
        public Color splashColor = new Color(0.85f, 0.9f, 0.95f);

        /// <summary>Default physics layers for the forest valley (forest floor, meadow, soil, rock).</summary>
        public static LayerSurface[] ForestLayers() => new[]
        {
            new LayerSurface("ForestFloor", 0.95f, 0.92f, 0.12f, 0.35f, new Color(0.33f, 0.30f, 0.22f), 0.03f, 2),
            new LayerSurface("Meadow", 0.9f, 0.9f, 0.1f, 0.25f, new Color(0.45f, 0.42f, 0.30f), 0.025f, 2),
            new LayerSurface("Soil", 0.93f, 0.9f, 0.08f, 0.6f, new Color(0.36f, 0.26f, 0.18f), 0.035f, 2),
            new LayerSurface("Granite", 1.1f, 1.0f, 0.0f, 0.12f, new Color(0.55f, 0.55f, 0.53f), 0f, 3),
        };

        Terrain _terrain;
        TerrainCollider _collider;
        float[,,] _alpha;
        int _w, _h, _n;

        void Awake()
        {
            _terrain = GetComponent<Terrain>();
            _collider = GetComponent<TerrainCollider>();
            var td = _terrain.terrainData;
            if (td == null) return;
            _w = td.alphamapWidth;
            _h = td.alphamapHeight;
            _n = td.alphamapLayers;
            if (_n > 0) _alpha = td.GetAlphamaps(0, 0, _w, _h);
        }

        public SurfaceInfo GetSurface(Vector3 worldPoint, Collider collider)
        {
            if (collider != _collider || _alpha == null) return ToInfo(objects);
            var td = _terrain.terrainData;
            Vector3 local = worldPoint - _terrain.transform.position;
            int x = Mathf.Clamp(Mathf.RoundToInt(local.x / td.size.x * (_w - 1)), 0, _w - 1);
            int z = Mathf.Clamp(Mathf.RoundToInt(local.z / td.size.z * (_h - 1)), 0, _h - 1);

            var s = new SurfaceInfo { dustColor = Color.clear };
            float total = 0f;
            int n = Mathf.Min(_n, layers.Length);
            for (int i = 0; i < n; i++)
            {
                float wgt = _alpha[z, x, i];
                if (wgt <= 0f) continue;
                var l = layers[i];
                s.grip += l.grip * wgt;
                s.traction += l.traction * wgt;
                s.drag += l.drag * wgt;
                s.dust += l.dust * wgt;
                s.dustColor += l.dustColor * wgt;
                s.sink += l.sink * wgt;
                int cls = l.tyreClass >= 0 && l.tyreClass < 4 ? l.tyreClass : i;
                s.layers[cls] += wgt;
                total += wgt;
            }
            if (total <= 1e-4f) return SurfaceInfo.Default;
            float inv = 1f / total;
            s.grip *= inv; s.traction *= inv; s.drag *= inv; s.dust *= inv; s.sink *= inv;
            s.dustColor *= inv;
            s.dustColor.a = 1f;
            if (hazardMap != null) ApplyHazards(ref s, local.x / td.size.x, local.z / td.size.z);
            return s;
        }

        /// <summary>Hazard values (mud, quicksand, washboard, water) at a normalised terrain position.</summary>
        public Color HazardAt(float u, float v) => hazardMap != null ? hazardMap.GetPixelBilinear(u, v) : Color.clear;

        void ApplyHazards(ref SurfaceInfo s, float u, float v)
        {
            var hz = hazardMap.GetPixelBilinear(u, v);
            float mudW = Mathf.Clamp01(Mathf.Max(hz.r, hz.a));
            float quick = greenIsWater ? 0f : Mathf.Clamp01(hz.g);
            if (mudW > 0.02f) Blend(ref s, mud, mudW);
            if (quick > 0.02f) Blend(ref s, quicksand, quick);
            s.mud = mudW;
            s.quicksand = quick;
            if (greenIsWater && hz.g > 0.004f)
            {
                s.water = hz.g * 2.5f;
                float wet = Mathf.Clamp01(s.water * 4f);
                s.dust = Mathf.Max(s.dust, wet);
                s.dustColor = Color.Lerp(s.dustColor, splashColor, wet);
                s.grip *= Mathf.Lerp(1f, 0.85f, wet);
                s.sink = 0f;
            }
            s.washboard = Mathf.Clamp01(hz.b);
        }

        static void Blend(ref SurfaceInfo s, in LayerSurface l, float t)
        {
            s.grip = Mathf.Lerp(s.grip, l.grip, t);
            s.traction = Mathf.Lerp(s.traction, l.traction, t);
            s.drag = Mathf.Lerp(s.drag, l.drag, t);
            s.dust = Mathf.Lerp(s.dust, l.dust, t);
            s.dustColor = Color.Lerp(s.dustColor, l.dustColor, t);
        }

        static SurfaceInfo ToInfo(in LayerSurface l) => new SurfaceInfo
        {
            grip = l.grip, traction = l.traction, drag = l.drag, dust = l.dust, dustColor = l.dustColor,
            layers = new Vector4(0f, 0f, 0f, 1f),   // props are rock
        };
    }
}
