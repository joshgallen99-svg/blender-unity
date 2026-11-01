using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Offroad.EditorTools
{
    /// <summary>
    /// One-stop project configuration from code: URP pipeline asset, colour space, player and
    /// build settings. Idempotent; run by the scene builder and by CI before every build.
    /// </summary>
    public static class ProjectSetup
    {
        const string SettingsDir = "Assets/Settings";
        const string PipelinePath = SettingsDir + "/URP_Pipeline.asset";
        const string RendererPath = SettingsDir + "/URP_Renderer.asset";

        [MenuItem("Offroad/Apply Project Settings")]
        public static void Run()
        {
            var pipeline = EnsurePipeline();
            ConfigurePipeline(pipeline);

            GraphicsSettings.defaultRenderPipeline = pipeline;
            int current = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = pipeline;
            }
            QualitySettings.SetQualityLevel(current, false);

            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.companyName = "Offroad Expedition";
            PlayerSettings.productName = "Offroad Expedition (Prototype)";
            PlayerSettings.runInBackground = true;
            // Components are added from code at runtime (particles, probes, colliders in tests);
            // keep engine modules that the scene does not reference directly.
            PlayerSettings.stripEngineCode = false;
            PlayerSettings.SetManagedStrippingLevel(UnityEditor.Build.NamedBuildTarget.WebGL, ManagedStrippingLevel.Minimal);
            PlayerSettings.SetManagedStrippingLevel(UnityEditor.Build.NamedBuildTarget.Standalone, ManagedStrippingLevel.Minimal);

            AssetDatabase.SaveAssets();
        }

        static UniversalRenderPipelineAsset EnsurePipeline()
        {
            var asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (asset != null) return asset;

            Directory.CreateDirectory(SettingsDir);
            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(RendererPath);
            if (renderer == null) renderer = CreateRenderer();
            asset = UniversalRenderPipelineAsset.Create(renderer);
            AssetDatabase.CreateAsset(asset, PipelinePath);
            AssetDatabase.SaveAssets();
            return asset;
        }

        static UniversalRendererData CreateRenderer()
        {
            // URP's own editor helper fills in default resources (post-processing data, shaders).
            var method = typeof(UniversalRenderPipelineAsset).GetMethod("CreateRendererAsset",
                BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            if (method != null)
            {
                var args = new object[method.GetParameters().Length];
                var ps = method.GetParameters();
                for (int i = 0; i < ps.Length; i++)
                {
                    if (ps[i].ParameterType == typeof(string) && i == 0) args[i] = RendererPath;
                    else if (ps[i].ParameterType == typeof(RendererType)) args[i] = RendererType.UniversalRenderer;
                    else if (ps[i].ParameterType == typeof(bool)) args[i] = false;   // relativePath
                    else if (ps[i].ParameterType == typeof(string)) args[i] = "Renderer";
                    else args[i] = ps[i].HasDefaultValue ? ps[i].DefaultValue : null;
                }
                if (method.Invoke(null, args) is UniversalRendererData created)
                {
                    if (!AssetDatabase.Contains(created)) AssetDatabase.CreateAsset(created, RendererPath);
                    return created;
                }
            }
            var data = ScriptableObject.CreateInstance<UniversalRendererData>();
            AssetDatabase.CreateAsset(data, RendererPath);
            return data;
        }

        static void ConfigurePipeline(UniversalRenderPipelineAsset a)
        {
            a.supportsHDR = true;
            a.msaaSampleCount = 1;
            a.renderScale = 1f;
            a.shadowDistance = 120f;
            a.shadowCascadeCount = 2;
            a.useSRPBatcher = true;
            a.supportsCameraDepthTexture = false;
            a.supportsCameraOpaqueTexture = false;
            // Sun only: no additional lights means fewer shader variants and cheaper lighting.
            var so = new SerializedObject(a);
            var addl = so.FindProperty("m_AdditionalLightsRenderingMode");
            if (addl != null) { addl.intValue = (int)LightRenderingMode.Disabled; so.ApplyModifiedPropertiesWithoutUndo(); }
            a.upscalingFilter = UpscalingFilterSelection.FSR;
            a.colorGradingMode = ColorGradingMode.LowDynamicRange;
            EditorUtility.SetDirty(a);
        }
    }
}
