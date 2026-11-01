using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Offroad.CameraRig;
using Offroad.UI;
using Offroad.Vehicles;
using Offroad.World;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

namespace Offroad.EditorTools
{
    /// <summary>
    /// Builds the prototype scene entirely from generated data:
    /// terrain (Python), models (Blender), materials/prefabs/lighting (here).
    /// Menu: Offroad > Rebuild Prototype Scene. CI runs it before every build.
    /// </summary>
    public static class PrototypeSceneBuilder
    {
        public const string ScenePath = "Assets/Scenes/Prototype.unity";
        const string SourceDir = "Assets/Terrain/Source~";
        const string GeneratedDir = "Assets/Terrain/Generated";
        const string PrefabDir = "Assets/Prefabs";
        const string VehicleModel = "Assets/Models/Vehicles/Fleet.fbx";

        /// <summary>The region being built (set by Build for each region in turn).</summary>
        static RegionProfile P = RegionProfiles.Desert;
        static string Region => P.id;

        [Serializable] public class SpawnInfo { public float x, z, yaw; }
        [Serializable] public class RegionInfo
        {
            public float size, height;
            public int resolution, splatResolution;
            public string[] layers;
            public SpawnInfo spawn;
            public LandmarkInfo[] landmarks;
            public PieceInfo[] markers;
            public FormationInfo[] formations;
            public float[] roadX, roadZ;
            public TrackInfo[] tracks;
            public RiverInfo river;
            public LakeInfo lake;
            public FallsInfo falls;
        }
        [Serializable] public class RiverInfo { public float[] x, z, halfWidth, level; }
        [Serializable] public class LakeInfo { public float x, z, rx, rz, yaw, level; }
        [Serializable] public class FallsInfo { public float x, z, top, bottom; }
        [Serializable] public class FormationInfo { public string model; public float x, z, yaw, scale, sink; }
        [Serializable] public class TrackInfo { public string name; public float width; public float[] x, z, washboard, fade; }
        [Serializable] public class PieceInfo { public string model; public float x, z, yaw, sink, align, absY; }
        [Serializable] public class LandmarkInfo
        {
            public string id, name;
            public float x, z, radius, discoverRadius;
            public PieceInfo[] pieces;
        }
        [Serializable] public class PropEntry { public string kind; public int variant; public float x, z, yaw, scale, sink; }
        [Serializable] public class ScatterFile { public PropEntry[] props; }

        [MenuItem("Offroad/Rebuild Prototype Scene")]
        public static void BuildFromMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Build();
            EditorSceneManager.OpenScene(ScenePath);
        }

        public static void Build()
        {
            ProjectSetup.Run();
            MaterialLibrary.EnsureAll();
            AssetDatabase.ImportAsset(VehicleModel, ImportAssetOptions.ForceUpdate);
            var scenes = new List<EditorBuildSettingsScene>();
            foreach (var profile in RegionProfiles.All)
            {
                if (!File.Exists($"{SourceDir}/{profile.id}_info.json")) { Debug.LogWarning($"[Offroad] No data for region {profile.id}"); continue; }
                BuildRegion(profile);
                scenes.Add(new EditorBuildSettingsScene(profile.scenePath, true));
            }
            EditorBuildSettings.scenes = scenes.ToArray();
            AssetDatabase.SaveAssets();
        }

        static void BuildRegion(RegionProfile profile)
        {
            P = profile;
            AssetDatabase.ImportAsset(P.propsModel, ImportAssetOptions.ForceUpdate);
            foreach (var m in P.landmarkModels) AssetDatabase.ImportAsset(m, ImportAssetOptions.ForceUpdate);
            AssetDatabase.ImportAsset(P.formationsModel, ImportAssetOptions.ForceUpdate);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var info = ReadJson<RegionInfo>($"{SourceDir}/{Region}_info.json");

            CreateLighting();
            var terrain = CreateTerrain(info);
            PlaceFormations(terrain, info);
            CreateTracks(terrain, info);
            if (P.water) CreateWater(terrain, info);
            PlaceProps(terrain, info);
            PlaceLandmarks(terrain, info);
            var vehicle = CreateVehicle(terrain, info);
            var cam = CreateCamera(vehicle);
            CreateSystems(vehicle, cam);

            Directory.CreateDirectory(Path.GetDirectoryName(P.scenePath));
            EditorSceneManager.SaveScene(scene, P.scenePath);
            Debug.Log($"[Offroad] Built {P.scenePath}: terrain {info.size}m, camera {cam.name}");
        }


        // ------------------------------------------------------------------ lighting

        static Light CreateLighting()
        {
            var go = new GameObject("Sun");
            var sun = go.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = P.sunColor;
            sun.intensity = P.sunIntensity;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.9f;
            go.transform.rotation = Quaternion.Euler(P.sunEuler);

            RenderSettings.skybox = P == RegionProfiles.Desert ? MaterialLibrary.Skybox()
                : MaterialLibrary.Skybox($"Skybox_{P.title}", P.skyTint, P.atmosphereThickness, P.skyExposure, P.ambientGround);
            RenderSettings.sun = sun;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = P.ambientSky;
            RenderSettings.ambientEquatorColor = P.ambientEquator;
            RenderSettings.ambientGroundColor = P.ambientGround;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = P.fogColor;           // blue aerial haze
            RenderSettings.fogStartDistance = 200f;
            RenderSettings.fogEndDistance = 900f;

            var backdrop = new GameObject("Distant Ranges").AddComponent<Backdrop>();
            string prefix = P == RegionProfiles.Desert ? "" : P.title;
            backdrop.farMaterial = MaterialLibrary.Backdrop($"{prefix}BackdropRanges", P.farLit, P.farShadow, P.farHaze,
                P.farHazeAmount, P.farHazeHeight, P.farSnowLine > 0 ? 300f : 0f);
            backdrop.midMaterial = MaterialLibrary.Backdrop($"{prefix}BackdropMesas", P.midLit, P.midShadow, P.midHaze,
                P.midHazeAmount, P.midHazeHeight);
            var clouds = backdrop.gameObject.AddComponent<SkyClouds>();
            clouds.material = MaterialLibrary.Clouds($"Clouds{P.title}", P.cloudCoverage, P.fogColor);
            return sun;
        }

