using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Offroad.EditorTools
{
    /// <summary>
    /// Creates the project's URP materials from code. Names match the Blender material names,
    /// so imported meshes are re-skinned by looking up each sub-mesh's material name here.
    /// Colours are given in linear space (as in Blender) and converted for Unity.
    /// </summary>
    public static class MaterialLibrary
    {
        public const string Dir = "Assets/Art/Materials";
        const string LitShader = "Universal Render Pipeline/Lit";

        struct Spec
        {
            public Color linear;
            public float metallic, roughness, emission;
            public bool instanced;
            public Spec(float r, float g, float b, float metallic, float roughness, float emission = 0f, bool instanced = false)
            {
                linear = new Color(r, g, b); this.metallic = metallic; this.roughness = roughness;
                this.emission = emission; this.instanced = instanced;
            }
        }

        // Keep in sync with blender/vehicles/ridgeback.py and blender/props/desert_props.py palettes.
        static readonly Dictionary<string, Spec> Specs = new Dictionary<string, Spec>
        {
            ["Paint"] = new Spec(0.055f, 0.25f, 0.27f, 0f, 0.32f),
            ["PaintRoof"] = new Spec(0.80f, 0.77f, 0.69f, 0f, 0.38f),
            ["Paint2"] = new Spec(0.24f, 0.28f, 0.14f, 0f, 0.5f),
            ["Accent"] = new Spec(0.85f, 0.36f, 0.06f, 0f, 0.4f),
            ["Trim"] = new Spec(0.035f, 0.035f, 0.037f, 0f, 0.78f),
            ["Steel"] = new Spec(0.07f, 0.07f, 0.075f, 0.6f, 0.45f),
            ["Chassis"] = new Spec(0.02f, 0.02f, 0.02f, 0f, 0.85f),
            ["Chrome"] = new Spec(0.6f, 0.6f, 0.6f, 1f, 0.18f),
            ["Glass"] = new Spec(0.02f, 0.03f, 0.035f, 0f, 0.04f),
            ["Lights"] = new Spec(0.95f, 0.93f, 0.88f, 0f, 0.1f, 2.5f),
            ["TailLights"] = new Spec(0.5f, 0.02f, 0.02f, 0f, 0.2f, 1.2f),
            ["Amber"] = new Spec(0.9f, 0.42f, 0.05f, 0f, 0.2f, 0.8f),
            ["Canvas"] = new Spec(0.45f, 0.38f, 0.26f, 0f, 0.9f),
            ["Tire"] = new Spec(0.03f, 0.03f, 0.03f, 0f, 0.92f),
            ["Rim"] = new Spec(0.36f, 0.27f, 0.15f, 0.85f, 0.35f),
            ["Yucca"] = new Spec(0.25f, 0.36f, 0.27f, 0f, 0.6f, 0f, true),
            ["Bark"] = new Spec(0.33f, 0.28f, 0.23f, 0f, 0.9f, 0f, true),
            ["BarkBleached"] = new Spec(0.55f, 0.50f, 0.44f, 0f, 0.85f, 0f, true),
            ["Ash"] = new Spec(0.05f, 0.045f, 0.04f, 0f, 0.95f, 0f, true),
        };

        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>();

        // Materials that use the project's custom shaders instead of URP Lit.
        static readonly Dictionary<string, System.Func<Material>> Custom = new Dictionary<string, System.Func<Material>>
        {
            ["RockSandstone"] = () => Rock("RockSandstone", new Color(1.08f, 1.02f, 0.98f), 0.35f),
            ["RockPale"] = () => Rock("RockPale", new Color(1.55f, 1.38f, 1.2f), 0.22f),
            ["Leaves"] = () => Foliage("Leaves", "ScrubLeaves", 0.07f, 1.4f),
            ["LeavesFlowering"] = () => Foliage("LeavesFlowering", "ScrubFlowering", 0.07f, 1.3f),
            ["GrassCards"] = () => Foliage("GrassCards", "DryGrass", 0.14f, 0.7f),
            ["Wood"] = () => Textured("Wood", "Wood", Color.white, 0f, 0.12f),
            ["WoodDark"] = () => Textured("WoodDark", "Wood", new Color(0.55f, 0.5f, 0.46f), 0f, 0.1f),
            ["Rust"] = () => Textured("Rust", "Rust", Color.white, 0.25f, 0.22f),
            ["Galvanized"] = () => Textured("Galvanized", "Galvanized", Color.white, 0.65f, 0.45f),
            ["Canvas"] = () => Textured("Canvas", "Canvas", Color.white, 0f, 0.08f, 0.5f),
        };

        /// <summary>URP Lit with a tiling albedo + normal map (UVs are in metres, from Blender box projection).</summary>
        static Material Textured(string name, string texture, Color tint, float metallic, float smoothness, float tiling = 1f)
        {
            var m = LoadOrCreate($"{Dir}/{name}.mat", LitShader);
            m.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Art/Textures/Materials/{texture}_albedo.png"));
            m.SetTextureScale("_BaseMap", new Vector2(tiling, tiling));
            var normal = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Art/Textures/Materials/{texture}_normal.png");
            m.SetTexture("_BumpMap", normal);
            m.SetFloat("_BumpScale", 1f);
            if (normal) m.EnableKeyword("_NORMALMAP");
            m.SetColor("_BaseColor", tint);
            m.SetFloat("_Metallic", metallic);
            m.SetFloat("_Smoothness", smoothness);
            m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        static Material Rock(string name, Color tint, float strata)
        {
            var m = LoadOrCreate($"{Dir}/{name}.mat", "Offroad/RockTriplanar");
            m.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Terrain/Textures/RedRock_albedo.png"));
            m.SetTexture("_BumpMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Terrain/Textures/RedRock_normal.png"));
            m.SetTexture("_TopMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Terrain/Textures/Sand_albedo.png"));
            m.SetTexture("_TopNormal", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Terrain/Textures/Sand_normal.png"));
            m.SetColor("_BaseColor", tint);
            m.SetColor("_TopColor", new Color(1.05f, 1.0f, 0.95f));
            m.SetFloat("_Scale", 5f);
            m.SetFloat("_TopScale", 9f);
            m.SetFloat("_StrataStrength", strata);
            m.SetFloat("_TopAmount", 0.42f);
            m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        static Material Foliage(string name, string texture, float wind, float windHeight)
        {
            var m = LoadOrCreate($"{Dir}/{name}.mat", "Offroad/Foliage");
            m.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Art/Textures/Foliage/{texture}.png"));
            m.SetColor("_BaseColor", Color.white);
            m.SetFloat("_Cutoff", 0.45f);
            m.SetFloat("_WindStrength", wind);
            m.SetFloat("_WindHeight", windHeight);
            m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        public static void EnsureAll()
        {
            Cache.Clear();
            Directory.CreateDirectory(Dir);
            foreach (var kv in Specs) Get(kv.Key);
            foreach (var kv in Custom) Get(kv.Key);
            AssetDatabase.SaveAssets();
        }

        /// <summary>Material for a Blender material name (falls back to a neutral grey).</summary>
        public static Material Get(string name)
        {
            if (Cache.TryGetValue(name, out var m) && m) return m;
            if (Custom.TryGetValue(name, out var make))
            {
                m = make();
                Cache[name] = m;
                return m;
            }
            if (!Specs.TryGetValue(name, out var spec))
            {
                Debug.LogWarning($"MaterialLibrary: no spec for '{name}', using grey.");
                spec = new Spec(0.4f, 0.4f, 0.4f, 0f, 0.8f);
            }
            m = LoadOrCreate($"{Dir}/{name}.mat", LitShader);
            m.SetColor("_BaseColor", spec.linear.gamma);
            m.SetFloat("_Metallic", spec.metallic);
            m.SetFloat("_Smoothness", 1f - spec.roughness);
            m.enableInstancing = spec.instanced;
            if (spec.emission > 0f)
            {
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                m.SetColor("_EmissionColor", spec.linear * spec.emission);
            }
            else
            {
                m.DisableKeyword("_EMISSION");
                m.SetColor("_EmissionColor", Color.black);
            }
            EditorUtility.SetDirty(m);
            Cache[name] = m;
            return m;
        }

        /// <summary>Replaces imported materials with library ones, matched by name.</summary>
        public static Material[] Remap(Material[] imported)
        {
            var result = new Material[imported.Length];
            for (int i = 0; i < imported.Length; i++)
                result[i] = Get(imported[i] ? imported[i].name : "Missing");
            return result;
        }

        public static Material Terrain()
        {
            var m = LoadOrCreate($"{Dir}/Terrain.mat", "Universal Render Pipeline/Terrain/Lit");
            m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        public static Material Skybox()
        {
            var m = LoadOrCreate($"{Dir}/Skybox_GoldenHour.mat", "Skybox/Procedural");
            m.SetFloat("_SunDisk", 2f);               // high quality
            m.SetFloat("_SunSize", 0.035f);
            m.SetFloat("_SunSizeConvergence", 6f);
            m.SetFloat("_AtmosphereThickness", 1.35f);
            m.SetColor("_SkyTint", new Color(0.52f, 0.52f, 0.56f));
            m.SetColor("_GroundColor", new Color(0.55f, 0.42f, 0.34f));
            m.SetFloat("_Exposure", 1.15f);
            EditorUtility.SetDirty(m);
            return m;
        }

        public static Material Dust()
        {
            var tex = SoftParticleTexture();
            var m = LoadOrCreate($"{Dir}/Dust.mat", "Universal Render Pipeline/Particles/Unlit");
            m.SetTexture("_BaseMap", tex);
            m.SetColor("_BaseColor", Color.white);
            m.SetFloat("_Surface", 1f);                // transparent
            m.SetFloat("_Blend", 0f);                  // alpha
            m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat("_ZWrite", 0f);
            m.SetOverrideTag("RenderType", "Transparent");
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = (int)RenderQueue.Transparent;
            EditorUtility.SetDirty(m);
            return m;
        }

        public static PhysicsMaterial VehicleBodyPhysics()
        {
            const string path = "Assets/Art/Physics/VehicleBody.asset";
            var pm = AssetDatabase.LoadAssetAtPath<PhysicsMaterial>(path);
            if (pm == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                pm = Vehicles.VehicleRig.CreateBodyPhysicsMaterial();
                AssetDatabase.CreateAsset(pm, path);
            }
            return pm;
        }

        static Texture2D SoftParticleTexture()
        {
            const string path = "Assets/Art/Textures/SoftParticle.png";
            if (!File.Exists(path))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                const int n = 128;
                var tex = new Texture2D(n, n, TextureFormat.RGBA32, false);
                var px = new Color32[n * n];
                for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2f - 1f, dy = (y + 0.5f) / n * 2f - 1f;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float noise = Mathf.PerlinNoise(x * 0.06f, y * 0.06f) * 0.6f + Mathf.PerlinNoise(x * 0.15f + 7f, y * 0.15f) * 0.4f;
                    float a = Mathf.Clamp01(1f - r) * Mathf.Clamp01(1f - r) * Mathf.Lerp(0.55f, 1f, noise);
                    px[y * n + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
                tex.SetPixels32(px);
                File.WriteAllBytes(path, tex.EncodeToPNG());
                Object.DestroyImmediate(tex);
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static Material LoadOrCreate(string path, string shaderName)
        {
            var shader = Shader.Find(shaderName);
            if (shader == null) throw new System.Exception($"Shader not found: {shaderName}");
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                m = new Material(shader);
                AssetDatabase.CreateAsset(m, path);
            }
            else if (m.shader != shader) m.shader = shader;
            return m;
        }
    }
}
