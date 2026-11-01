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
        public float postExposure = 0.15f;
        public float contrast = 12f;
        public float saturation = 8f;
        public float temperature = 10f;
        public float bloomIntensity = 0.55f;
        public float bloomThreshold = 1.05f;
        public float vignette = 0.22f;

        [Header("Reflections")]
        public int reflectionResolution = 128;

        Volume _volume;
        ReflectionProbe _probe;

        void Awake()
        {
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

            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(bloomIntensity);
            bloom.threshold.Override(bloomThreshold);
            bloom.scatter.Override(0.7f);
            bloom.tint.Override(new Color(1f, 0.92f, 0.82f));
            bloom.highQualityFiltering.Override(false);

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
            VehicleEffects.GlobalDustScale = s.preset == QualityPreset.BatterySaver ? 0.5f : 1f;
        }
    }
}
