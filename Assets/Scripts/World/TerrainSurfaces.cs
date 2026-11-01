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

            public LayerSurface(string name, float grip, float traction, float drag, float dust, Color dustColor)
            {
                this.name = name; this.grip = grip; this.traction = traction; this.drag = drag;
                this.dust = dust; this.dustColor = dustColor;
            }
        }

        public LayerSurface[] layers =
        {
            new LayerSurface("Sand", 0.84f, 0.8f, 0.55f, 1.0f, new Color(0.86f, 0.62f, 0.42f)),
            new LayerSurface("Gravel", 0.93f, 0.95f, 0.08f, 0.7f, new Color(0.64f, 0.54f, 0.45f)),
            new LayerSurface("CrackedSoil", 1.0f, 1.0f, 0.03f, 0.85f, new Color(0.80f, 0.66f, 0.52f)),
            new LayerSurface("RedRock", 1.12f, 1.0f, 0.0f, 0.25f, new Color(0.62f, 0.38f, 0.27f)),
        };
        public LayerSurface objects = new LayerSurface("Rock", 1.1f, 1.0f, 0f, 0.15f, new Color(0.6f, 0.4f, 0.3f));

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
                s.layers[i] = wgt;
                total += wgt;
            }
            if (total <= 1e-4f) return SurfaceInfo.Default;
            float inv = 1f / total;
            s.grip *= inv; s.traction *= inv; s.drag *= inv; s.dust *= inv;
            s.dustColor *= inv;
            s.dustColor.a = 1f;
            return s;
        }

        static SurfaceInfo ToInfo(in LayerSurface l) => new SurfaceInfo
        {
            grip = l.grip, traction = l.traction, drag = l.drag, dust = l.dust, dustColor = l.dustColor,
            layers = new Vector4(0f, 0f, 0f, 1f),   // props are rock
        };
    }
}
