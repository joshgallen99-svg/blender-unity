using Offroad.Settings;
using Offroad.Vehicles;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Offroad.World
{
    /// <summary>
    /// Sets up the region's mood at runtime: colour grading / bloom (URP volume), a one-off
    /// reflection capture of the sky so metal and glass reflect it, and ties both to the
    /// graphics settings.
    /// </summary>
    public class Atmosphere : MonoBehaviour
    {
        [Header("Grading")]
        public float postExposure = 0.08f;
        public float contrast = 15f;
        public float saturation = 5f;
        public float temperature = 2f;
        public float bloomIntensity = 0.65f;
        public float bloomThreshold = 0.95f;
        public float vignette = 0.2f;
        [Tooltip("Cool shadows / warm highlights: complementary contrast that makes the red rock pop.")]
        public Color splitShadows = new Color(0.47f, 0.50f, 0.55f);
        public Color splitHighlights = new Color(0.54f, 0.50f, 0.46f);

        [Header("Aerial perspective")]
        [Tooltip("Colour the distance haze takes on when looking toward the sun (matches the sky's sun glow).")]
        public Color sunFogColor = new Color(1f, 0.74f, 0.5f);
        [Range(0, 1)] public float sunFogStrength = 0.7f;

        [Header("Light rays")]
        public Color shaftTint = new Color(1f, 0.86f, 0.66f);
        [Range(0, 2)] public float shaftIntensity = 0.55f;
        [Tooltip("Only pixels brighter than this (HDR) around the sun make rays.")]
        public float shaftThreshold = 1.1f;

        [Header("Reflections")]
        public int reflectionResolution = 128;

        Volume _volume;
        ReflectionProbe _probe;

        static readonly int SunFogId = Shader.PropertyToID("_OffroadSunFogColor");

        void Awake()
        {
            Shader.SetGlobalVector(SunFogId, new Vector4(sunFogColor.r, sunFogColor.g, sunFogColor.b, sunFogStrength));
            Offroad.Rendering.SunShafts.Tint = shaftTint;
            Offroad.Rendering.SunShafts.Intensity = shaftIntensity;
            Offroad.Rendering.SunShafts.Threshold = shaftThreshold;
            BuildVolume();
            BuildReflectionProbe();
        }

        void OnEnable() => GameSettings.Changed += OnSettingsChanged;
        void OnDisable() => GameSettings.Changed -= OnSettingsChanged;

        void Start()
        {
            OnSettingsChanged(GameSettings.Current);
            if (_probe) _probe.RenderProbe();
        }

        void BuildVolume()
        {
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            profile.name = "Atmosphere (runtime)";

            var tone = profile.Add<Tonemapping>(true);
            tone.mode.Override(TonemappingMode.ACES);

            var color = profile.Add<ColorAdjustments>(true);
            color.postExposure.Override(postExposure);
            color.contrast.Override(contrast);
            color.saturation.Override(saturation);
            color.colorFilter.Override(Color.white);
            color.hueShift.Override(0f);

            var wb = profile.Add<WhiteBalance>(true);
            wb.temperature.Override(temperature);
            wb.tint.Override(0f);

            var split = profile.Add<SplitToning>(true);
            split.shadows.Override(splitShadows);
            split.highlights.Override(splitHighlights);
            split.balance.Override(-10f);

            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(bloomIntensity);
            bloom.threshold.Override(bloomThreshold);
            bloom.scatter.Override(0.72f);
            bloom.tint.Override(new Color(1f, 0.92f, 0.82f));
            bloom.highQualityFiltering.Override(false);
            bloom.downscale.Override(BloomDownscaleMode.Quarter);   // a soft glow looks the same from quarter res

            var vig = profile.Add<Vignette>(true);
            vig.intensity.Override(vignette);
            vig.smoothness.Override(0.45f);
            vig.color.Override(Color.black);

            var go = new GameObject("Post Processing Volume");
            go.transform.SetParent(transform, false);
            _volume = go.AddComponent<Volume>();
            _volume.isGlobal = true;
            _volume.priority = 1;
            _volume.sharedProfile = profile;
        }

        void BuildReflectionProbe()
        {
            var go = new GameObject("Sky Reflection");
            go.transform.SetParent(transform, false);
            go.transform.position = new Vector3(0f, 200f, 0f);
            _probe = go.AddComponent<ReflectionProbe>();
            _probe.mode = ReflectionProbeMode.Realtime;
            _probe.refreshMode = ReflectionProbeRefreshMode.ViaScripting;
            _probe.timeSlicingMode = ReflectionProbeTimeSlicingMode.AllFacesAtOnce;
            _probe.resolution = reflectionResolution;
            _probe.size = new Vector3(10000f, 10000f, 10000f);
            _probe.cullingMask = 0;                    // sky only: cheap and stable
            _probe.clearFlags = ReflectionProbeClearFlags.Skybox;
            _probe.importance = 0;
            _probe.hdr = true;
        }

        void OnSettingsChanged(SettingsData s)
        {
            if (_volume) _volume.enabled = s.postEffects;
            Offroad.Rendering.SunShafts.Enabled = s.postEffects && s.preset != QualityPreset.BatterySaver;
            VehicleEffects.GlobalDustScale = s.preset == QualityPreset.BatterySaver ? 0.5f : 1f;
        }
    }
}