        // ------------------------------------------------------------------ terrain

        static Terrain CreateTerrain(RegionInfo info)
        {
            Directory.CreateDirectory(GeneratedDir);
            int res = info.resolution;
            var bytes = File.ReadAllBytes($"{SourceDir}/{Region}_height.r16");
            if (bytes.Length != res * res * 2) throw new Exception($"Heightmap size mismatch: {bytes.Length} bytes");
            var heights = new float[res, res];
            for (int z = 0; z < res; z++)
            for (int x = 0; x < res; x++)
            {
                int i = (z * res + x) * 2;
                heights[z, x] = (bytes[i] | (bytes[i + 1] << 8)) / 65535f;
            }

            var td = new TerrainData { name = $"{P.title}Terrain" };
            td.heightmapResolution = res;
            td.size = new Vector3(info.size, info.height, info.size);
            td.SetHeights(0, 0, heights);
            td.baseMapResolution = 1024;
            td.alphamapResolution = info.splatResolution;
            td.terrainLayers = info.layers.Select(CreateLayer).ToArray();

            var splatTex = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
            splatTex.LoadImage(File.ReadAllBytes($"{SourceDir}/{Region}_splat.png"));
            int sr = info.splatResolution;
            if (splatTex.width != sr) throw new Exception($"Splat size {splatTex.width} != {sr}");
            var px = splatTex.GetPixels32();
            var alpha = new float[sr, sr, 4];
            for (int y = 0; y < sr; y++)
            for (int x = 0; x < sr; x++)
            {
                var c = px[y * sr + x];
                float sum = Mathf.Max(1, c.r + c.g + c.b + c.a);
                alpha[y, x, 0] = c.r / sum;
                alpha[y, x, 1] = c.g / sum;
                alpha[y, x, 2] = c.b / sum;
                alpha[y, x, 3] = c.a / sum;
            }
            Object.DestroyImmediate(splatTex);
            td.SetAlphamaps(0, 0, alpha);

            var tdPath = $"{GeneratedDir}/{P.title}Terrain.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = "Terrain";
            var t = go.GetComponent<Terrain>();
            var mask = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Masks/{Region}_mask.png");
            if (mask == null) throw new Exception("Terrain mask missing");
            t.materialTemplate = P.terrainMaterial(mask);
            t.drawInstanced = false;            // our terrain shaders read regular terrain vertices
            t.heightmapPixelError = 4f;
            t.basemapDistance = 20000f;         // never switch to Unity's basemap shader
            t.drawTreesAndFoliage = false;
            t.shadowCastingMode = ShadowCastingMode.On;
            var surfaces = go.AddComponent<TerrainSurfaces>();
            if (P.surfaces != null) surfaces.layers = P.surfaces;
            surfaces.greenIsWater = P.hazardGreenIsWater;
            var hazard = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Masks/{Region}_hazard.png");
            surfaces.hazardMap = hazard;      // mud, quicksand, washboard, water (read on the CPU too)

            // Heightmap as a texture for the rock shader's sand skirt.
            var htex = new Texture2D(res, res, TextureFormat.RHalf, false, true)
            {
                name = $"{P.title}Height", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear,
            };
            var hpx = new Color[res * res];
            for (int z = 0; z < res; z++)
            for (int x = 0; x < res; x++)
                hpx[z * res + x] = new Color(heights[z, x], 0f, 0f, 1f);
            htex.SetPixels(hpx);
            htex.Apply(false, false);
            var hPath = $"{GeneratedDir}/{P.title}Height.asset";
            AssetDatabase.DeleteAsset(hPath);
            AssetDatabase.CreateAsset(htex, hPath);
            var globals = go.AddComponent<TerrainGlobals>();
            globals.terrain = t;
            globals.heightTexture = htex;
            globals.hazardTexture = hazard;
            globals.Publish();
            return t;
        }

        static TerrainLayer CreateLayer(string name)
        {
            // Layers only carry the physics surface weights; our terrain shaders do the rendering.
            string tex = P.layerTexture(name);
            float tile = 8f;
            var layer = new TerrainLayer
            {
                diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{tex}_albedo.png"),
                normalMapTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{tex}_normal.png"),
                tileSize = new Vector2(tile, tile),
                normalScale = 1f,
                metallic = 0f,
                smoothness = 0.05f,
            };
            if (layer.diffuseTexture == null) Debug.LogWarning($"[Offroad] Missing terrain texture for {name}");
            var path = $"{GeneratedDir}/Layer_{name}.terrainlayer";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(layer, path);
            return layer;
        }

        // ------------------------------------------------------------------ props

        static PropKind KindOf(string kind) =>
            P.kinds.TryGetValue(kind, out var k) ? k : new PropKind { cullHeight = 0.01f, shadows = true, collider = 2, alignToGround = 0.5f };

