using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>Dust kicked up by the wheels, tinted by the surface being driven on.</summary>
    [RequireComponent(typeof(OffroadVehicle))]
    public class VehicleEffects : MonoBehaviour
    {
        public Material dustMaterial;
        [Range(0, 3)] public float dustAmount = 1f;
        public int maxParticles = 160;

        OffroadVehicle _vehicle;
        ParticleSystem _dust;
        float[] _accum;

        public static float GlobalDustScale = 1f;   // lowered by graphics presets

        void Start()
        {
            _vehicle = GetComponent<OffroadVehicle>();
            _accum = new float[_vehicle.wheels.Length];
            if (dustMaterial) _dust = CreateDust();
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
                if (!w.grounded) { _accum[i] = 0f; continue; }
                float moving = Mathf.Clamp01((speed - 2.5f) / 14f);
                float intensity = w.surface.dust * (moving + w.slip * 1.5f) * dustAmount * GlobalDustScale;
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
