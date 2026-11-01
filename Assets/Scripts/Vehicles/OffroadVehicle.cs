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
        }

        [Header("Wheels")]
        public Wheel[] wheels = Array.Empty<Wheel>();
        public float wheelRadius = 0.43f;

        [Header("Suspension")]
        [Tooltip("Total wheel travel in metres.")]
        public float suspensionTravel = 0.32f;
        [Tooltip("Fraction of travel used up when standing still.")]
        [Range(0.2f, 0.7f)] public float restCompression = 0.45f;
        [Range(0.05f, 1.5f)] public float bumpDamping = 0.35f;     // damping ratios (1 = critical)
        [Range(0.05f, 1.5f)] public float reboundDamping = 0.55f;
        [Tooltip("Anti-roll stiffness as a multiple of the spring rate.")]
        public float antiRoll = 0.6f;

        [Header("Drivetrain")]
        public float enginePower = 165000f;      // watts at the wheels
        public float maxTractiveForce = 13500f;  // newtons, all wheels
        public float topSpeed = 34f;             // m/s (~122 km/h)
        public float reverseTopSpeed = 9f;
        public float brakeForce = 9000f;         // per wheel
        public float rollingResistance = 30f;    // N per m/s per wheel
        [Tooltip("Seconds the brake must be held at a standstill before reverse engages.")]
        public float reverseDelay = 0.3f;

        [Header("Tyres")]
        public float tireGrip = 1.05f;           // friction coefficient on a neutral surface
        [Range(0, 1)] public float lateralStiffness = 0.82f;
        [Range(0, 1)] public float handbrakeRearGrip = 0.35f;
        [Tooltip("Height above the contact patch where tyre forces act (lower = more body roll).")]
        public float tireForceHeight = 0.3f;

        [Header("Steering")]
        public float maxSteerAngle = 34f;
        public float highSpeedSteerAngle = 11f;
        public float steerSpeed = 3.2f;
        public float steerReturnSpeed = 5f;

        [Header("Stability")]
        public Vector3 centerOfMass = new Vector3(0f, 0.58f, 0.05f);
        public float downforce = 2.5f;
        public float airControl = 2.2f;          // rad/s^2
        public float autoRightDelay = 2.5f;

        public VehicleControls controls;
        public ISurfaceProvider surfaceProvider;

        public Rigidbody Body { get; private set; }
        public float ForwardSpeed { get; private set; }
        public float SteerAngle { get; private set; }
        public int GroundedWheels { get; private set; }
        public bool IsReversing { get; private set; }
        public float SpringRate { get; private set; }

        const float CastLift = 0.3f;              // start casts above the travel so close ground is not missed
        static readonly RaycastHit[] Hits = new RaycastHit[16];

        float _steerInput;
        float _brakeHeldAtStop;
        float _upsideDownTime;
        Vector3 _spawnPosition;
        Quaternion _spawnRotation;

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

            ApplyAntiRoll(up);

            // ---- Drivetrain request.
            float driveTotal = 0f, brakeAmount = 0f;
            IsReversing = false;
            if (controls.throttle > 0.01f)
            {
                if (ForwardSpeed < -0.8f) brakeAmount = controls.throttle;
                else driveTotal = controls.throttle * TractiveForce(ForwardSpeed, topSpeed);
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
                        driveTotal = -controls.brake * TractiveForce(-ForwardSpeed, reverseTopSpeed) * 0.7f;
                        IsReversing = true;
                    }
                    else brakeAmount = Mathf.Max(brakeAmount, controls.brake);
                }
            }
            else _brakeHeldAtStop = 0f;
            bool idle = controls.throttle <= 0.01f && controls.brake <= 0.01f;

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

                float grip = tireGrip * w.surface.grip;
                bool handbraked = controls.handbrake && !w.front;

                float fLong = drivenGrounded > 0 ? driveTotal / drivenGrounded * w.surface.traction : 0f;
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
                fLong -= vLong * (rollingResistance + w.surface.drag * 220f);

                float latGrip = lateralStiffness * (handbraked ? handbrakeRearGrip : 1f);
                float fLat = -(vLat / dt + gLat) * massShare * latGrip;

                float limit = grip * w.load;
                Vector2 f = new Vector2(fLong, fLat);
                float mag = f.magnitude;
                w.slip = 0f;
                if (mag > limit && mag > 1e-3f)
                {
                    w.slip = Mathf.Clamp01((mag - limit) / Mathf.Max(limit, 1f));
                    f *= limit / mag;
                }

                Vector3 at = w.contactPoint + up * tireForceHeight;
                Body.AddForceAtPosition(fwd * f.x + right * f.y, at);
            }

            // ---- Helpers.
            if (GroundedWheels >= 2)
                Body.AddForce(-up * downforce * ForwardSpeed * ForwardSpeed);
            if (GroundedWheels == 0)
            {
                Vector3 torque = transform.right * (controls.throttle - controls.brake) * airControl
                                 - transform.forward * controls.steer * airControl;
                Body.AddTorque(torque, ForceMode.Acceleration);
            }
            CheckAutoRight(dt);
        }

        float TractiveForce(float speed, float limit)
        {
            float s = Mathf.Max(Mathf.Abs(speed), 1f);
            float f = Mathf.Min(maxTractiveForce, enginePower / s);
            return f * Mathf.Clamp01((limit - Mathf.Max(speed, 0f)) / 4f);
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
            w.springLength = Mathf.Clamp(best - CastLift, 0f, suspensionTravel);
            Vector3 center = anchor - up * w.springLength;
            bool overlapped = hit.point == Vector3.zero && hit.distance <= 0f;
            w.contactPoint = overlapped ? center - up * wheelRadius : hit.point;
            w.contactNormal = overlapped || Vector3.Dot(hit.normal, up) < 0.2f ? up : hit.normal;
            if (w.contactCollider != hit.collider || surfaceProvider != null)
                w.surface = surfaceProvider != null ? surfaceProvider.GetSurface(w.contactPoint, hit.collider) : SurfaceInfo.Default;
            w.contactCollider = hit.collider;
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
                    float f = (ca - cb) * k;
                    if (a.grounded) Body.AddForceAtPosition(-up * f, WheelCenterWorld(a));
                    if (b.grounded) Body.AddForceAtPosition(up * f, WheelCenterWorld(b));
                }
            }
        }

        void CheckAutoRight(float dt)
        {
            bool upsideDown = Vector3.Dot(transform.up, Vector3.up) < 0.25f;
            if (upsideDown && Body.linearVelocity.magnitude < 2.5f) _upsideDownTime += dt;
            else _upsideDownTime = 0f;
            if (_upsideDownTime > autoRightDelay) ResetUpright();
            if (transform.position.y < -100f) Respawn();
        }

        /// <summary>Lift the vehicle and put it back on its wheels, keeping its heading.</summary>
        public void ResetUpright()
        {
            _upsideDownTime = 0f;
            Vector3 fwd = Vector3.ProjectOnPlane(transform.forward, Vector3.up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            Vector3 pos = transform.position + Vector3.up * 2f;
            if (Physics.Raycast(pos + Vector3.up * 50f, Vector3.down, out var hit, 200f,
                    Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) && hit.collider.attachedRigidbody != Body)
                pos.y = hit.point.y + 1.2f;
            Teleport(pos, Quaternion.LookRotation(fwd, Vector3.up));
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
            foreach (var w in wheels) w.spinSpeed = 0;
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
