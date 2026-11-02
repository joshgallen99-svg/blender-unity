using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>
    /// Procedural vehicle sound, synthesised on the audio thread so it needs no audio assets:
    /// a diesel-ish engine note following rpm and load, tyre scrub when sliding or spinning,
    /// suspension thumps on big hits, and chassis creak plus a warning tick as the vehicle nears tipping.
    /// </summary>
    [RequireComponent(typeof(OffroadVehicle))]
    public class VehicleAudio : MonoBehaviour
    {
        [Range(0, 1)] public float volume = 0.55f;

        OffroadVehicle _vehicle;
        AudioSource _source;
        int _rate;

        // Written on the main thread, read on the audio thread (single floats: torn reads are harmless).
        volatile float _rpm, _load, _scrub, _creak, _tip, _thump;

        double _phase, _creakPhase, _tickPhase;
        float _noiseLp, _scrubLp, _thumpEnv;
        uint _seed = 22222u;
        float[] _prevSpring;

        void Start()
        {
            _vehicle = GetComponent<OffroadVehicle>();
            _rate = AudioSettings.outputSampleRate;
            _prevSpring = new float[_vehicle.wheels.Length];
            _source = gameObject.AddComponent<AudioSource>();
            _source.playOnAwake = false;
            _source.loop = true;
            _source.spatialBlend = 0f;   // the player's own vehicle: always in the ears
            _source.Play();              // with no clip, OnAudioFilterRead supplies every sample
        }

        void Update()
        {
            if (_vehicle == null) return;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            _rpm = _vehicle.EngineRpm;
            _load = Mathf.Max(_vehicle.controls.throttle, _vehicle.IsReversing ? _vehicle.controls.brake : 0f);
            float scrub = 0f, thump = 0f;
            var wheels = _vehicle.wheels;
            for (int i = 0; i < wheels.Length; i++)
            {
                var w = wheels[i];
                if (w.grounded) scrub = Mathf.Max(scrub, w.slip + (w.sliding ? 0.5f : 0f));
                float v = Mathf.Abs(w.springLength - _prevSpring[i]) / dt;
                _prevSpring[i] = w.springLength;
                thump = Mathf.Max(thump, Mathf.Clamp01((v - 1.2f) / 3f));
            }
            _scrub = Mathf.Clamp01(scrub) * Mathf.Clamp01(_vehicle.Body.linearVelocity.magnitude / 4f);
            if (thump > _thump) _thump = thump;
            _tip = Mathf.Clamp01((_vehicle.TipRisk - 0.6f) / 0.35f);
            _creak = Mathf.Clamp01((_vehicle.TipRisk - 0.45f) / 0.4f) * Mathf.Clamp01(_vehicle.Body.angularVelocity.magnitude * 2f + 0.3f);
            bool paused = Time.timeScale <= 0f || AudioListener.pause;
            _source.volume = paused ? 0f : volume;
        }

        float Noise()
        {
            _seed ^= _seed << 13; _seed ^= _seed >> 17; _seed ^= _seed << 5;
            return (_seed & 0xFFFFFF) / (float)0x800000 - 1f;
        }

        void OnAudioFilterRead(float[] data, int channels)
        {
            if (_rate <= 0) return;
            float rpm = Mathf.Max(600f, _rpm), load = _load, scrub = _scrub, creak = _creak, tip = _tip;
            if (_thump > 0.05f) { _thumpEnv = Mathf.Max(_thumpEnv, _thump); _thump = 0f; }
            // Six-cylinder four-stroke: three firing pulses per revolution.
            double fire = rpm / 60.0 * 3.0;
            double inc = fire / _rate;
            float engineGain = 0.16f + 0.22f * load;
            for (int i = 0; i < data.Length; i += channels)
            {
                _phase += inc;
                if (_phase > 1.0) _phase -= 1.0;
                float ph = (float)_phase;
                // Firing pulse: a sharp decaying knock each cycle plus a sub harmonic for body.
                float pulse = Mathf.Exp(-ph * 9f) * 2f - 0.25f;
                float sub = Mathf.Sin((float)(_phase * Mathf.PI));
                float n = Noise();
                _noiseLp += (n - _noiseLp) * 0.08f;
                float engine = (pulse * 0.6f + sub * 0.3f + _noiseLp * (0.4f + load)) * engineGain;

                // Tyre scrub: band-limited noise.
                _scrubLp += (n - _scrubLp) * 0.3f;
                float tyres = (_scrubLp - _noiseLp) * scrub * 0.5f;

                // Suspension thump: low decaying sine.
                _thumpEnv *= 0.9993f;
                float thump = Mathf.Sin((float)(_creakPhase * 0.31)) * _thumpEnv * 0.5f;

                // Chassis creak: slow, rough, low-frequency grind.
                _creakPhase += 2.0 * Mathf.PI * (38.0 + 14.0 * Mathf.Sin((float)(_tickPhase * 0.7))) / _rate;
                float creakS = Mathf.Sin((float)_creakPhase) * (0.5f + 0.5f * _noiseLp * 6f) * creak * 0.18f;

                // Tip warning: a soft tick that speeds up as the tipping point nears.
                _tickPhase += (2.0 + 9.0 * tip) / _rate;
                if (_tickPhase > 1.0) _tickPhase -= 1.0;
                float tick = tip > 0.01f ? Mathf.Exp(-(float)_tickPhase * 60f) * Mathf.Sin((float)_tickPhase * 6000f) * tip * 0.12f : 0f;

                float s = Mathf.Clamp(engine + tyres + thump + creakS + tick, -1f, 1f);
                for (int c = 0; c < channels; c++) data[i + c] += s;
            }
        }
    }
}
