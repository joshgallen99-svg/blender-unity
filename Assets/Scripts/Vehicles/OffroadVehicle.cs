using System;
using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>Driver commands for a vehicle. Set by the player controller, AI or tests.</summary>
    [Serializable]
    public struct VehicleControls
    {
        [Range(0, 1)] public float throttle;
        [Range(0, 1)] public float brake;      // brakes when moving forward, reverses when stopped
        [Range(-1, 1)] public float steer;
        public bool handbrake;
    }

    /// <summary>
    /// Arcade-leaning off-road vehicle physics.
    ///
    /// Each wheel is a sphere cast along the suspension axis (so tyres roll up and over rocks
    /// instead of snagging), with a spring/damper tuned automatically from the vehicle mass,
    /// a friction-circle tyre model that cancels sideways slip, a simple power-limited 4x4
    /// drivetrain, anti-roll bars and a few stability helpers (low centre of mass, air control,
    /// auto-righting).
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    [DefaultExecutionOrder(-50)]
    public class OffroadVehicle : MonoBehaviour
    {
        [Serializable]
        public class Wheel
        {
            public string name = "Wheel";
            public Vector3 restPosition;   // wheel centre at rest, vehicle-local
            public bool front;
            public bool left;
            public Transform visual;       // optional: moved and spun every frame

            [NonSerialized] public bool grounded;
            [NonSerialized] public float springLength;
            [NonSerialized] public float prevSpringLength;
            [NonSerialized] public float load;
            [NonSerialized] public float slip;
            [NonSerialized] public float spinSpeed;      // rad/s
            [NonSerialized] public float spinAngle;      // degrees
            [NonSerialized] public float visualSpring;
            [NonSerialized] public float forwardSpeed;
            [NonSerialized] public Vector3 contactPoint;
            [NonSerialized] public Vector3 contactNormal;
            [NonSerialized] public Collider contactCollider;
            [NonSerialized] public SurfaceInfo surface;
            [NonSerialized] public float sink;           // how far the tyre has sunk into soft ground (m)
            [NonSerialized] public float quickSink;      // the quicksand part of it, which builds up over time
            [NonSerialized] public float washPhase;      // distance rolled over corrugations, in wavelengths
            [NonSerialized] public bool sliding;         // broken loose: on sliding grip until it hooks up again
        }

        [Header("Wheels")]
        public Wheel[] wheels = Array.Empty<Wheel>();
        public float wheelRadius = 0.43f;
        [Tooltip("Tread width (m): how wide a track the tyres press into soft ground.")]
        public float tireWidth = 0.32f;

        [Header("Suspension")]
        [Tooltip("Total wheel travel in metres.")]
        public float suspensionTravel = 0.5f;
        [Tooltip("Fraction of travel used up when standing still.")]
        [Range(0.2f, 0.7f)] public float restCompression = 0.4f;
        [Range(0.05f, 1.5f)] public float bumpDamping = 0.35f;     // damping ratios (1 = critical)
        [Range(0.05f, 1.5f)] public float reboundDamping = 0.55f;
        [Tooltip("Sway-bar stiffness as a multiple of the spring rate. Disconnected in low range so the axles can flex.")]
        public float antiRoll = 0.3f;

        [Header("Engine")]
        [Tooltip("Peak engine torque (N m). The curve rises from idle, holds through the mid range and falls toward redline.")]
        public float peakTorque = 620f;
        public float idleRpm = 850f;
        public float redlineRpm = 4800f;
        [Tooltip("Engine braking at redline, as a fraction of peak torque.")]
        public float engineBraking = 0.18f;

        [Header("Gearbox")]
        public float[] gearRatios = { 4.06f, 2.39f, 1.52f, 1.0f, 0.79f };
        public float reverseRatio = 3.8f;
        public float finalDrive = 4.1f;
        [Tooltip("Transfer-case low range, engaged in manual 1st: the crawl gear.")]
        public float lowRangeRatio = 2.72f;
        public float drivetrainEfficiency = 0.85f;
        public float shiftTime = 0.15f;
        public float autoUpshiftRpm = 3900f;
        public float autoDownshiftRpm = 1700f;
        [Tooltip("Manual gearbox: the player picks gears; 1st is low range.")]
        public bool manual;
        [Tooltip("Aerodynamic drag area (Cd x frontal area, m^2).")]
        public float dragArea = 1.7f;

        [Header("Drivetrain")]
        [Tooltip("Garage engine upgrades scale the torque by this.")]
        public float torqueScale = 1f;
        public float reverseTopSpeed = 12f;
        public float brakeForce = 9000f;         // per wheel
        public float rollingResistance = 6f;     // N per m/s per wheel (plus aero drag on the body)
        [Tooltip("Seconds the brake must be held at a standstill before reverse engages.")]
        public float reverseDelay = 0.3f;

        [Header("Tyres")]
        public TireProfile tire = TireProfile.Neutral;
        public float tireGrip = 1.05f;           // friction coefficient on a neutral surface
        [Range(0, 1)] public float lateralStiffness = 0.82f;
        [Range(0, 1)] public float handbrakeRearGrip = 0.35f;
        [Tooltip("Grip once a tyre breaks loose, as a fraction of peak: below 1 lets a slide carry on into a drift.")]
        [Range(0.5f, 1f)] public float slidingGrip = 0.8f;
        [Tooltip("How much grip per newton falls as load rises (0 = none). Weight transfer then costs grip, as on real tyres.")]
        [Range(0f, 0.4f)] public float loadSensitivity = 0.15f;
        [Tooltip("Height above the contact patch where tyre forces act (lower = more body roll).")]
        public float tireForceHeight = 0.12f;

        [Header("Steering")]
        public float maxSteerAngle = 34f;
        public float highSpeedSteerAngle = 11f;
        public float steerSpeed = 3.2f;
        public float steerReturnSpeed = 5f;

        [Header("Soft ground")]
        [Tooltip("How far tyres settle into wet mud (m).")]
        public float mudSinkDepth = 0.11f;
        [Tooltip("How far wheels sink into deep snow (m).")]
        public float snowSinkDepth = 0.17f;
        [Tooltip("How fast quicksand swallows a slow or stopped vehicle (m/s).")]
        public float quicksandSinkRate = 0.09f;
        [Tooltip("Below this speed (m/s) quicksand pulls the vehicle down; above it the tyres climb back out.")]
        public float quicksandEscapeSpeed = 3.5f;
        public float quicksandMaxSink = 0.85f;
        [Tooltip("Height of washboard corrugations (m) and their spacing (m).")]
        public float washboardHeight = 0.014f;
        public float washboardSpacing = 0.75f;
        [Tooltip("Water deeper than this (m) floods the air intake: the engine barely pulls.")]
        public float fordingDepth = 0.85f;

        [Header("Stability")]
        public Vector3 centerOfMass = new Vector3(0f, 0.72f, 0.05f);
        public float downforce = 0.4f;
        public float airControl = 0.6f;          // rad/s^2
        [Tooltip("Seconds between recoveries (R).")]
        public float recoverCooldown = 3f;

        public VehicleControls controls;
        public ISurfaceProvider surfaceProvider;

        public Rigidbody Body { get; private set; }
        public float ForwardSpeed { get; private set; }
        public float SteerAngle { get; private set; }
        public int GroundedWheels { get; private set; }
        public bool IsReversing { get; private set; }
        public float SpringRate { get; private set; }
        /// <summary>Deepest quicksand sink over all wheels (m): the HUD warns, recovery uses it.</summary>
        public float QuicksandSink { get; private set; }
        /// <summary>0..1 how hard the vehicle is being shaken by washboard right now.</summary>
        public float Rattle { get; private set; }
        /// <summary>Deepest water under any wheel (m).</summary>
        public float WaterDepth { get; private set; }
        public bool Flooded => WaterDepth > fordingDepth;
        /// <summary>Current gear: -1 reverse, 0 neutral (shifting), 1.. forward.</summary>
        public int Gear { get; private set; } = 1;
        public float EngineRpm { get; private set; }
        /// <summary>Transfer case in low range (manual 1st): crawl gearing, sway bars disconnected.</summary>
        public bool LowRange => manual && Gear == 1;
        /// <summary>0..1 how close the vehicle is to tipping over sideways or end-over-end.</summary>
        public float TipRisk { get; private set; }
        public int GearCount => gearRatios.Length;

        const float CastLift = 0.3f;              // start casts above the travel so close ground is not missed
        static readonly RaycastHit[] Hits = new RaycastHit[16];

        float _steerInput;
        float _brakeHeldAtStop;
        float _shiftTimer;
        int _manualGear = 1;
        float _lastRecover = -100f;
        Vector3 _spawnPosition;
        Quaternion _spawnRotation;
        Vector3 _safePosition;
        Quaternion _safeRotation;
        bool _hasSafe;
        float _safeTimer;

        void Awake()
        {
            Body = GetComponent<Rigidbody>();
            Body.centerOfMass = centerOfMass;
            Body.interpolation = RigidbodyInterpolation.Interpolate;
            _spawnPosition = transform.position;
            _spawnRotation = transform.rotation;
            foreach (var w in wheels)
            {
                w.springLength = w.prevSpringLength = w.visualSpring = suspensionTravel * (1f - restCompression);
                w.surface = SurfaceInfo.Default;
            }
            if (surfaceProvider == null) surfaceProvider = FindSurfaceProvider();
        }

        static ISurfaceProvider FindSurfaceProvider()
        {
            foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (mb is ISurfaceProvider sp) return sp;
            return null;
        }

        /// <summary>Wheel-centre position at the top of the suspension travel, vehicle-local.</summary>
        public Vector3 AnchorLocal(Wheel w) => w.restPosition + Vector3.up * (suspensionTravel * (1f - restCompression));

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            float mass = Body.mass;
            float g = -Physics.gravity.y;
            int count = Mathf.Max(1, wheels.Length);
            float cornerMass = mass / count;
            SpringRate = cornerMass * g / (suspensionTravel * restCompression);
            Vector3 up = transform.up;
            ForwardSpeed = Vector3.Dot(Body.linearVelocity, transform.forward);

            UpdateSteering(dt);

            // ---- Suspension pass.
            GroundedWheels = 0;
            foreach (var w in wheels)
            {
                CastWheel(w, up);
                if (w.grounded) GroundedWheels++;
            }

            float bumpC = 2f * bumpDamping * Mathf.Sqrt(SpringRate * cornerMass);
            float reboundC = 2f * reboundDamping * Mathf.Sqrt(SpringRate * cornerMass);
            foreach (var w in wheels)
            {
                if (!w.grounded) { w.load = 0; w.prevSpringLength = w.springLength; continue; }
                float compression = suspensionTravel - w.springLength;
                float velocity = (w.prevSpringLength - w.springLength) / dt;    // + when compressing
                float force = SpringRate * compression + (velocity > 0 ? bumpC : reboundC) * velocity;
                if (w.springLength <= 0.001f) force += SpringRate * 4f * Mathf.Max(0, -velocity * dt); // bump stop
                force = Mathf.Clamp(force, 0f, mass * g * 1.6f);
                w.load = force;
                w.prevSpringLength = w.springLength;
                Body.AddForceAtPosition(up * force, WheelCenterWorld(w));
            }

            if (!LowRange) ApplyAntiRoll(up);

            // ---- Drivetrain request: pedals pick drive / brake / reverse, the gearbox and engine
            // curve turn throttle into wheel force.
            float brakeAmount = 0f, throttle = 0f;
            IsReversing = false;
            if (controls.throttle > 0.01f)
            {
                if (ForwardSpeed < -0.8f) brakeAmount = controls.throttle;
                else throttle = controls.throttle;
            }
            if (controls.brake > 0.01f)
            {
                if (ForwardSpeed > 0.8f)
                {
                    brakeAmount = Mathf.Max(brakeAmount, controls.brake);
                    _brakeHeldAtStop = 0f;
                }
                else if (controls.throttle <= 0.01f)
                {
                    _brakeHeldAtStop += dt;
                    if (_brakeHeldAtStop >= reverseDelay || ForwardSpeed < -0.3f)
                    {
                        throttle = controls.brake;
                        IsReversing = true;
                    }
                    else brakeAmount = Mathf.Max(brakeAmount, controls.brake);
                }
            }
            else _brakeHeldAtStop = 0f;
            bool idle = controls.throttle <= 0.01f && controls.brake <= 0.01f;
            float driveTotal = Drivetrain(throttle, dt);
            if (Flooded) driveTotal *= 0.2f;                 // water in the intake: barely any power

            // ---- Tyre forces.
            int drivenGrounded = 0;
            foreach (var w in wheels) if (w.grounded) drivenGrounded++;
            float massShare = mass / Mathf.Max(1, GroundedWheels);

            foreach (var w in wheels)
            {
                if (!w.grounded) { w.slip = 0; continue; }
                Vector3 n = w.contactNormal;
                Vector3 heading = w.front ? Quaternion.AngleAxis(SteerAngle, up) * transform.forward : transform.forward;
                Vector3 fwd = Vector3.ProjectOnPlane(heading, n).normalized;
                Vector3 right = Vector3.Cross(n, fwd);
                Vector3 pv = Body.GetPointVelocity(w.contactPoint);
                float vLong = Vector3.Dot(pv, fwd);
                float vLat = Vector3.Dot(pv, right);
                // Gravity pulling along / across the tyre this step (so holds and grip cancel it too).
                float gLong = Vector3.Dot(Physics.gravity, fwd);
                float gLat = Vector3.Dot(Physics.gravity, right);
                w.forwardSpeed = vLong;

                float tireFit = tire.GripOn(w.surface);
                float grip = tireGrip * w.surface.grip * tireFit;
                bool handbraked = controls.handbrake && !w.front;

                float fLong = drivenGrounded > 0 ? driveTotal / drivenGrounded * w.surface.traction * Mathf.Min(1.15f, tireFit) : 0f;
                float stopForce = -(vLong / dt + gLong) * massShare;
                if (brakeAmount > 0f || handbraked)
                {
                    float b = handbraked ? 1f : brakeAmount;
                    fLong += Mathf.Clamp(stopForce, -brakeForce * b, brakeForce * b);
                }
                else if (idle && Mathf.Abs(ForwardSpeed) < 1.2f)
                {
                    fLong += stopForce;                        // hold on slopes when no pedal is pressed
                }
                fLong -= vLong * (rollingResistance * tire.rolling + w.surface.drag * 220f * tire.DragOn(w.surface)
                                  + w.sink * 1800f                         // ploughing through soft ground
                                  + Mathf.Min(w.surface.water, 1.2f) * 700f);   // wading
                if (w.surface.washboard > 0.01f)
                    grip *= 1f - 0.22f * w.surface.washboard * Mathf.Clamp01(Mathf.Abs(vLong) / 12f);

                float latGrip = lateralStiffness * (handbraked ? handbrakeRearGrip : 1f);
                float fLat = -(vLat / dt + gLat) * massShare * latGrip;

                // Load sensitivity: a tyre carrying more than its share grips proportionally less, so
                // weight transfer in a corner costs total grip. Once broken loose the tyre runs on
                // sliding grip until the demand falls back well inside it: that is what holds a drift.
                float nominal = mass * g / count;
                float muLoad = Mathf.Clamp(1f - loadSensitivity * (w.load / nominal - 1f), 0.6f, 1.25f);
                float limit = grip * muLoad * w.load * (w.sliding ? slidingGrip : 1f);
                Vector2 f = new Vector2(fLong, fLat);
                float mag = f.magnitude;
                w.slip = 0f;
                if (mag > limit && mag > 1e-3f)
                {
                    w.slip = Mathf.Clamp01((mag - limit) / Mathf.Max(limit, 1f));
                    f *= limit / mag;
                    if (mag > limit * 1.08f && Mathf.Abs(vLat) > 1.2f) w.sliding = true;
                }
                else if (mag < limit * 0.85f || Mathf.Abs(vLat) < 0.6f) w.sliding = false;

                Vector3 at = w.contactPoint + up * tireForceHeight;
                Body.AddForceAtPosition(fwd * f.x + right * f.y, at);
            }

            // ---- Aero and a touch of air control. No auto-righting: a rollover is yours to recover.
            Vector3 vel = Body.linearVelocity;
            Body.AddForce(-0.5f * 1.2f * dragArea * vel.magnitude * vel);
            if (GroundedWheels >= 2)
                Body.AddForce(-up * downforce * ForwardSpeed * ForwardSpeed);
            if (GroundedWheels == 0)
            {
                Vector3 torque = transform.right * (controls.throttle - controls.brake) * airControl
                                 - transform.forward * controls.steer * airControl;
                Body.AddTorque(torque, ForceMode.Acceleration);
            }
            if (transform.position.y < -100f) Respawn();
            UpdateTipRisk();
            TrackSoftGround(dt);
        }

        /// <summary>Static stability: how far the centre of mass has leaned toward the line between the
        /// downhill wheels. 1 = over the tipping point.</summary>
        void UpdateTipRisk()
        {
            float halfTrack = 0f, halfBase = 0f;
            foreach (var w in wheels)
            {
                halfTrack = Mathf.Max(halfTrack, Mathf.Abs(w.restPosition.x));
                halfBase = Mathf.Max(halfBase, Mathf.Abs(w.restPosition.z));
            }
            float h = Mathf.Max(0.2f, centerOfMass.y);
            // Lean angles relative to gravity, against the static tipping angles atan(halfTrack / h).
            Vector3 gLocal = transform.InverseTransformDirection(Vector3.down);
            float roll = Mathf.Atan2(Mathf.Abs(gLocal.x), -gLocal.y);
            float pitch = Mathf.Atan2(Mathf.Abs(gLocal.z), -gLocal.y);
            if (gLocal.y >= 0f) { TipRisk = 1f; return; }
            float rollRisk = roll / Mathf.Atan2(halfTrack, h);
            float pitchRisk = pitch / Mathf.Atan2(halfBase, h);
            int lifted = 0;
            foreach (var w in wheels) if (!w.grounded) lifted++;
            TipRisk = Mathf.Clamp01(Mathf.Max(rollRisk, pitchRisk) + (GroundedWheels > 0 ? lifted * 0.08f : 0f));
        }

        /// <summary>Manual gearbox: shift up / down (1st is low range). Ignored in automatic.</summary>
        public void ShiftManual(int delta)
        {
            if (!manual) return;
            _manualGear = Mathf.Clamp(_manualGear + delta, 1, gearRatios.Length);
            _shiftTimer = shiftTime;
        }

        public void SetManual(bool on)
        {
            if (manual == on) return;
            manual = on;
            // Pick up in a sensible gear: in manual from the gear auto was using (never straight into low range at speed).
            _manualGear = Mathf.Clamp(Gear < 1 ? 1 : Gear, ForwardSpeed > 6f ? 2 : 1, gearRatios.Length);
        }

        float TorqueCurve(float rpm)
        {
            // Turbo-diesel-like: strong from just off idle, flat mid range, tailing off to redline.
            float r = Mathf.Clamp(rpm, idleRpm, redlineRpm);
            if (r < 1900f) return Mathf.Lerp(0.62f, 1f, Mathf.InverseLerp(idleRpm, 1900f, r));
            if (r < 3500f) return 1f;
            return Mathf.Lerp(1f, 0.72f, Mathf.InverseLerp(3500f, redlineRpm, r));
        }

        /// <summary>Picks the gear (auto), works out engine rpm from the driven wheels and returns the total
        /// longitudinal force at the tyres (newtons, + forward).</summary>
        float Drivetrain(float throttle, float dt)
        {
            float wheelSpeed = 0f;
            int driven = 0;
            foreach (var w in wheels) { wheelSpeed += Mathf.Abs(w.grounded ? w.forwardSpeed : w.spinSpeed * wheelRadius); driven++; }
            wheelSpeed /= Mathf.Max(1, driven);
            float wheelRpm = wheelSpeed / wheelRadius * 60f / (2f * Mathf.PI);

            int gear;
            if (IsReversing) gear = -1;
            else if (manual) gear = _manualGear;
            else
            {
                gear = Mathf.Clamp(Gear < 1 ? 1 : Gear, 1, gearRatios.Length);
                float rpmNow = wheelRpm * RatioFor(gear);
                if (_shiftTimer <= 0f)
                {
                    if (rpmNow > autoUpshiftRpm && gear < gearRatios.Length && throttle > 0.05f) { gear++; _shiftTimer = shiftTime; }
                    else if (gear > 1 && wheelRpm * RatioFor(gear - 1) < autoUpshiftRpm * 0.85f && rpmNow < autoDownshiftRpm) { gear--; _shiftTimer = shiftTime * 0.6f; }
                }
            }
            if (gear != Gear && Gear != 0 && gear > 0 && Gear > 0 && _shiftTimer <= 0f) _shiftTimer = shiftTime;
            Gear = gear;
            _shiftTimer -= dt;

            float ratio = RatioFor(gear);
            // Clutch / converter slip below the gear's stall speed keeps the engine above idle.
            float rpm = Mathf.Max(idleRpm + throttle * 900f * Mathf.Clamp01(1f - wheelRpm * ratio / 1800f), wheelRpm * ratio);
            EngineRpm = Mathf.Lerp(EngineRpm, Mathf.Min(rpm, redlineRpm * 1.02f), 1f - Mathf.Exp(-12f * dt));
            if (_shiftTimer > 0f) return 0f;

            float wheelTorque;
            if (throttle > 0.01f && rpm < redlineRpm)
                wheelTorque = throttle * peakTorque * torqueScale * TorqueCurve(rpm) * ratio * drivetrainEfficiency;
            else if (throttle <= 0.01f && wheelSpeed > 0.3f)
                wheelTorque = -engineBraking * peakTorque * (rpm / redlineRpm) * ratio;   // engine braking: hill descent in low range
            else wheelTorque = 0f;
            float force = wheelTorque / wheelRadius;
            if (gear < 0)
            {
                if (-ForwardSpeed > reverseTopSpeed) force = 0f;
                return throttle > 0.01f ? -force : (ForwardSpeed < 0f ? -force : force);
            }
            return ForwardSpeed < 0f && force < 0f ? -force : force;
        }

        float RatioFor(int gear)
        {
            if (gear < 0) return reverseRatio * finalDrive;
            float r = gearRatios[Mathf.Clamp(gear - 1, 0, gearRatios.Length - 1)] * finalDrive;
            return manual && gear == 1 ? r * lowRangeRatio : r;
        }

        void TrackSoftGround(float dt)
        {
            float deepest = 0f, rattle = 0f, hazard = 0f, water = 0f;
            foreach (var w in wheels)
            {
                deepest = Mathf.Max(deepest, w.quickSink);
                if (!w.grounded) continue;
                water = Mathf.Max(water, w.surface.water);
                rattle = Mathf.Max(rattle, w.surface.washboard * Mathf.Clamp01(Mathf.Abs(ForwardSpeed) / 10f));
                hazard = Mathf.Max(hazard, w.surface.quicksand + w.surface.mud * 0.5f);
            }
            QuicksandSink = deepest;
            Rattle = rattle;
            WaterDepth = water;
            // The body pushing through water: drag on the whole vehicle, growing with depth.
            if (water > 0.25f)
            {
                Vector3 v = Body.linearVelocity;
                Body.AddForce(-v * v.magnitude * Mathf.Min(water, 1.5f) * 140f);
            }

            // Remember the last spot on firm ground, for recovery.
            _safeTimer += dt;
            if (_safeTimer > 1f && GroundedWheels >= 3 && hazard < 0.05f && deepest < 0.01f && water < 0.05f &&
                Vector3.Dot(transform.up, Vector3.up) > 0.85f)
            {
                _safeTimer = 0f;
                _safePosition = transform.position;
                _safeRotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(transform.forward, Vector3.up), Vector3.up);
                _hasSafe = true;
            }
        }

        void UpdateSteering(float dt)
        {
            float target = Mathf.Clamp(controls.steer, -1f, 1f);
            float rate = Mathf.Abs(target) > Mathf.Abs(_steerInput) && Mathf.Sign(target) == Mathf.Sign(_steerInput)
                ? steerSpeed : steerReturnSpeed;
            _steerInput = Mathf.MoveTowards(_steerInput, target, rate * dt);
            float speedFactor = Mathf.Clamp01(Mathf.Abs(ForwardSpeed) / 28f);
            SteerAngle = _steerInput * Mathf.Lerp(maxSteerAngle, highSpeedSteerAngle, speedFactor);
        }

        void CastWheel(Wheel w, Vector3 up)
        {
            Vector3 anchor = transform.TransformPoint(AnchorLocal(w));
            Vector3 origin = anchor + up * CastLift;
            float maxDist = CastLift + suspensionTravel;
            int n = Physics.SphereCastNonAlloc(origin, wheelRadius, -up, Hits, maxDist,
                Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);

            float best = float.MaxValue;
            int bestIdx = -1;
            for (int i = 0; i < n; i++)
            {
                var h = Hits[i];
                if (h.collider.attachedRigidbody == Body) continue;
                float d = h.distance;
                if (d <= 0f && h.point == Vector3.zero) d = 0f; // started overlapping: treat as fully compressed
                if (d < best) { best = d; bestIdx = i; }
            }

            if (bestIdx < 0)
            {
                w.grounded = false;
                w.springLength = suspensionTravel;
                w.contactCollider = null;
                return;
            }

            var hit = Hits[bestIdx];
            w.grounded = true;
            // Soft ground: the tyre sits below the collider surface by its sink depth; washboard
            // corrugations push it up and down as it rolls.
            float corrugation = w.surface.washboard > 0.01f
                ? washboardHeight * w.surface.washboard * (0.5f + 0.5f * Mathf.Sin(w.washPhase * 2f * Mathf.PI))
                : 0f;
            w.springLength = Mathf.Clamp(best - CastLift + w.sink - corrugation, 0f, suspensionTravel);
            Vector3 center = anchor - up * w.springLength;
            bool overlapped = hit.point == Vector3.zero && hit.distance <= 0f;
            w.contactPoint = overlapped ? center - up * wheelRadius : hit.point;
            w.contactNormal = overlapped || Vector3.Dot(hit.normal, up) < 0.2f ? up : hit.normal;
            if (w.contactCollider != hit.collider || surfaceProvider != null)
                w.surface = surfaceProvider != null ? surfaceProvider.GetSurface(w.contactPoint, hit.collider) : SurfaceInfo.Default;
            w.contactCollider = hit.collider;
            UpdateSink(w, Time.fixedDeltaTime);
        }

        void UpdateSink(Wheel w, float dt)
        {
            float speed = Mathf.Abs(ForwardSpeed);
            if (w.surface.quicksand > 0.05f)
            {
                // Slow or stopped: sink. Fast: the tyres climb back out.
                float pull = speed < quicksandEscapeSpeed
                    ? quicksandSinkRate * (1f - speed / quicksandEscapeSpeed)
                    : -quicksandSinkRate * 2.5f * Mathf.Min(1f, (speed - quicksandEscapeSpeed) / 3f);
                w.quickSink = Mathf.Clamp(w.quickSink + pull * w.surface.quicksand * dt, 0f, quicksandMaxSink);
            }
            else w.quickSink = Mathf.MoveTowards(w.quickSink, 0f, 0.6f * dt);
            float target = w.surface.sink + w.surface.mud * mudSinkDepth + w.surface.snow * snowSinkDepth + w.quickSink;
            w.sink = Mathf.MoveTowards(w.sink, target, 0.5f * dt);
            if (w.surface.washboard > 0.01f) w.washPhase += Mathf.Abs(w.forwardSpeed) * dt / washboardSpacing;
        }

        Vector3 WheelCenterWorld(Wheel w) =>
            transform.TransformPoint(AnchorLocal(w)) - transform.up * w.springLength;

        void ApplyAntiRoll(Vector3 up)
        {
            float k = SpringRate * antiRoll;
            for (int i = 0; i < wheels.Length; i++)
            {
                var a = wheels[i];
                if (!a.left) continue;
                for (int j = 0; j < wheels.Length; j++)
                {
                    var b = wheels[j];
                    if (b.left || b.front != a.front) continue;
                    float ca = a.grounded ? suspensionTravel - a.springLength : 0f;
                    float cb = b.grounded ? suspensionTravel - b.springLength : 0f;
                    // The more-compressed side gets extra lift, the other side less: resists body roll.
                    float f = (ca - cb) * k;
                    if (a.grounded) Body.AddForceAtPosition(up * f, WheelCenterWorld(a));
                    if (b.grounded) Body.AddForceAtPosition(-up * f, WheelCenterWorld(b));
                }
            }
        }

        /// <summary>Why the last <see cref="ResetUpright"/> was refused, for the HUD; null if it went ahead.</summary>
        public string RecoverRefusal { get; private set; }
        public float RecoverRefusedAt { get; private set; } = -100f;

        /// <summary>Recovery (R): put the vehicle back on its wheels on the ground below, keeping its heading.
        /// If it is stuck in quicksand, deep mud or water, tow it back to the last spot on firm ground instead.
        /// Refused while on cooldown, or while it is upright, on its wheels and moving: it is not stuck.</summary>
        public bool ResetUpright()
        {
            RecoverRefusal = null;
            if (Time.time - _lastRecover < recoverCooldown) { RecoverRefusal = "Recovery cooling down"; RecoverRefusedAt = Time.time; return false; }
            bool stuck = QuicksandSink > 0.2f;
            foreach (var w in wheels) stuck |= w.sink > 0.2f;
            stuck |= Flooded;
            bool upright = Vector3.Dot(transform.up, Vector3.up) > 0.7f && GroundedWheels >= 3;
            if (!stuck && upright && Body.linearVelocity.magnitude > 1.5f) { RecoverRefusal = "Stop first to recover"; RecoverRefusedAt = Time.time; return false; }
            _lastRecover = Time.time;

            if (stuck && _hasSafe)
            {
                Teleport(GroundBelow(_safePosition), _safeRotation);
                return true;
            }
            Vector3 fwd = Vector3.ProjectOnPlane(transform.forward, Vector3.up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.ProjectOnPlane(transform.up, Vector3.up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            Teleport(GroundBelow(transform.position), Quaternion.LookRotation(fwd, Vector3.up));
            return true;
        }

        /// <summary>The ground surface under a point (ignoring this vehicle), plus a small drop clearance.</summary>
        Vector3 GroundBelow(Vector3 p)
        {
            int n = Physics.RaycastNonAlloc(p + Vector3.up * 4f, Vector3.down, Hits, 60f,
                Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            float best = float.MaxValue;
            Vector3 ground = p;
            for (int i = 0; i < n; i++)
            {
                if (Hits[i].collider.attachedRigidbody == Body) continue;
                if (Hits[i].distance < best) { best = Hits[i].distance; ground = Hits[i].point; }
            }
            return ground + Vector3.up * 0.15f;
        }

        public void Respawn() => Teleport(_spawnPosition, _spawnRotation);

        public void SetSpawn(Vector3 position, Quaternion rotation)
        {
            _spawnPosition = position;
            _spawnRotation = rotation;
        }

        public void Teleport(Vector3 position, Quaternion rotation)
        {
            Body.position = position;
            Body.rotation = rotation;
            transform.SetPositionAndRotation(position, rotation);
            Body.linearVelocity = Vector3.zero;
            Body.angularVelocity = Vector3.zero;
            foreach (var w in wheels) { w.spinSpeed = 0; w.sink = 0; w.quickSink = 0; w.sliding = false; }
            QuicksandSink = 0f;
            var winch = GetComponent<Winch>();
            if (winch) winch.Release();
        }

        void Update()
        {
            float dt = Time.deltaTime;
            foreach (var w in wheels)
            {
                float target = w.grounded ? w.springLength : suspensionTravel;
                w.visualSpring = Mathf.Lerp(w.visualSpring, target, 1f - Mathf.Exp(-30f * dt));

                float rolling = w.forwardSpeed / wheelRadius;
                if (w.grounded)
                {
                    // Wheelspin: driven wheels spin faster than the ground speed when traction is exceeded.
                    float spin = rolling + w.slip * 25f * (controls.throttle - (IsReversing ? controls.brake : 0f));
                    if (controls.handbrake && !w.front) spin = 0f;
                    w.spinSpeed = Mathf.Lerp(w.spinSpeed, spin, 1f - Mathf.Exp(-20f * dt));
                }
                else
                {
                    float free = controls.throttle * 40f - (IsReversing ? controls.brake * 20f : 0f);
                    w.spinSpeed = Mathf.Lerp(w.spinSpeed, free, 1f - Mathf.Exp(-(free != 0 ? 3f : 0.5f) * dt));
                }
                w.spinAngle = Mathf.Repeat(w.spinAngle + w.spinSpeed * Mathf.Rad2Deg * dt, 360f);

                if (w.visual == null) continue;
                w.visual.localPosition = AnchorLocal(w) - Vector3.up * w.visualSpring;
                w.visual.localRotation = Quaternion.Euler(0f, w.front ? SteerAngle : 0f, 0f) *
                                         Quaternion.Euler(w.spinAngle, 0f, 0f);
            }
        }

        void OnDrawGizmosSelected()
        {
            foreach (var w in wheels)
            {
                Vector3 c = Application.isPlaying ? WheelCenterWorld(w) : transform.TransformPoint(w.restPosition);
                Gizmos.color = Application.isPlaying && w.grounded ? Color.green : Color.yellow;
                Gizmos.DrawWireSphere(c, wheelRadius);
            }
        }
    }
}
