using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>Dust kicked up by the wheels, tinted by the surface being driven on, plus heavier spray
    /// (gravel, mud clods, snow, water) flung off the tread when the tyres spin, slide or churn soft ground.</summary>
    [RequireComponent(typeof(OffroadVehicle))]
    public class VehicleEffects : MonoBehaviour
    {
        public Material dustMaterial;
        [Range(0, 3)] public float dustAmount = 1f;
        public int maxParticles = 160;

        OffroadVehicle _vehicle;
        ParticleSystem _dust;
        ParticleSystem _spray;
        float[] _accum;
        float[] _sprayAccum;

        public static float GlobalDustScale = 1f;   // lowered by graphics presets

        void Start()
        {
            _vehicle = GetComponent<OffroadVehicle>();
            _accum = new float[_vehicle.wheels.Length];
            _sprayAccum = new float[_vehicle.wheels.Length];
            if (dustMaterial) { _dust = CreateDust(); _spray = CreateSpray(); }
        }

        ParticleSystem CreateDust()
        {
            var go = new GameObject("Dust");
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(1.6f, 2.8f);
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(1.0f, 2.2f);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = maxParticles;
            main.gravityModifier = -0.015f;

            var emission = ps.emission;
            emission.rateOverTime = 0f;
            var shape = ps.shape;
            shape.enabled = false;

            var size = ps.sizeOverLifetime;
            size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0f, 0.45f), new Keyframe(1f, 1.9f)));

            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(
                new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.12f), new GradientAlphaKey(0.5f, 0.5f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;

            var limit = ps.limitVelocityOverLifetime;
            limit.enabled = true;
            limit.dampen = 0.08f;
            limit.limit = 0.5f;

            var rot = ps.rotationOverLifetime;
            rot.enabled = true;
            rot.z = new ParticleSystem.MinMaxCurve(-0.4f, 0.4f);

            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = dustMaterial;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.sortingFudge = 10f;
            ps.Play();
            return ps;
        }

        ParticleSystem CreateSpray()
        {
            var go = new GameObject("Spray");
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 1.1f);
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.06f, 0.2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = maxParticles;
            main.gravityModifier = 1f;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            var shape = ps.shape;
            shape.enabled = false;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(
                new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 0.7f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = dustMaterial;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            ps.Play();
            return ps;
        }

        void EmitSpray(int i, OffroadVehicle.Wheel w, Vector3 vel, float dt)
        {
            var s = w.surface;
            float soft = Mathf.Max(s.mud, s.snow, Mathf.Min(1f, s.water * 2f), s.layers.y * 0.6f, s.layers.x * 0.4f);
            float spin = w.slip + (w.sliding ? 0.6f : 0f);
            float rolling = Mathf.Clamp01(Mathf.Abs(w.forwardSpeed) / 10f);
            float intensity = soft * (spin * 1.6f + rolling * 0.5f) * dustAmount * GlobalDustScale;
            _sprayAccum[i] += intensity * 60f * dt;
            if (_sprayAccum[i] < 1f) return;
            int n = Mathf.Min(8, (int)_sprayAccum[i]);
            _sprayAccum[i] -= n;
            // Thrown back off the top of the tread, opposite the direction of travel.
            Vector3 back = -transform.forward * Mathf.Sign(w.forwardSpeed == 0f ? 1f : w.forwardSpeed);
            Color c = s.water > 0.05f ? new Color(0.85f, 0.9f, 0.95f, 0.8f)
                    : s.snow > 0.3f ? new Color(0.95f, 0.97f, 1f, 0.95f)
                    : s.mud > 0.3f ? new Color(0.22f, 0.16f, 0.1f, 1f)
                    : s.dustColor * 0.75f;
            c.a = Mathf.Max(c.a, 0.85f);
            for (int k = 0; k < n; k++)
            {
                var p = new ParticleSystem.EmitParams
                {
                    position = w.contactPoint + transform.up * 0.15f + Random.insideUnitSphere * 0.15f,
                    velocity = vel * 0.6f + back * Random.Range(2f, 5f) * (0.5f + spin) + transform.up * Random.Range(1.5f, 4f)
                               + Random.insideUnitSphere * 1.2f,
                    startColor = c,
                    applyShapeToPosition = false,
                };
                _spray.Emit(p, 1);
            }
        }

        void Update()
        {
            if (_dust == null || Time.timeScale <= 0f) return;
            float dt = Time.deltaTime;
            Vector3 vel = _vehicle.Body.linearVelocity;
            float speed = vel.magnitude;
            var wheels = _vehicle.wheels;
            for (int i = 0; i < wheels.Length; i++)
            {
                var w = wheels[i];
                if (!w.grounded) { _accum[i] = 0f; _sprayAccum[i] = 0f; continue; }
                if (_spray) EmitSpray(i, w, vel, dt);
                float moving = Mathf.Clamp01((speed - 2.5f) / 14f);
                float intensity = w.surface.dust * (moving + w.slip * 1.5f + (w.sliding ? 1.2f : 0f)) * dustAmount * GlobalDustScale;
                _accum[i] += intensity * 22f * dt;
                while (_accum[i] >= 1f)
                {
                    _accum[i] -= 1f;
                    var c = w.surface.dustColor;
                    c.a = Mathf.Lerp(0.25f, 0.55f, Random.value);
                    var p = new ParticleSystem.EmitParams
                    {
                        position = w.contactPoint + transform.up * 0.25f - vel.normalized * 0.4f + Random.insideUnitSphere * 0.3f,
                        velocity = vel * 0.18f + Vector3.up * Random.Range(0.3f, 1.1f) + Random.insideUnitSphere * 0.8f,
                        startColor = c,
                        applyShapeToPosition = false,
                    };
                    _dust.Emit(p, 1);
                }
            }
        }
    }
}
