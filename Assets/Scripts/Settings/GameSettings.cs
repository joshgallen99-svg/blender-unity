using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Offroad.Settings
{
    public enum QualityPreset { BatterySaver, Low, Medium, High, Custom }
    public enum ShadowSetting { Off, Low, High }
    public enum AntiAliasingSetting { Off, FXAA, SMAA }
    public enum FrameCap { Fps30, Fps60, Unlimited }

    [Serializable]
    public class SettingsData
    {
        public QualityPreset preset = QualityPreset.Medium;
        [Range(0.5f, 1f)] public float renderScale = 0.9f;
        public ShadowSetting shadows = ShadowSetting.Low;
        public float viewDistance = 800f;
        public float detail = 1f;               // LOD bias: how far props stay visible
        public bool postEffects = true;
        public AntiAliasingSetting antiAliasing = AntiAliasingSetting.FXAA;
        public FrameCap frameCap = FrameCap.Fps60;
        public bool showFps;

        public SettingsData Clone() => (SettingsData)MemberwiseClone();
    }

    /// <summary>
    /// Graphics/performance settings: presets tuned for a fanless laptop, persisted in PlayerPrefs,
    /// applied to URP, the camera, fog, LODs, terrain and the frame-rate cap.
    /// </summary>
    public static class GameSettings
    {
        const string Key = "offroad.settings.v1";

        public static SettingsData Current { get; private set; } = Load();
        public static event Action<SettingsData> Changed;

        static UniversalRenderPipelineAsset _runtimeAsset;
        static int _lastScreenHeight;

        /// <summary>Internal render height cap per preset (before the user's render-scale slider).</summary>
        public static int MaxRenderHeight(QualityPreset p) => p switch
        {
            QualityPreset.BatterySaver => 720,
            QualityPreset.Low => 900,
            QualityPreset.High => 1440,
            _ => 1080,
        };

        public static float EffectiveRenderScale(SettingsData s)
        {
            int h = Mathf.Max(Screen.height, 1);
            var capPreset = s.preset == QualityPreset.Custom ? QualityPreset.Medium : s.preset;
            float cap = Mathf.Min(1f, MaxRenderHeight(capPreset) / (float)h);
            return Mathf.Clamp(s.renderScale * cap, 0.35f, 1f);
        }

        /// <summary>Re-apply the render scale when the window or display resolution changes.</summary>
        public static void CheckResolution()
        {
            if (_runtimeAsset != null && Screen.height != _lastScreenHeight)
            {
                _lastScreenHeight = Screen.height;
                _runtimeAsset.renderScale = EffectiveRenderScale(Current);
            }
        }

        public static SettingsData Preset(QualityPreset p)
        {
            switch (p)
            {
                case QualityPreset.BatterySaver:
                    return new SettingsData { preset = p, renderScale = 0.7f, shadows = ShadowSetting.Off, viewDistance = 450f,
                        detail = 0.5f, postEffects = false, antiAliasing = AntiAliasingSetting.Off, frameCap = FrameCap.Fps30 };
                case QualityPreset.Low:
                    return new SettingsData { preset = p, renderScale = 0.8f, shadows = ShadowSetting.Low, viewDistance = 550f,
                        detail = 0.7f, postEffects = true, antiAliasing = AntiAliasingSetting.FXAA, frameCap = FrameCap.Fps60 };
                case QualityPreset.High:
                    return new SettingsData { preset = p, renderScale = 1f, shadows = ShadowSetting.High, viewDistance = 1100f,
                        detail = 1.6f, postEffects = true, antiAliasing = AntiAliasingSetting.SMAA, frameCap = FrameCap.Fps60 };
                default:
                    return new SettingsData { preset = QualityPreset.Medium };
            }
        }

        public static void ApplyPreset(QualityPreset p)
        {
            bool fps = Current.showFps;
            Current = Preset(p);
            Current.showFps = fps;
            Commit();
        }

        /// <summary>Change individual options (switches the preset to Custom).</summary>
        public static void Modify(Action<SettingsData> change)
        {
            var before = JsonUtility.ToJson(Current);
            change(Current);
            if (JsonUtility.ToJson(Current) == before) return;
            var match = Preset(Current.preset);
            match.showFps = Current.showFps;
            if (Current.preset != QualityPreset.Custom && JsonUtility.ToJson(match) != JsonUtility.ToJson(Current))
                Current.preset = QualityPreset.Custom;
            Commit();
        }

        static void Commit()
        {
            Save();
            Apply();
        }

        static SettingsData Load()
        {
            try
            {
                var json = PlayerPrefs.GetString(Key, "");
                if (!string.IsNullOrEmpty(json)) return JsonUtility.FromJson<SettingsData>(json);
            }
            catch (Exception e) { Debug.LogWarning("Settings reset: " + e.Message); }
            return Preset(DefaultPresetForPlatform());
        }

        static QualityPreset DefaultPresetForPlatform() =>
            Application.platform == RuntimePlatform.WebGLPlayer ? QualityPreset.Low : QualityPreset.Medium;

        static void Save()
        {
            PlayerPrefs.SetString(Key, JsonUtility.ToJson(Current));
            PlayerPrefs.Save();
        }

        /// <summary>Push the current settings to the engine. Safe to call any time.</summary>
        public static void Apply()
        {
            var s = Current;

            // URP asset: clone once so runtime tweaks never modify the project asset.
            if (_runtimeAsset == null && GraphicsSettings.defaultRenderPipeline is UniversalRenderPipelineAsset src)
            {
                _runtimeAsset = UnityEngine.Object.Instantiate(src);
                _runtimeAsset.name = src.name + " (Runtime)";
                GraphicsSettings.defaultRenderPipeline = _runtimeAsset;
                QualitySettings.renderPipeline = _runtimeAsset;
            }
            if (_runtimeAsset != null)
            {
                // Retina screens have ~2.5x the pixels of 1080p. Render at most ~MaxRenderHeight lines
                // and let FSR upscale and sharpen: almost the same picture for a fraction of the GPU work.
                _runtimeAsset.renderScale = EffectiveRenderScale(s);
                _runtimeAsset.upscalingFilter = UpscalingFilterSelection.FSR;
                _runtimeAsset.fsrOverrideSharpness = true;
                _runtimeAsset.fsrSharpness = 0.82f;
                _lastScreenHeight = Screen.height;
                _runtimeAsset.shadowDistance = s.shadows == ShadowSetting.Off ? 0f
                    : s.shadows == ShadowSetting.Low ? 70f : 160f;
                _runtimeAsset.shadowCascadeCount = s.shadows == ShadowSetting.High ? 4 : 2;
                _runtimeAsset.mainLightShadowmapResolution = s.shadows == ShadowSetting.High ? 2048 : 1024;
                _runtimeAsset.msaaSampleCount = 1;
            }

            QualitySettings.lodBias = s.detail;
            switch (s.frameCap)
            {
                case FrameCap.Fps30: QualitySettings.vSyncCount = 0; Application.targetFrameRate = 30; break;
                case FrameCap.Fps60: QualitySettings.vSyncCount = 0; Application.targetFrameRate = 60; break;
                default: QualitySettings.vSyncCount = 1; Application.targetFrameRate = -1; break;
            }

            RenderSettings.fogStartDistance = s.viewDistance * 0.3f;   // keep mid-distance rock crisp
            RenderSettings.fogEndDistance = s.viewDistance * 0.97f;

            foreach (var cam in Camera.allCameras) ApplyToCamera(cam, s);

            foreach (var light in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None))
                if (light.type == LightType.Directional)
                    light.shadows = s.shadows == ShadowSetting.Off ? LightShadows.None
                        : s.shadows == ShadowSetting.Low ? LightShadows.Hard : LightShadows.Soft;

            foreach (var t in Terrain.activeTerrains)
            {
                t.heightmapPixelError = s.detail >= 1.5f ? 3f : s.detail >= 1f ? 5f : 8f;
                t.basemapDistance = 20000f;   // the desert shader handles distance itself
            }

            Changed?.Invoke(s);
        }

        public static void ApplyToCamera(Camera cam, SettingsData s)
        {
            cam.farClipPlane = s.viewDistance;
            var data = cam.GetUniversalAdditionalCameraData();
            if (data == null) return;
            data.renderPostProcessing = s.postEffects;
            data.antialiasing = s.antiAliasing == AntiAliasingSetting.SMAA ? AntialiasingMode.SubpixelMorphologicalAntiAliasing
                : s.antiAliasing == AntiAliasingSetting.FXAA ? AntialiasingMode.FastApproximateAntialiasing
                : AntialiasingMode.None;
        }

        public static string Describe(QualityPreset p) => p switch
        {
            QualityPreset.BatterySaver => "Battery Saver",
            _ => p.ToString(),
        };
    }
}
