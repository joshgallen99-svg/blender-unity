using Offroad.Core;
using UnityEngine;

namespace Offroad.CameraRig
{
    /// <summary>
    /// Smooth third-person chase camera. Follows the vehicle's heading (not its pitch/roll, so it
    /// stays calm over bumps), can be orbited with the mouse / right stick and drifts back behind
    /// the vehicle when left alone. Pulls in to avoid clipping through terrain and rocks.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class ChaseCamera : MonoBehaviour
    {
        public Rigidbody target;
        public float distance = 6.8f;
        public float distanceAtSpeed = 8.2f;
        public float pivotHeight = 1.35f;
        public float basePitch = 11f;
        public float followTime = 0.28f;
        public float orbitSensitivity = 2.2f;
        public float recenterDelay = 1.8f;
        public float baseFov = 58f;
        public float speedFov = 12f;
        public float collisionRadius = 0.35f;

        Camera _cam;
        float _yaw, _yawVel;
        float _orbitYaw, _orbitPitch, _lastOrbitTime = -10f;
        float _currentDistance;
        bool _initialised;

        public bool InputEnabled { get; set; } = true;

        void Awake()
        {
            _cam = GetComponent<Camera>();
            _currentDistance = distance;
        }

        public void SnapBehindTarget()
        {
            if (!target) return;
            Vector3 f = Vector3.ProjectOnPlane(target.transform.forward, Vector3.up);
            _yaw = Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg;
            _yawVel = 0;
            _orbitYaw = _orbitPitch = 0;
            _initialised = true;
            LateUpdate();
        }

        void LateUpdate()
        {
            if (!target) return;
            float dt = Time.unscaledDeltaTime;
            if (!_initialised) { SnapBehindTarget(); return; }

            Transform t = target.transform;
            Vector3 vel = target.linearVelocity;
            Vector3 flatVel = Vector3.ProjectOnPlane(vel, Vector3.up);
            Vector3 fwd = Vector3.ProjectOnPlane(t.forward, Vector3.up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.ProjectOnPlane(t.up, Vector3.up);
            fwd.Normalize();
            float speed = flatVel.magnitude;
            // When moving forward at speed, look along the direction of travel (smooths slides).
            if (speed > 4f && Vector3.Dot(flatVel, fwd) > 0f)
                fwd = Vector3.Slerp(fwd, flatVel.normalized, 0.4f);

            float targetYaw = Mathf.Atan2(fwd.x, fwd.z) * Mathf.Rad2Deg;
            if (Time.timeScale > 0f)
                _yaw = Mathf.SmoothDampAngle(_yaw, targetYaw, ref _yawVel, followTime, Mathf.Infinity, dt);

            // Orbit input.
            if (InputEnabled)
            {
                GameInput.Poll();
                Vector2 look = GameInput.Look;
                if (look.sqrMagnitude > 0.0004f)
                {
                    _orbitYaw += look.x * orbitSensitivity;
                    _orbitPitch = Mathf.Clamp(_orbitPitch - look.y * orbitSensitivity, -8f, 50f);
                    _lastOrbitTime = Time.unscaledTime;
                }
            }
            if (Time.unscaledTime - _lastOrbitTime > recenterDelay)
            {
                float k = 1f - Mathf.Exp(-2.5f * dt);
                _orbitYaw = Mathf.LerpAngle(_orbitYaw, 0f, k);
                _orbitPitch = Mathf.Lerp(_orbitPitch, 0f, k);
            }

            float speedT = Mathf.Clamp01(speed / 30f);
            Quaternion rot = Quaternion.Euler(basePitch + _orbitPitch, _yaw + _orbitYaw, 0f);
            Vector3 pivot = t.position + Vector3.up * pivotHeight;
            float wanted = Mathf.Lerp(distance, distanceAtSpeed, speedT);

            // Keep the camera out of terrain and rocks.
            float allowed = wanted;
            if (Physics.SphereCast(pivot, collisionRadius, rot * Vector3.back, out var hit, wanted,
                    Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) && hit.rigidbody != target)
                allowed = Mathf.Max(1.5f, hit.distance - 0.1f);
            _currentDistance = allowed < _currentDistance
                ? allowed
                : Mathf.Lerp(_currentDistance, allowed, 1f - Mathf.Exp(-3f * dt));

            Vector3 pos = pivot + rot * Vector3.back * _currentDistance;
            transform.position = pos;
            transform.rotation = Quaternion.LookRotation(pivot + fwd * 1.5f - pos, Vector3.up);

            if (_cam)
                _cam.fieldOfView = Mathf.Lerp(_cam.fieldOfView, baseFov + speedFov * speedT * speedT,
                    1f - Mathf.Exp(-2f * dt));
        }
    }
}