        static void PlaceProps(Terrain terrain, RegionInfo info)
        {
            var scatter = ReadJson<ScatterFile>($"{SourceDir}/{Region}_scatter.json");
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(P.propsModel);
            if (model == null) throw new Exception("Props model missing: " + P.propsModel);
            var prefabs = new Dictionary<string, GameObject>();
            var root = new GameObject("Props").transform;
            var groups = new Dictionary<string, Transform>();
            var td = terrain.terrainData;

            // Instanced scenery: grass, shrubs, small rocks and yuccas.
            var scatterGo = new GameObject("Instanced Scenery");
            var inst = scatterGo.AddComponent<InstancedScatter>();
            var data = new Dictionary<string, List<float>>();
            int gameObjects = 0;

            foreach (var p in scatter.props)
            {
                string key = $"{p.kind}_{p.variant}";
                var pos = new Vector3(p.x, 0f, p.z);
                pos.y = terrain.SampleHeight(pos) + terrain.transform.position.y - p.sink * p.scale;
                Vector3 n = td.GetInterpolatedNormal(p.x / td.size.x, p.z / td.size.z);

                if (P.instanced.TryGetValue(p.kind, out var spec))
                {
                    var up = Vector3.Slerp(Vector3.up, n, spec.align).normalized;
                    if (!data.TryGetValue(key, out var list)) data[key] = list = new List<float>();
                    list.AddRange(new[] { pos.x, pos.y, pos.z, p.yaw, p.scale, up.x, up.z });
                    if (spec.collider)
                    {
                        // Collider only: the mesh itself is drawn by the instancer.
                        var src = model.transform.Find(key + "_LOD1");
                        if (src == null) src = model.transform.Find(key);
                        if (src == null) continue;
                        if (!groups.TryGetValue(p.kind, out var cgroup))
                        {
                            cgroup = new GameObject(p.kind + " Colliders").transform;
                            cgroup.SetParent(root, false);
                            groups[p.kind] = cgroup;
                        }
                        var col = new GameObject(key);
                        col.transform.SetParent(cgroup, false);
                        col.transform.SetPositionAndRotation(pos, Quaternion.FromToRotation(Vector3.up, up) * Quaternion.Euler(0f, p.yaw, 0f));
                        col.transform.localScale = Vector3.one * p.scale;
                        col.AddComponent<MeshCollider>().sharedMesh = src.GetComponent<MeshFilter>().sharedMesh;
                        col.isStatic = true;
                        gameObjects++;
                    }
                    continue;
                }

                if (!prefabs.TryGetValue(key, out var prefab))
                {
                    prefab = CreatePropPrefab(model, key, KindOf(p.kind));
                    prefabs[key] = prefab;
                }
                if (prefab == null) continue;
                if (!groups.TryGetValue(p.kind, out var group))
                {
                    group = new GameObject(p.kind).transform;
                    group.SetParent(root, false);
                    groups[p.kind] = group;
                }
                var kind = KindOf(p.kind);
                Quaternion tilt = Quaternion.FromToRotation(Vector3.up, Vector3.Slerp(Vector3.up, n, kind.alignToGround));
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, group);
                go.transform.SetPositionAndRotation(pos, tilt * Quaternion.Euler(0f, p.yaw, 0f));
                go.transform.localScale = Vector3.one * p.scale;
                gameObjects++;
            }

