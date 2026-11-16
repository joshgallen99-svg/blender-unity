using System.Collections;
using System.Collections.Generic;
using Offroad.World;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Offroad.Rendering
{
    /// <summary>
    /// Pre-compiles the shaders a region uses, so the game doesn't hitch the first time something new
    /// comes into view (a distant landmark, the water, a rock material). The GPU driver compiles a shader
    /// the first time it is drawn with a given setup, which on Metal can stall a frame noticeably.
    ///
    /// Right after a scene loads, while the title screen is up, a hidden camera draws every distinct
    /// material/mesh-layout combination in the scene (and the instanced vegetation and rocks) into a tiny
    /// texture, a batch per frame. It uses the scene's real lights, fog and shadows, so the compiled
    /// variants are the ones gameplay needs. Takes a handful of frames, then removes itself.
    /// </summary>
    public class ShaderWarmup : MonoBehaviour
    {
        const int Layer = 30;          // unused layer, seen only by the warm-up camera
        const int PerFrame = 24;

        public static bool Running { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Install()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
            Begin();
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode) => Begin();

        static void Begin()
        {
            if (Application.isBatchMode) return;     // tests and CI: nothing to compile for
            if (FindAnyObjectByType<ShaderWarmup>() != null) return;   // already warming this scene
            var go = new GameObject("Shader Warm-up") { hideFlags = HideFlags.HideInHierarchy };
            go.AddComponent<ShaderWarmup>();
        }

        struct Item
        {
            public Mesh mesh;
            public Material material;
            public int submesh;
            public bool instanced;
        }

        IEnumerator Start()
        {
            Running = true;
            yield return null;                         // let the scene's own Start()s apply settings first

            var items = Collect();
            var rt = new RenderTexture(64, 64, 24, RenderTextureFormat.DefaultHDR) { name = "Shader Warm-up" };
            var camGo = new GameObject("Warm-up Camera") { hideFlags = HideFlags.HideAndDontSave };
            camGo.transform.SetPositionAndRotation(new Vector3(0f, -3000f, 0f), Quaternion.identity);
            var cam = camGo.AddComponent<Camera>();
            cam.targetTexture = rt;
            cam.cullingMask = 1 << Layer;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Color.black;
            cam.depth = -100;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 50f;
            cam.fieldOfView = 70f;

            var temp = new List<GameObject>(PerFrame);
            var oneMatrix = new Matrix4x4[2];
            for (int start = 0; start < items.Count; start += PerFrame)
            {
                int end = Mathf.Min(start + PerFrame, items.Count);
                for (int k = start; k < end; k++)
                {
                    var it = items[k];
                    // Lay the batch out on a grid in front of the camera, each mesh scaled to about 1 m.
                    int slot = k - start;
                    var local = new Vector3((slot % 6 - 2.5f) * 1.1f, (slot / 6 - 1.5f) * 1.1f, 4f);
                    var pos = camGo.transform.TransformPoint(local);
                    float size = Mathf.Max(it.mesh.bounds.size.magnitude, 0.01f);
                    var trs = Matrix4x4.TRS(pos - it.mesh.bounds.center / size, Quaternion.identity, Vector3.one / size);
                    if (it.instanced)
                    {
                        oneMatrix[0] = trs;
                        oneMatrix[1] = trs;
                        var rp = new RenderParams(it.material)
                        {
                            camera = cam,
                            layer = Layer,
                            worldBounds = new Bounds(pos, Vector3.one * 2f),
                            shadowCastingMode = ShadowCastingMode.On,
                            receiveShadows = true,
                        };
                        Graphics.RenderMeshInstanced(rp, it.mesh, it.submesh, oneMatrix);
                        continue;
                    }
                    var go = new GameObject("warm") { layer = Layer, hideFlags = HideFlags.HideAndDontSave };
                    go.transform.SetPositionAndRotation(trs.GetPosition(), Quaternion.identity);
                    go.transform.localScale = Vector3.one / size;
                    go.AddComponent<MeshFilter>().sharedMesh = it.mesh;
                    var mr = go.AddComponent<MeshRenderer>();
                    var mats = new Material[it.mesh.subMeshCount];
                    for (int s = 0; s < mats.Length; s++) mats[s] = it.material;
                    mr.sharedMaterials = mats;
                    temp.Add(go);
                }
                yield return null;                     // the warm-up camera draws this batch
                foreach (var go in temp) Destroy(go);
                temp.Clear();
            }

            Destroy(camGo);
            rt.Release();
            Destroy(rt);
            Running = false;
            Destroy(gameObject);
        }

        /// <summary>Distinct material + vertex layout combinations in the loaded scene.</summary>
        static List<Item> Collect()
        {
            var items = new List<Item>();
            var seen = new HashSet<string>();
            void Add(Mesh mesh, Material mat, int submesh, bool instanced)
            {
                if (mesh == null || mat == null || mat.shader == null) return;
                if (mesh.vertexCount == 0) return;
                string key = $"{mat.GetInstanceID()}|{Layout(mesh)}|{instanced}";
                if (!seen.Add(key)) return;
                items.Add(new Item { mesh = mesh, material = mat, submesh = Mathf.Clamp(submesh, 0, mesh.subMeshCount - 1), instanced = instanced });
            }

            foreach (var mr in FindObjectsByType<MeshRenderer>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (mr.gameObject.layer == Layer) continue;
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null) continue;
                var mats = mr.sharedMaterials;
                for (int s = 0; s < mats.Length; s++) Add(mf.sharedMesh, mats[s], s, false);
            }
            foreach (var scatter in FindObjectsByType<InstancedScatter>(FindObjectsSortMode.None))
                foreach (var p in scatter.prototypes)
                {
                    if (p.materials != null)
                        for (int s = 0; s < p.materials.Length; s++)
                        {
                            Add(p.mesh, p.materials[s], s, true);
                            Add(p.lodMesh, p.materials[s], s, true);
                        }
                    if (p.lod2Materials != null)
                        for (int s = 0; s < p.lod2Materials.Length; s++) Add(p.lod2Mesh, p.lod2Materials[s], s, true);
                }
            return items;
        }

        static readonly Dictionary<Mesh, string> LayoutCache = new Dictionary<Mesh, string>();

        static string Layout(Mesh mesh)
        {
            if (LayoutCache.TryGetValue(mesh, out var s)) return s;
            var sb = new System.Text.StringBuilder();
            foreach (var a in mesh.GetVertexAttributes()) sb.Append((int)a.attribute).Append(':').Append(a.dimension).Append(',');
            s = sb.ToString();
            LayoutCache[mesh] = s;
            return s;
        }
    }
}
