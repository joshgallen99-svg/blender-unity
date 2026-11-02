using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Offroad.World
{
    /// <summary>
    /// Rings of distant scenery around the region: red mesas a little beyond the cliffs and blue
    /// mountain ranges on the horizon. Meshes are generated procedurally and drawn every frame with
    /// bounds around the camera, so they are never culled by the view-distance setting.
    /// </summary>
    public class Backdrop : MonoBehaviour
    {
        public Vector3 centre = new Vector3(512f, 0f, 512f);
        public Material farMaterial;
        public Material midMaterial;
        public int seed = 7;
        [Tooltip("Scales the far ranges' height (alpine regions need taller peaks behind their own).")]
        public float heightScale = 1f;
        public float midHeightScale = 1f;
        [Tooltip("Mid-distance ring as jagged peaks instead of flat-topped mesas.")]
        public bool midJagged;

        readonly List<(Mesh mesh, Material mat)> _layers = new List<(Mesh, Material)>();

        void Awake()
        {
            _layers.Clear();
            if (farMaterial) _layers.Add((Range(2600f, 380f * heightScale, 0.9f, seed, jagged: true), farMaterial));
            if (farMaterial) _layers.Add((Range(3400f, 520f * heightScale, 0.75f, seed + 3, jagged: true), farMaterial));
            if (midMaterial) _layers.Add((Range(1400f, 150f * midHeightScale, 1.0f, seed + 7, jagged: midJagged), midMaterial));
        }

        /// <summary>A closed ring of peaks (jagged) or flat-topped mesas, facing inward.</summary>
        Mesh Range(float radius, float height, float tint, int s, bool jagged)
        {
            const int segments = 360;
            var verts = new List<Vector3>();
            var cols = new List<Color>();
            var tris = new List<int>();
            float o1 = s * 13.1f, o2 = s * 7.7f;
            for (int i = 0; i <= segments; i++)
            {
                float a = i / (float)segments * Mathf.PI * 2f;
                float u = i / (float)segments * 40f;
                float h;
                if (jagged)
                {
                    float ridge = 1f - Mathf.Abs(Mathf.PerlinNoise(u * 0.35f + o1, o2) * 2f - 1f);
                    h = height * (0.35f + 0.65f * Mathf.PerlinNoise(u * 0.12f + o2, o1)) * (0.6f + 0.4f * ridge);
                    h += height * 0.12f * Mathf.PerlinNoise(u * 1.3f + o1, 3f);
                }
                else
                {
                    // Mesas: plateaus with steep sides and gaps.
                    float m = Mathf.PerlinNoise(u * 0.18f + o1, o2);
                    h = height * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.42f, 0.5f, m)) * (0.75f + 0.25f * Mathf.PerlinNoise(u * 0.6f, o1));
                    h += height * 0.18f * Mathf.PerlinNoise(u * 0.5f + o2, 5f);
                }
                float r = radius * (1f + 0.06f * (Mathf.PerlinNoise(u * 0.2f + 9f, o1) - 0.5f));
                var dir = new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a));
                var b = centre + dir * (r + height * 0.6f) + Vector3.down * 60f;   // wide base
                var mid = centre + dir * (r + height * 0.25f) + Vector3.up * (h * 0.55f);
                var top = centre + dir * r + Vector3.up * h;
                verts.Add(b); verts.Add(mid); verts.Add(top);
                var c = new Color(tint, tint, tint, 1f);
                cols.Add(c); cols.Add(c); cols.Add(c);
                if (i == 0) continue;
                int p = (i - 1) * 3, q = i * 3;
                for (int k = 0; k < 2; k++)
                {
                    tris.Add(p + k); tris.Add(q + k); tris.Add(q + k + 1);
                    tris.Add(p + k); tris.Add(q + k + 1); tris.Add(p + k + 1);
                }
            }
            var mesh = new Mesh { name = "Backdrop" };
            mesh.SetVertices(verts);
            mesh.SetColors(cols);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            // Normals point inward (toward the player) for lighting.
            var n = mesh.normals;
            for (int i = 0; i < n.Length; i++)
            {
                var toCentre = (centre - verts[i]);
                toCentre.y = 0f;
                if (Vector3.Dot(n[i], toCentre) < 0f) n[i] = -n[i];
            }
            mesh.normals = n;
            mesh.bounds = new Bounds(centre, Vector3.one * 10000f);
            return mesh;
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (!cam) return;
            var bounds = new Bounds(cam.transform.position, Vector3.one * 100f);
            foreach (var (mesh, mat) in _layers)
            {
                var rp = new RenderParams(mat)
                {
                    worldBounds = bounds,
                    shadowCastingMode = ShadowCastingMode.Off,
                    receiveShadows = false,
                };
                Graphics.RenderMesh(rp, mesh, 0, Matrix4x4.identity);
            }
        }
    }
}
