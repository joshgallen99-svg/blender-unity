using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

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
        [Tooltip("Optional low-detail mesh used for chunks further than lodDistance.")]
        public Mesh lodMesh;
        public float lodDistance = 60f;
        [Tooltip("Optional far mesh (e.g. impostor cards) with its own materials, beyond lod2Distance.")]
        public Mesh lod2Mesh;
        public Material[] lod2Materials;
        public float lod2Distance = 250f;
        [Tooltip("Trunk collider (capsule) created at load for every instance; 0 = none.")]
        public float colliderRadius;
        public float colliderHeight = 4f;
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

        /// <summary>Instances drawn last frame (for the performance overlay and tests).</summary>
        public int DrawnInstances { get; private set; }

        void Awake()
        {
            Build();
            BuildColliders();
        }

        /// <summary>Static capsule colliders for trunks (trees), created at load from the instance data.</summary>
        void BuildColliders()
        {
            Transform root = null;
            foreach (var p in prototypes)
            {
                if (p.colliderRadius <= 0f) continue;
                if (root == null)
                {
                    root = new GameObject("Trunk Colliders").transform;
                    root.SetParent(transform, false);
                }
                for (int i = 0; i < p.Count; i++)
                {
                    int o = i * 7;
                    float s = p.data[o + 4];
                    var go = new GameObject(p.name);
                    go.transform.SetParent(root, false);
                    go.transform.position = new Vector3(p.data[o], p.data[o + 1], p.data[o + 2]);
                    var cap = go.AddComponent<CapsuleCollider>();
                    cap.radius = p.colliderRadius * s;
                    cap.height = p.colliderHeight * s;
                    cap.center = new Vector3(0f, cap.height * 0.5f, 0f);
                    go.isStatic = true;
                }
            }
        }

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
            // Small scenery only casts shadows inside the shadow range (no point rendering it into
            // cascades where its shadow would be culled or sub-pixel anyway).
            float shadowD = QualitySettings.renderPipeline is UniversalRenderPipelineAsset urp ? urp.shadowDistance : 0f;
            float shadowSq = shadowD * shadowD;
            float farSq = cam.farClipPlane * cam.farClipPlane;
            int drawn = 0;
            foreach (var c in _chunks)
            {
                float maxD = c.proto.drawDistance * detail;
                float d2 = c.bounds.SqrDistance(eye);
                if (d2 > maxD * maxD || d2 > farSq) continue;
                if (!GeometryUtility.TestPlanesAABB(_planes, c.bounds)) continue;
                float lodD = c.proto.lodDistance * detail;
                float lod2D = c.proto.lod2Distance * detail;
                var mesh = c.proto.lodMesh != null && d2 > lodD * lodD ? c.proto.lodMesh : c.proto.mesh;
                var mats = c.proto.materials;
                if (c.proto.lod2Mesh != null && c.proto.lod2Materials != null && d2 > lod2D * lod2D)
                {
                    mesh = c.proto.lod2Mesh;
                    mats = c.proto.lod2Materials;
                }
                bool shadows = c.proto.castShadows && d2 < shadowSq;
                drawn += c.matrices.Length;
                for (int s = 0; s < mesh.subMeshCount && s < mats.Length; s++)
                {
                    var rp = new RenderParams(mats[s])
                    {
                        worldBounds = c.bounds,
                        shadowCastingMode = shadows ? ShadowCastingMode.On : ShadowCastingMode.Off,
                        receiveShadows = true,
                        layer = gameObject.layer,
                    };
                    Graphics.RenderMeshInstanced(rp, mesh, s, c.matrices);
                }
            }
            DrawnInstances = drawn;
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
