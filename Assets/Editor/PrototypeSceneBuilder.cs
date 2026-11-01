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
        const string Region = "desert";
        const string SourceDir = "Assets/Terrain/Source~";
        const string GeneratedDir = "Assets/Terrain/Generated";
        const string PrefabDir = "Assets/Prefabs";
        const string VehicleModel = "Assets/Models/Vehicles/Fleet.fbx";
        const string PropsModel = "Assets/Models/Props/DesertProps.fbx";
        const string LandmarksModel = "Assets/Models/Landmarks/DesertLandmarks.fbx";

        [Serializable] public class SpawnInfo { public float x, z, yaw; }
        [Serializable] public class RegionInfo
        {
            public float size, height;
            public int resolution, splatResolution;
            public string[] layers;
            public SpawnInfo spawn;
            public LandmarkInfo[] landmarks;
            public PieceInfo[] markers;
        }
        [Serializable] public class PieceInfo { public string model; public float x, z, yaw, sink, align; }
        [Serializable] public class LandmarkInfo
        {
            public string id, name;
            public float x, z, radius, discoverRadius;
            public PieceInfo[] pieces;
        }
        [Serializable] public class PropEntry { public string kind; public int variant; public float x, z, yaw, scale, sink; }
        [Serializable] public class ScatterFile { public PropEntry[] props; }

        struct PropKind
        {
            public float cullHeight;     // LOD screen height below which it disappears (scaled by Detail setting)
            public bool shadows;
            public int collider;         // 0 none, 1 mesh, 2 convex mesh, 3 trunk capsule
            public float alignToGround;  // 0 upright .. 1 fully aligned to terrain normal
        }

        static readonly Dictionary<string, PropKind> Kinds = new Dictionary<string, PropKind>
        {
            ["Boulder"] = new PropKind { cullHeight = 0.004f, shadows = true, collider = 1, alignToGround = 0.6f },
            ["Slab"] = new PropKind { cullHeight = 0.006f, shadows = true, collider = 1, alignToGround = 0.85f },
            ["Hoodoo"] = new PropKind { cullHeight = 0.0015f, shadows = true, collider = 1, alignToGround = 0f },
            ["Rock"] = new PropKind { cullHeight = 0.012f, shadows = false, collider = 2, alignToGround = 0.8f },
            ["Scrub"] = new PropKind { cullHeight = 0.014f, shadows = true, collider = 0, alignToGround = 0.3f },
            ["Grass"] = new PropKind { cullHeight = 0.03f, shadows = false, collider = 0, alignToGround = 0.6f },
            ["Yucca"] = new PropKind { cullHeight = 0.012f, shadows = true, collider = 0, alignToGround = 0.1f },
            ["DeadTree"] = new PropKind { cullHeight = 0.006f, shadows = true, collider = 3, alignToGround = 0.05f },
        };

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
            AssetDatabase.ImportAsset(PropsModel, ImportAssetOptions.ForceUpdate);
            AssetDatabase.ImportAsset(LandmarksModel, ImportAssetOptions.ForceUpdate);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var info = ReadJson<RegionInfo>($"{SourceDir}/{Region}_info.json");

            var sun = CreateLighting();
            var terrain = CreateTerrain(info);
            PlaceProps(terrain, info);
            PlaceLandmarks(terrain, info);
            var vehicle = CreateVehicle(terrain, info);
            var cam = CreateCamera(vehicle);
            CreateSystems(vehicle, cam);

            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log($"[Offroad] Built {ScenePath}: terrain {info.size}m, camera {cam.name}");
        }

        // ------------------------------------------------------------------ lighting

        static Light CreateLighting()
        {
            var go = new GameObject("Sun");
            var sun = go.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = new Color(1f, 0.80f, 0.62f);
            sun.intensity = 2.1f;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.88f;
            go.transform.rotation = Quaternion.Euler(22f, 19f, 0f);   // low golden-hour sun, side-on to the spawn heading

            RenderSettings.skybox = MaterialLibrary.Skybox();
            RenderSettings.sun = sun;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.52f, 0.60f, 0.76f);
            RenderSettings.ambientEquatorColor = new Color(0.72f, 0.57f, 0.45f);
            RenderSettings.ambientGroundColor = new Color(0.34f, 0.24f, 0.18f);
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.86f, 0.70f, 0.57f);
            RenderSettings.fogStartDistance = 180f;
            RenderSettings.fogEndDistance = 780f;
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

            var td = new TerrainData { name = "DesertTerrain" };
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

            var tdPath = $"{GeneratedDir}/DesertTerrain.asset";
            AssetDatabase.DeleteAsset(tdPath);
            AssetDatabase.CreateAsset(td, tdPath);

            var go = Terrain.CreateTerrainGameObject(td);
            go.name = "Terrain";
            var t = go.GetComponent<Terrain>();
            t.materialTemplate = MaterialLibrary.Terrain();
            t.drawInstanced = true;
            t.heightmapPixelError = 5f;
            t.basemapDistance = 300f;
            t.drawTreesAndFoliage = false;
            t.shadowCastingMode = ShadowCastingMode.On;
            go.AddComponent<TerrainSurfaces>();
            return t;
        }

        static TerrainLayer CreateLayer(string name)
        {
            float tile = name switch { "Sand" => 12f, "Gravel" => 5f, "CrackedSoil" => 10f, "RedRock" => 16f, _ => 8f };
            var layer = new TerrainLayer
            {
                diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{name}_albedo.png"),
                normalMapTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{name}_normal.png"),
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

        static void PlaceProps(Terrain terrain, RegionInfo info)
        {
            var scatter = ReadJson<ScatterFile>($"{SourceDir}/{Region}_scatter.json");
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(PropsModel);
            if (model == null) throw new Exception("Props model missing: " + PropsModel);
            var prefabs = new Dictionary<string, GameObject>();
            var root = new GameObject("Props").transform;
            var groups = new Dictionary<string, Transform>();
            var td = terrain.terrainData;

            foreach (var p in scatter.props)
            {
                string key = $"{p.kind}_{p.variant}";
                if (!prefabs.TryGetValue(key, out var prefab))
                {
                    prefab = CreatePropPrefab(model, key, Kinds.TryGetValue(p.kind, out var k) ? k : Kinds["Rock"]);
                    prefabs[key] = prefab;
                }
                if (prefab == null) continue;
                if (!groups.TryGetValue(p.kind, out var group))
                {
                    group = new GameObject(p.kind).transform;
                    group.SetParent(root, false);
                    groups[p.kind] = group;
                }

                var kind = Kinds.TryGetValue(p.kind, out var kk) ? kk : Kinds["Rock"];
                var pos = new Vector3(p.x, 0f, p.z);
                pos.y = terrain.SampleHeight(pos) + terrain.transform.position.y - p.sink * p.scale;
                Vector3 n = td.GetInterpolatedNormal(p.x / td.size.x, p.z / td.size.z);
                Quaternion tilt = Quaternion.FromToRotation(Vector3.up, Vector3.Slerp(Vector3.up, n, kind.alignToGround));

                var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab, group);
                inst.transform.SetPositionAndRotation(pos, tilt * Quaternion.Euler(0f, p.yaw, 0f));
                inst.transform.localScale = Vector3.one * p.scale;
            }
            Debug.Log($"[Offroad] Placed {scatter.props.Length} props");
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
            lod.SetLODs(new[] { new LOD(kind.cullHeight, new Renderer[] { mr }) });
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
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(LandmarksModel);
            if (model == null) throw new Exception("Landmarks model missing: " + LandmarksModel);
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
                marker.reward = l.id == "basecamp" ? 0 : 150;
                foreach (var piece in l.pieces ?? Array.Empty<PieceInfo>())
                    PlacePiece(terrain, model, prefabs, piece, go.transform);
            }

            var markers = new GameObject("Trail Markers").transform;
            foreach (var m in info.markers ?? Array.Empty<PieceInfo>())
                PlacePiece(terrain, model, prefabs, m, markers);
            Debug.Log($"[Offroad] Placed {info.landmarks.Length} landmarks and {info.markers?.Length ?? 0} trail markers");
        }

        static void PlacePiece(Terrain terrain, GameObject model, Dictionary<string, GameObject> prefabs, PieceInfo p, Transform parent)
        {
            if (!prefabs.TryGetValue(p.model, out var prefab))
            {
                prefab = CreateLandmarkPrefab(model, p.model);
                prefabs[p.model] = prefab;
            }
            if (prefab == null) return;
            var pos = new Vector3(p.x, 0f, p.z);
            pos.y = terrain.SampleHeight(pos) + terrain.transform.position.y - p.sink;
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
            go.AddComponent<Atmosphere>();
            go.AddComponent<DiscoveryTracker>().player = vehicle.transform;
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