            foreach (var kv in data)
            {
                var src = model.transform.Find(kv.Key);
                if (src == null) { Debug.LogWarning($"[Offroad] Prop mesh {kv.Key} not found"); continue; }
                var spec = P.instanced[kv.Key.Split('_')[0]];
                var lodSrc = spec.lod > 0f ? model.transform.Find(kv.Key + "_LOD1") : null;
                var lod2Src = spec.lod2 > 0f ? model.transform.Find(kv.Key + "_LOD2") : null;
                inst.prototypes.Add(new InstancePrototype
                {
                    name = kv.Key,
                    mesh = src.GetComponent<MeshFilter>().sharedMesh,
                    lodMesh = lodSrc != null ? lodSrc.GetComponent<MeshFilter>().sharedMesh : null,
                    lodDistance = spec.lod,
                    lod2Mesh = lod2Src != null ? lod2Src.GetComponent<MeshFilter>().sharedMesh : null,
                    lod2Materials = lod2Src != null ? MaterialLibrary.Remap(lod2Src.GetComponent<MeshRenderer>().sharedMaterials) : null,
                    lod2Distance = spec.lod2,
                    colliderRadius = spec.trunkRadius,
                    colliderHeight = spec.trunkHeight,
                    materials = MaterialLibrary.Remap(src.GetComponent<MeshRenderer>().sharedMaterials),
                    castShadows = spec.shadows,
                    drawDistance = spec.distance,
                    data = kv.Value.ToArray(),
                });
            }
            Debug.Log($"[Offroad] Placed {gameObjects} prop objects and {inst.TotalInstances} instanced pieces");
        }

        // ------------------------------------------------------------------ formations

        static void PlaceFormations(Terrain terrain, RegionInfo info)
        {
            if (info.formations == null) return;
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(P.formationsModel);
            if (model == null) throw new Exception("Formations model missing: " + P.formationsModel);
            var prefabs = new Dictionary<string, GameObject>();
            var root = new GameObject("Formations").transform;
            foreach (var f in info.formations)
            {
                if (!prefabs.TryGetValue(f.model, out var prefab))
                {
                    prefab = CreateFormationPrefab(model, f.model);
                    prefabs[f.model] = prefab;
                }
                if (prefab == null) continue;
                var pos = new Vector3(f.x, 0f, f.z);
                pos.y = terrain.SampleHeight(pos) + terrain.transform.position.y - f.sink * f.scale;
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root);
                go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, f.yaw, 0f));
                go.transform.localScale = Vector3.one * f.scale;
            }
            Debug.Log($"[Offroad] Placed {info.formations.Length} rock formations");
        }

        static GameObject CreateFormationPrefab(GameObject model, string name)
        {
            var lod0 = model.transform.Find(name);
            var lod1 = model.transform.Find(name + "_LOD1");
            if (lod0 == null) { Debug.LogWarning($"[Offroad] Formation {name} not found"); return null; }
            var go = new GameObject(name);
            var r0 = AddChildMesh(go, lod0, "LOD0", true);
            var renderers = new List<LOD> { new LOD(0.18f, new Renderer[] { r0 }) };
            if (lod1 != null)
            {
                var r1 = AddChildMesh(go, lod1, "LOD1", true);
                renderers.Add(new LOD(0.0008f, new Renderer[] { r1 }));
                go.AddComponent<MeshCollider>().sharedMesh = lod1.GetComponent<MeshFilter>().sharedMesh;
            }
            else go.AddComponent<MeshCollider>().sharedMesh = lod0.GetComponent<MeshFilter>().sharedMesh;
            var lod = go.AddComponent<LODGroup>();
            lod.SetLODs(renderers.ToArray());
            lod.fadeMode = LODFadeMode.None;
            Directory.CreateDirectory($"{PrefabDir}/Formations");
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, $"{PrefabDir}/Formations/{name}.prefab");
            Object.DestroyImmediate(go);
            return prefab;
        }

        static Renderer AddChildMesh(GameObject parent, Transform src, string name, bool shadows)
        {
            var child = new GameObject(name);
            child.transform.SetParent(parent.transform, false);
            child.AddComponent<MeshFilter>().sharedMesh = src.GetComponent<MeshFilter>().sharedMesh;
            var mr = child.AddComponent<MeshRenderer>();
            mr.sharedMaterials = MaterialLibrary.Remap(src.GetComponent<MeshRenderer>().sharedMaterials);
            mr.shadowCastingMode = shadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
            return mr;
        }

        // ------------------------------------------------------------------ road

        /// <summary>
        /// Dirt tracks: ribbons draped on the terrain and drawn with the DirtTrack decal shader (wheel
        /// ruts, grassy crown, washboard, soft edges). Per vertex: uv0 = (metres from centre line,
        /// metres along), uv1.x = half width, colour = (washboard, wear, fade), tangent = across.
        /// Each track is split into chunks so off-screen parts are culled.
        /// </summary>
        static void CreateTracks(Terrain terrain, RegionInfo info)
        {
            if (info.tracks == null) return;
            var root = new GameObject("Tracks").transform;
            var material = P.trackMaterial();
            var td = terrain.terrainData;
            const int Across = 9;
            const int ChunkPoints = 120;
            foreach (var t in info.tracks)
            {
                int n = t.x.Length;
                if (n < 2) continue;
                float half = t.width * 0.5f;
                float reach = half * 1.35f;              // ribbon is wider than the track: soft edges
                float wear = t.name == "main" ? 1f : 0.65f;
                var dist = new float[n];
                for (int i = 1; i < n; i++) dist[i] = dist[i - 1] + Vector2.Distance(new Vector2(t.x[i], t.z[i]), new Vector2(t.x[i - 1], t.z[i - 1]));

                for (int start = 0, chunk = 0; start < n - 1; start += ChunkPoints, chunk++)
                {
                    int end = Mathf.Min(start + ChunkPoints, n - 1);
                    var verts = new List<Vector3>();
                    var normals = new List<Vector3>();
                    var tangents = new List<Vector4>();
                    var uv0 = new List<Vector2>();
                    var uv1 = new List<Vector2>();
                    var cols = new List<Color>();
                    var tris = new List<int>();
                    for (int i = start; i <= end; i++)
                    {
                        var p = new Vector3(t.x[i], 0f, t.z[i]);
                        int ip = Mathf.Max(i - 1, 0), inx = Mathf.Min(i + 1, n - 1);
                        var dir = new Vector3(t.x[inx] - t.x[ip], 0f, t.z[inx] - t.z[ip]).normalized;
                        var right = new Vector3(dir.z, 0f, -dir.x);
                        float wash = t.washboard != null && t.washboard.Length == n ? t.washboard[i] : 0f;
                        float fade = t.fade != null && t.fade.Length == n ? t.fade[i] : 1f;
                        for (int s = 0; s < Across; s++)
                        {
                            float lat = Mathf.Lerp(-reach, reach, s / (Across - 1f));
                            var q = p + right * lat;
                            var nrm = td.GetInterpolatedNormal(q.x / td.size.x, q.z / td.size.z);
                            q.y = terrain.SampleHeight(q) + terrain.transform.position.y + 0.06f;
                            verts.Add(q);
                            normals.Add(nrm);
                            var across = Vector3.ProjectOnPlane(right, nrm).normalized;
                            tangents.Add(new Vector4(across.x, across.y, across.z, 1f));
                            uv0.Add(new Vector2(lat, dist[i]));
                            uv1.Add(new Vector2(half, 0f));
                            cols.Add(new Color(wash, wear, fade, 1f));
                        }
                        if (i == start) continue;
                        int a = (i - start - 1) * Across, b = (i - start) * Across;
                        for (int s = 0; s < Across - 1; s++)
                        {
                            tris.Add(a + s); tris.Add(b + s); tris.Add(b + s + 1);
                            tris.Add(a + s); tris.Add(b + s + 1); tris.Add(a + s + 1);
                        }
                    }
                    var mesh = new Mesh { name = $"Track_{Region}_{t.name}_{chunk}" };
                    mesh.SetVertices(verts);
                    mesh.SetNormals(normals);
                    mesh.SetTangents(tangents);
                    mesh.SetUVs(0, uv0);
                    mesh.SetUVs(1, uv1);
                    mesh.SetColors(cols);
                    mesh.SetTriangles(tris, 0);
                    mesh.RecalculateBounds();
                    var path = $"{GeneratedDir}/Tracks/{mesh.name}.asset";
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    AssetDatabase.DeleteAsset(path);
                    AssetDatabase.CreateAsset(mesh, path);
                    var go = new GameObject(mesh.name);
                    go.transform.SetParent(root, false);
                    go.AddComponent<MeshFilter>().sharedMesh = mesh;
                    var mr = go.AddComponent<MeshRenderer>();
                    mr.sharedMaterial = material;
                    mr.shadowCastingMode = ShadowCastingMode.Off;
                    go.isStatic = true;
                }
            }
        }

        // ------------------------------------------------------------------ water

        /// <summary>
        /// River ribbon (flowing downstream along uv.y), the plunge lake and the waterfall sheet, all with
        /// the Water shader; mist at the foot of the falls. Vertex colour: r turbulence, g extra foam,
        /// b waterfall, a flow-speed multiplier.
        /// </summary>
        static void CreateWater(Terrain terrain, RegionInfo info)
        {
            var root = new GameObject("Water").transform;
            var mat = MaterialLibrary.Water();
            float ty = terrain.transform.position.y;
            Vector3 fallsPos = info.falls != null ? new Vector3(info.falls.x, 0f, info.falls.z) : Vector3.zero;

            // --- River, in chunks for culling.
            var r = info.river;
            if (r != null && r.x != null && r.x.Length > 2)
            {
                int n = r.x.Length;
                const int Across = 7;
                var dist = new float[n];
                for (int i = 1; i < n; i++) dist[i] = dist[i - 1] + Vector2.Distance(new Vector2(r.x[i], r.z[i]), new Vector2(r.x[i - 1], r.z[i - 1]));
                for (int start = 0, chunk = 0; start < n - 1; start += 150, chunk++)
                {
                    int end = Mathf.Min(start + 150, n - 1);
                    var mb = new MeshBits();
                    for (int i = start; i <= end; i++)
                    {
                        int ip = Mathf.Max(i - 1, 0), inx = Mathf.Min(i + 1, n - 1);
                        var dir = new Vector3(r.x[inx] - r.x[ip], 0f, r.z[inx] - r.z[ip]).normalized;
                        var right = new Vector3(dir.z, 0f, -dir.x);
                        float reach = r.halfWidth[i] + 5f;
                        // Rapids where the river is narrow or drops fast.
                        int i2 = Mathf.Min(i + 4, n - 1), i0 = Mathf.Max(i - 4, 0);
                        float drop = (r.level[i0] - r.level[i2]) / Mathf.Max(dist[i2] - dist[i0], 1f);
                        float turb = Mathf.Clamp01((10f - r.halfWidth[i]) / 6f * 0.6f + drop * 25f);
                        float foam = Mathf.Clamp01(1f - dist[i] / 45f);           // churned water below the falls
                        for (int s = 0; s < Across; s++)
                        {
                            float lat = Mathf.Lerp(-reach, reach, s / (Across - 1f));
                            var q = new Vector3(r.x[i], r.level[i] + ty, r.z[i]) + right * lat;
                            mb.Add(q, Vector3.up, new Vector4(right.x, 0f, right.z, 1f), new Vector2(lat, dist[i]), new Color(turb, foam, 0f, 1f));
                        }
                        if (i > start) mb.Strip(i - start - 1, Across);
                    }
                    Place(root, mb.Build($"River_{chunk}"), mat);
                }
            }

            // --- Lake: an ellipse a little larger than its bed, so it meets the shore slopes.
            var l = info.lake;
            if (l != null && l.rx > 0f)
            {
                var mb = new MeshBits();
                const int Seg = 48, Rings = 5;
                var rot = Quaternion.Euler(0f, -l.yaw, 0f);
                for (int ring = 0; ring <= Rings; ring++)
                {
                    float t = ring / (float)Rings;
                    for (int k = 0; k < Seg; k++)
                    {
                        float a = k * Mathf.PI * 2f / Seg;
                        var off = rot * new Vector3(Mathf.Cos(a) * (l.rx + 8f) * t, 0f, Mathf.Sin(a) * (l.rz + 8f) * t);
                        var q = new Vector3(l.x, l.level + ty, l.z) + off;
                        float foam = info.falls != null ? Mathf.Clamp01(1f - Vector2.Distance(new Vector2(q.x, q.z), new Vector2(fallsPos.x, fallsPos.z)) / 22f) : 0f;
                        mb.Add(q, Vector3.up, new Vector4(1f, 0f, 0f, 1f), new Vector2(q.x, q.z), new Color(0.15f, foam * 0.8f, 0f, 0.08f));
                    }
                }
                for (int ring = 0; ring < Rings; ring++)
                for (int k = 0; k < Seg; k++)
                {
                    int a0 = ring * Seg + k, a1 = ring * Seg + (k + 1) % Seg, b0 = a0 + Seg, b1 = a1 + Seg;
                    mb.Tri(a0, b0, b1);
                    mb.Tri(a0, b1, a1);
                }
                Place(root, mb.Build("Lake"), mat);
            }

            // --- Waterfall: a curved sheet pouring from the cliff notch into the lake, plus mist.
            if (info.falls != null && info.falls.top > 0f && l != null)
            {
                float baseY = terrain.SampleHeight(fallsPos) + ty - 3f;   // the cliff formation's base (sink 3 m)
                float top = baseY + 18.4f;                               // floor of its notch
                float bottom = l.level + ty - 0.3f;
                var mb = new MeshBits();
                const int Rows = 12, Cols = 5;
                float h = Mathf.Max(top - bottom, 1f);
                for (int j = 0; j <= Rows; j++)
                {
                    float t = j / (float)Rows;
                    float y = Mathf.Lerp(top, bottom, t);
                    float zOff = -0.8f - 3.2f * Mathf.Sqrt(t);           // arcs out from the face (the lake is to the south)
                    float half = Mathf.Lerp(3.6f, 5.2f, t);
                    for (int c = 0; c <= Cols; c++)
                    {
                        float u = Mathf.Lerp(-half, half, c / (float)Cols);
                        var q = new Vector3(fallsPos.x + u, y, fallsPos.z + zOff);
                        mb.Add(q, Vector3.back, new Vector4(1f, 0f, 0f, 1f), new Vector2(u, t * h), new Color(1f, 1f, 1f, 1f));
                    }
                    if (j > 0)
                        for (int c = 0; c < Cols; c++)
                        {
                            int a0 = (j - 1) * (Cols + 1) + c, a1 = a0 + 1, b0 = a0 + Cols + 1, b1 = b0 + 1;
                            mb.Tri(a0, a1, b1);
                            mb.Tri(a0, b1, b0);
                        }
                }
                Place(root, mb.Build("Waterfall"), mat);

                var mistGo = new GameObject("Falls Mist");
                mistGo.transform.SetParent(root, false);
                mistGo.transform.position = new Vector3(fallsPos.x, bottom + 0.5f, fallsPos.z - 5f);
                var ps = mistGo.AddComponent<ParticleSystem>();
                var main = ps.main;
                main.startLifetime = 6f;
                main.startSpeed = new ParticleSystem.MinMaxCurve(0.4f, 1.2f);
                main.startSize = new ParticleSystem.MinMaxCurve(4f, 9f);
                main.startColor = new Color(0.92f, 0.95f, 1f, 0.22f);
                main.maxParticles = 80;
                main.simulationSpace = ParticleSystemSimulationSpace.World;
                var em = ps.emission;
                em.rateOverTime = 9f;
                var shape = ps.shape;
                shape.shapeType = ParticleSystemShapeType.Box;
                shape.scale = new Vector3(9f, 1f, 3f);
                var col = ps.colorOverLifetime;
                col.enabled = true;
                var grad = new Gradient();
                grad.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                             new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.25f, 0.2f), new GradientAlphaKey(0f, 1f) });
                col.color = grad;
                var rend = mistGo.GetComponent<ParticleSystemRenderer>();
                rend.sharedMaterial = MaterialLibrary.Dust();
            }
            Debug.Log("[Offroad] Built river, lake and waterfall");
        }

        static void Place(Transform root, Mesh mesh, Material mat)
        {
            var path = $"{GeneratedDir}/Water/{Region}_{mesh.name}.asset";
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mesh, path);
            var go = new GameObject(mesh.name);
            go.transform.SetParent(root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            go.isStatic = true;
        }

        /// <summary>Small mesh builder.</summary>
        class MeshBits
        {
            readonly List<Vector3> _v = new List<Vector3>(), _n = new List<Vector3>();
            readonly List<Vector4> _t = new List<Vector4>();
            readonly List<Vector2> _uv = new List<Vector2>();
            readonly List<Color> _c = new List<Color>();
            readonly List<int> _i = new List<int>();

            public void Add(Vector3 v, Vector3 n, Vector4 t, Vector2 uv, Color c) { _v.Add(v); _n.Add(n); _t.Add(t); _uv.Add(uv); _c.Add(c); }
            public void Tri(int a, int b, int c) { _i.Add(a); _i.Add(b); _i.Add(c); }

            /// <summary>Quads between row `row` and the next (each row `across` vertices).</summary>
            public void Strip(int row, int across)
            {
                int a = row * across, b = (row + 1) * across;
                for (int s = 0; s < across - 1; s++)
                {
                    Tri(a + s, b + s, b + s + 1);
                    Tri(a + s, b + s + 1, a + s + 1);
                }
            }

            public Mesh Build(string name)
            {
                var m = new Mesh { name = name };
                if (_v.Count > 65000) m.indexFormat = IndexFormat.UInt32;
                m.SetVertices(_v);
                m.SetNormals(_n);
                m.SetTangents(_t);
                m.SetUVs(0, _uv);
                m.SetColors(_c);
                m.SetTriangles(_i, 0);
                m.RecalculateBounds();
                return m;
            }
        }

        static GameObject CreatePropPrefab(GameObject model, string name, PropKind kind)
        {
            var src = model.transform.Find(name);
            if (src == null) { Debug.LogWarning($"[Offroad] Prop mesh {name} not found in model"); return null; }
            var srcMf = src.GetComponent<MeshFilter>();
            var srcMr = src.GetComponent<MeshRenderer>();

            var go = new GameObject(name);
            go.AddComponent<MeshFilter>().sharedMesh = srcMf.sharedMesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = MaterialLibrary.Remap(srcMr.sharedMaterials);
            mr.shadowCastingMode = kind.shadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
            switch (kind.collider)
            {
                case 1: go.AddComponent<MeshCollider>().sharedMesh = srcMf.sharedMesh; break;
                case 2:
                    var mc = go.AddComponent<MeshCollider>();
                    mc.sharedMesh = srcMf.sharedMesh;
                    mc.convex = true;
                    break;
                case 3:
                    var cap = go.AddComponent<CapsuleCollider>();
                    cap.radius = 0.2f;
                    cap.height = 2.2f;
                    cap.center = new Vector3(0f, 1.0f, 0f);
                    break;
            }
            var lod = go.AddComponent<LODGroup>();
            var lowSrc = model.transform.Find(name + "_LOD1");
            if (lowSrc != null)
            {
                var low = new GameObject(name + "_LOD1");
                low.transform.SetParent(go.transform, false);
                low.AddComponent<MeshFilter>().sharedMesh = lowSrc.GetComponent<MeshFilter>().sharedMesh;
                var lowMr = low.AddComponent<MeshRenderer>();
                lowMr.sharedMaterials = mr.sharedMaterials;
                lowMr.shadowCastingMode = mr.shadowCastingMode;
                lod.SetLODs(new[]
                {
                    new LOD(Mathf.Max(kind.cullHeight * 12f, 0.05f), new Renderer[] { mr }),
                    new LOD(kind.cullHeight, new Renderer[] { lowMr }),
                });
            }
            else lod.SetLODs(new[] { new LOD(kind.cullHeight, new Renderer[] { mr }) });
            lod.fadeMode = LODFadeMode.None;

            Directory.CreateDirectory($"{PrefabDir}/Props");
            var path = $"{PrefabDir}/Props/{name}.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
            Object.DestroyImmediate(go);
            return prefab;
        }

        // ------------------------------------------------------------------ landmarks

        static readonly HashSet<string> SmallLandmarkPieces = new HashSet<string> { "FireRing", "Crates", "Signpost", "Tent", "Cairn" };

        static void PlaceLandmarks(Terrain terrain, RegionInfo info)
        {
            if (info.landmarks == null) return;
            var model = P.landmarkModels.Select(AssetDatabase.LoadAssetAtPath<GameObject>).Where(m => m != null).ToArray();
            if (model.Length == 0) throw new Exception("Landmarks model missing: " + string.Join(", ", P.landmarkModels));
            var prefabs = new Dictionary<string, GameObject>();
            var root = new GameObject("Landmarks").transform;

            foreach (var l in info.landmarks)
            {
                var go = new GameObject(l.name);
                go.transform.SetParent(root, false);
                var centre = new Vector3(l.x, 0f, l.z);
                centre.y = terrain.SampleHeight(centre) + terrain.transform.position.y;
                go.transform.position = centre;
                var marker = go.AddComponent<Landmark>();
                marker.id = l.id;
                marker.displayName = l.name;
                marker.discoverRadius = l.discoverRadius;
                marker.reward = l.id == "basecamp" || l.id == "trailhead" ? 0 : 150;
                foreach (var piece in l.pieces ?? Array.Empty<PieceInfo>())
                    PlacePiece(terrain, model, prefabs, piece, go.transform);
            }

            var markers = new GameObject("Trail Markers").transform;
            foreach (var m in info.markers ?? Array.Empty<PieceInfo>())
                PlacePiece(terrain, model, prefabs, m, markers);
            Debug.Log($"[Offroad] Placed {info.landmarks.Length} landmarks and {info.markers?.Length ?? 0} trail markers");
        }

        static void PlacePiece(Terrain terrain, GameObject[] models, Dictionary<string, GameObject> prefabs, PieceInfo p, Transform parent)
        {
            if (!prefabs.TryGetValue(p.model, out var prefab))
            {
                var model = models.FirstOrDefault(m => m.transform.Find(p.model) != null) ?? models[0];
                prefab = CreateLandmarkPrefab(model, p.model);
                prefabs[p.model] = prefab;
            }
            if (prefab == null) return;
            var pos = new Vector3(p.x, 0f, p.z);
            pos.y = terrain.SampleHeight(pos) + terrain.transform.position.y - p.sink;
            if (Mathf.Abs(p.absY) > 0.001f) pos.y = p.absY + terrain.transform.position.y;   // e.g. a bridge deck
            var td = terrain.terrainData;
            Vector3 n = td.GetInterpolatedNormal(p.x / td.size.x, p.z / td.size.z);
            Quaternion tilt = Quaternion.FromToRotation(Vector3.up, Vector3.Slerp(Vector3.up, n, p.align));
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            inst.transform.SetPositionAndRotation(pos, tilt * Quaternion.Euler(0f, p.yaw, 0f));
        }

        static GameObject CreateLandmarkPrefab(GameObject model, string name)
        {
            var src = model.transform.Find(name);
            if (src == null) { Debug.LogWarning($"[Offroad] Landmark mesh {name} not found"); return null; }
            bool small = SmallLandmarkPieces.Contains(name);
            var go = new GameObject(name);
            var renderers = new List<Renderer> { AddMesh(go, src) };
            go.AddComponent<MeshCollider>().sharedMesh = src.GetComponent<MeshFilter>().sharedMesh;

            if (name == "Windmill")
            {
                var rotorSrc = model.transform.Find("Windmill_Rotor");
                if (rotorSrc != null)
                {
                    var rotor = new GameObject("Rotor");
                    rotor.transform.SetParent(go.transform, false);
                    rotor.transform.localPosition = rotorSrc.localPosition - src.localPosition;
                    rotor.transform.localRotation = rotorSrc.localRotation;
                    renderers.Add(AddMesh(rotor, rotorSrc));
                    rotor.AddComponent<WindmillRotor>();
                }
            }

            var lod = go.AddComponent<LODGroup>();
            lod.SetLODs(new[] { new LOD(small ? 0.01f : 0.0012f, renderers.ToArray()) });
            lod.fadeMode = LODFadeMode.None;
            Directory.CreateDirectory($"{PrefabDir}/Landmarks");
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, $"{PrefabDir}/Landmarks/{name}.prefab");
            Object.DestroyImmediate(go);
            return prefab;
        }

        static Renderer AddMesh(GameObject go, Transform src)
        {
            go.AddComponent<MeshFilter>().sharedMesh = src.GetComponent<MeshFilter>().sharedMesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = MaterialLibrary.Remap(src.GetComponent<MeshRenderer>().sharedMaterials);
            return mr;
        }

        // ------------------------------------------------------------------ vehicle

        static readonly string[] WheelMarkers = { "WheelFL", "WheelFR", "WheelRL", "WheelRR" };

        /// <summary>Collects every body, tyre and accessory mesh from Fleet.fbx into a VehicleArt asset.</summary>
        static VehicleArt BuildVehicleArt()
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(VehicleModel);
            if (model == null) throw new Exception("Vehicle model missing: " + VehicleModel);
            const string path = "Assets/Art/VehicleArt.asset";
            var art = AssetDatabase.LoadAssetAtPath<VehicleArt>(path);
            if (art == null)
            {
                art = ScriptableObject.CreateInstance<VehicleArt>();
                AssetDatabase.CreateAsset(art, path);
            }

            VehicleArt.Part Part(string name)
            {
                var t = model.transform.Find(name);
                if (t == null) throw new Exception($"{VehicleModel} has no '{name}'");
                return new VehicleArt.Part
                {
                    id = name,
                    mesh = t.GetComponent<MeshFilter>().sharedMesh,
                    materials = MaterialLibrary.Remap(t.GetComponent<MeshRenderer>().sharedMaterials),
                };
            }

            Vector3 Marker(string name)
            {
                var t = model.transform.Find(name);
                if (t == null) throw new Exception($"{VehicleModel} has no marker '{name}'");
                return t.localPosition;
            }

            art.bodies = new[] { "Ridgeback", "Packhorse" }.Select(b => new VehicleArt.BodyArt
            {
                id = b,
                body = Part($"Body_{b}"),
                wheelPositions = WheelMarkers.Select(w => Marker($"{b}_{w}")).ToArray(),
                spareMount = Marker($"{b}_Spare"),
                accessories = new[] { Part($"RoofRack_{b}"), Part($"Snorkel_{b}"), Part($"BullBar_{b}") },
            }).ToArray();
            art.tires = new[] { Part("Wheel_AT"), Part("Wheel_MT"), Part("Wheel_Dune") };
            art.dustMaterial = MaterialLibrary.Dust();
            art.bodyPhysics = MaterialLibrary.VehicleBodyPhysics();
            EditorUtility.SetDirty(art);
            AssetDatabase.SaveAssets();

            var fl = art.bodies[0].wheelPositions[0];
            if ((fl - VehicleRig.DefaultWheelPositions[0]).magnitude > 0.05f)
                Debug.LogWarning($"[Offroad] Ridgeback FL wheel at {fl}, expected {VehicleRig.DefaultWheelPositions[0]} - check FBX axes");
            return art;
        }

        static OffroadVehicle CreateVehicle(Terrain terrain, RegionInfo info)
        {
            var art = BuildVehicleArt();
            var root = new GameObject("Expedition Vehicle");
            VehicleRig.Assemble(root, new VehicleRig.Parts
            {
                wheelPositions = art.Body("Ridgeback").wheelPositions,
                dustMaterial = art.dustMaterial,
                bodyPhysicsMaterial = art.bodyPhysics,
            });
            root.AddComponent<PlayerVehicleController>();
            var assembler = root.AddComponent<VehicleAssembler>();
            assembler.art = art;
            assembler.Apply(new Garage.Loadout());   // default build; the saved loadout is fitted at runtime
            Directory.CreateDirectory(PrefabDir);
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, $"{PrefabDir}/ExpeditionVehicle.prefab");
            Object.DestroyImmediate(root);

            var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            var spawn = new Vector3(info.spawn.x, 0f, info.spawn.z);
            spawn.y = terrain.SampleHeight(spawn) + 0.35f;
            inst.transform.SetPositionAndRotation(spawn, Quaternion.Euler(0f, info.spawn.yaw, 0f));
            return inst.GetComponent<OffroadVehicle>();
        }

        // ------------------------------------------------------------------ camera + systems

        static Camera CreateCamera(OffroadVehicle vehicle)
        {
            var go = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = go.AddComponent<Camera>();
            cam.fieldOfView = 58f;
            cam.nearClipPlane = 0.3f;
            cam.farClipPlane = 800f;
            cam.allowHDR = true;
            cam.allowMSAA = false;
            go.AddComponent<AudioListener>();
            var data = cam.GetUniversalAdditionalCameraData();
            data.renderPostProcessing = true;
            data.antialiasing = AntialiasingMode.FastApproximateAntialiasing;
            data.renderShadows = true;

            var chase = go.AddComponent<ChaseCamera>();
            chase.target = vehicle.GetComponent<Rigidbody>();
            var t = vehicle.transform;
            go.transform.position = t.position - t.forward * 7f + Vector3.up * 2.6f;
            go.transform.LookAt(t.position + Vector3.up * 1.2f);
            return cam;
        }

        static void CreateSystems(OffroadVehicle vehicle, Camera cam)
        {
            var go = new GameObject("Systems");
            var atmosphere = go.AddComponent<Atmosphere>();
            atmosphere.contrast = P.contrast;
            atmosphere.saturation = P.saturation;
            atmosphere.temperature = P.temperature;
            go.AddComponent<DiscoveryTracker>().player = vehicle.transform;
            var trails = go.AddComponent<GroundTrails>();     // tyre tracks pressed into soft ground
            trails.stampShader = Shader.Find("Hidden/Offroad/TrailStamp");
            if (trails.stampShader == null) Debug.LogWarning("[Offroad] Trail stamp shader missing");
            var runner = go.AddComponent<Game.MissionRunner>();
            runner.vehicle = vehicle;

            var uiGo = new GameObject("UI");
            var doc = uiGo.AddComponent<UnityEngine.UIElements.UIDocument>();
            doc.panelSettings = PanelSettingsAsset();
            var ui = uiGo.AddComponent<UIRoot>();
            ui.style = AssetDatabase.LoadAssetAtPath<UnityEngine.UIElements.StyleSheet>("Assets/UI/Styles/Game.uss");
            ui.body = AssetDatabase.LoadAssetAtPath<Font>("Assets/UI/Fonts/Barlow-Medium.ttf");
            ui.bodyBold = AssetDatabase.LoadAssetAtPath<Font>("Assets/UI/Fonts/Barlow-SemiBold.ttf");
            ui.head = AssetDatabase.LoadAssetAtPath<Font>("Assets/UI/Fonts/BarlowCondensed-Bold.ttf");
            ui.headSemi = AssetDatabase.LoadAssetAtPath<Font>("Assets/UI/Fonts/BarlowCondensed-SemiBold.ttf");
            if (ui.style == null || ui.head == null) Debug.LogWarning("[Offroad] UI stylesheet or fonts missing");
            ui.runner = runner;
            ui.vehicle = vehicle;

            var flow = go.AddComponent<Game.GameFlow>();
            flow.regionId = Region;
            flow.vehicle = vehicle;
            flow.cam = cam.GetComponent<ChaseCamera>();
            flow.runner = runner;
            flow.ui = ui;
            ui.flow = flow;
        }

        static UnityEngine.UIElements.PanelSettings PanelSettingsAsset()
        {
            const string path = "Assets/UI/PanelSettings.asset";
            var ps = AssetDatabase.LoadAssetAtPath<UnityEngine.UIElements.PanelSettings>(path);
            if (ps == null)
            {
                ps = ScriptableObject.CreateInstance<UnityEngine.UIElements.PanelSettings>();
                AssetDatabase.CreateAsset(ps, path);
            }
            ps.themeStyleSheet = AssetDatabase.LoadAssetAtPath<UnityEngine.UIElements.ThemeStyleSheet>("Assets/UI/Styles/RuntimeTheme.tss");
            ps.scaleMode = UnityEngine.UIElements.PanelScaleMode.ScaleWithScreenSize;
            ps.referenceResolution = new Vector2Int(1920, 1080);
            ps.screenMatchMode = UnityEngine.UIElements.PanelScreenMatchMode.MatchWidthOrHeight;
            ps.match = 0.5f;
            EditorUtility.SetDirty(ps);
            return ps;
        }

        static T ReadJson<T>(string path) => JsonUtility.FromJson<T>(File.ReadAllText(path));
    }
}
