using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Offroad.World
{
    /// <summary>Compact list of instances for one mesh (grass, shrubs, small rocks), built in the editor.</summary>
    [Serializable]
    public class InstancePrototype
    {
        public string name;
        public Mesh mesh;
        public Material[] materials;
        public bool castShadows;
        [Tooltip("Draw distance in metres at Scenery Detail 1.0.")]
        public float drawDistance = 120f;
        // Per instance: position (3), yaw degrees, scale, up-vector x, up-vector z  = 7 floats.
        public float[] data = Array.Empty<float>();
        public int Count => data.Length / 7;
    }

    /// <summary>
    /// Draws thousands of small scenery pieces with GPU instancing instead of GameObjects.
    /// Instances are bucketed into square chunks; each frame only chunks within draw distance and
    /// inside the camera frustum are submitted (up to 1023 instances per call).
    /// </summary>
    public class InstancedScatter : MonoBehaviour
    {
        public float chunkSize = 64f;
        public List<InstancePrototype> prototypes = new List<InstancePrototype>();

        class Chunk
        {
            public InstancePrototype proto;
            public Bounds bounds;
            public Matrix4x4[] matrices;
        }

        readonly List<Chunk> _chunks = new List<Chunk>();
        readonly Plane[] _planes = new Plane[6];

        void Awake() => Build();

        public void Build()
        {
            _chunks.Clear();
            foreach (var p in prototypes)
            {
                if (p.mesh == null || p.materials == null || p.materials.Length == 0) continue;
                var buckets = new Dictionary<Vector2Int, List<Matrix4x4>>();
                for (int i = 0; i < p.Count; i++)
                {
                    int o = i * 7;
                    var pos = new Vector3(p.data[o], p.data[o + 1], p.data[o + 2]);
                    float ux = p.data[o + 5], uz = p.data[o + 6];
                    var up = new Vector3(ux, Mathf.Sqrt(Mathf.Max(0f, 1f - ux * ux - uz * uz)), uz);
                    var rot = Quaternion.FromToRotation(Vector3.up, up) * Quaternion.Euler(0f, p.data[o + 3], 0f);
                    var m = Matrix4x4.TRS(pos, rot, Vector3.one * p.data[o + 4]);
                    var key = new Vector2Int(Mathf.FloorToInt(pos.x / chunkSize), Mathf.FloorToInt(pos.z / chunkSize));
                    if (!buckets.TryGetValue(key, out var list)) buckets[key] = list = new List<Matrix4x4>();
                    list.Add(m);
                }
                var meshBounds = p.mesh.bounds;
                float pad = meshBounds.extents.magnitude * 2f;
                foreach (var kv in buckets)
                {
                    for (int start = 0; start < kv.Value.Count; start += 1023)
                    {
                        int n = Mathf.Min(1023, kv.Value.Count - start);
                        var mats = kv.Value.GetRange(start, n).ToArray();
                        var b = new Bounds(mats[0].GetColumn(3), Vector3.zero);
                        foreach (var m in mats) b.Encapsulate((Vector3)m.GetColumn(3));
                        b.Expand(pad);
                        _chunks.Add(new Chunk { proto = p, bounds = b, matrices = mats });
                    }
                }
            }
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (!cam || _chunks.Count == 0) return;
            GeometryUtility.CalculateFrustumPlanes(cam, _planes);
            Vector3 eye = cam.transform.position;
            float detail = Mathf.Max(QualitySettings.lodBias, 0.3f);
            foreach (var c in _chunks)
            {
                float maxD = c.proto.drawDistance * detail;
                if (c.bounds.SqrDistance(eye) > maxD * maxD) continue;
                if (!GeometryUtility.TestPlanesAABB(_planes, c.bounds)) continue;
                var mesh = c.proto.mesh;
                for (int s = 0; s < mesh.subMeshCount && s < c.proto.materials.Length; s++)
                {
                    var rp = new RenderParams(c.proto.materials[s])
                    {
                        worldBounds = c.bounds,
                        shadowCastingMode = c.proto.castShadows ? ShadowCastingMode.On : ShadowCastingMode.Off,
                        receiveShadows = true,
                        layer = gameObject.layer,
                    };
                    Graphics.RenderMeshInstanced(rp, mesh, s, c.matrices);
                }
            }
        }

        public int TotalInstances
        {
            get
            {
                int n = 0;
                foreach (var p in prototypes) n += p.Count;
                return n;
            }
        }
    }
}
