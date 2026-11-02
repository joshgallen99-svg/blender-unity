using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>
    /// Front winch. Hook the best anchor ahead (a tree trunk or a big rock; with nothing in reach, a
    /// portable ground anchor), hold to reel in, tap again to release. The cable is a one-sided spring
    /// (it pulls, never pushes) with a motor that stalls when the load exceeds its rating, so the winch
    /// can drag the vehicle up a ledge but not yank it through a cliff.
    /// </summary>
    [RequireComponent(typeof(OffroadVehicle))]
    public class Winch : MonoBehaviour
    {
        public Vector3 fairlead = new Vector3(0f, 0.75f, 2.3f);   // where the cable leaves the bumper (local)
        public float range = 32f;
        [Tooltip("Rated pull (N): about 5.4 t, a typical 12,000 lb winch.")]
        public float ratedPull = 53000f;
        public float reelSpeed = 1.1f;          // m/s with no load
        public float cableStiffness = 90000f;   // N per metre of stretch
        public float cableDamping = 9000f;
        public Material cableMaterial;

        public bool Attached { get; private set; }
        public bool Reeling { get; private set; }
        public bool PortableAnchor { get; private set; }
        public float Tension { get; private set; }
        public float CableLength => _length;
        public Vector3 AnchorPoint => _anchorBody ? _anchorBody.transform.TransformPoint(_anchorLocal) : _anchorWorld;

        OffroadVehicle _vehicle;
        LineRenderer _line;
        float _length;
        Vector3 _anchorWorld, _anchorLocal;
        Rigidbody _anchorBody;
        static readonly Collider[] Near = new Collider[64];

        void Awake()
        {
            _vehicle = GetComponent<OffroadVehicle>();
        }

        Vector3 FairleadWorld => transform.TransformPoint(fairlead);

        /// <summary>Hook the best anchor in front of the vehicle. Returns false if nothing usable is in reach.</summary>
        public bool Attach()
        {
            if (Attached) return true;
            Vector3 from = FairleadWorld;
            Vector3 fwd = transform.forward;
            Collider best = null;
            Vector3 bestPoint = Vector3.zero;
            float bestScore = float.MinValue;
            int n = Physics.OverlapSphereNonAlloc(from + fwd * range * 0.5f, range * 0.6f, Near,
                Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = Near[i];
                if (c.attachedRigidbody == _vehicle.Body || c is TerrainCollider) continue;
                Vector3 p = c.ClosestPoint(from + fwd * 2f);
                if (c is MeshCollider mc && !mc.convex) p = c.bounds.ClosestPoint(from + fwd * 2f);
                Vector3 to = p - from;
                float d = to.magnitude;
                if (d < 3f || d > range) continue;
                float facing = Vector3.Dot(to / d, fwd);
                if (facing < 0.35f) continue;
                // Must be a solid anchor: trunks, or rocks at least a metre and a half across.
                bool trunk = c is CapsuleCollider;
                if (!trunk && c.bounds.extents.magnitude < 0.8f) continue;
                // Line of sight for the cable.
                if (Physics.Linecast(from, p - to / d * 0.3f, out var block, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
                    && block.collider != c && block.collider.attachedRigidbody != _vehicle.Body) continue;
                float score = facing * 2f - d / range + (trunk ? 0.3f : 0f) + (p.y - from.y) * 0.05f;
                if (score > bestScore) { bestScore = score; best = c; bestPoint = p; }
            }

            PortableAnchor = best == null;
            if (best != null)
            {
                _anchorBody = best.attachedRigidbody;
                _anchorWorld = bestPoint;
                if (_anchorBody) _anchorLocal = _anchorBody.transform.InverseTransformPoint(bestPoint);
                if (best is CapsuleCollider)   // wrap the strap round the trunk at bumper height
                    _anchorWorld.y = Mathf.Clamp(from.y, best.bounds.min.y + 0.4f, best.bounds.max.y);
            }
            else
            {
                // Portable anchor: driven into the ground up to 18 m ahead.
                Vector3 probe = from + Vector3.ProjectOnPlane(fwd, Vector3.up).normalized * 18f + Vector3.up * 20f;
                if (!Physics.Raycast(probe, Vector3.down, out var g, 60f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    return false;
                _anchorBody = null;
                _anchorWorld = g.point + Vector3.up * 0.2f;
            }
            _length = Vector3.Distance(FairleadWorld, AnchorPoint) + 0.2f;
            Attached = true;
            EnsureLine();
            _line.enabled = true;
            return true;
        }

        public void Release()
        {
            Attached = false;
            Reeling = false;
            Tension = 0f;
            if (_line) _line.enabled = false;
        }

        /// <summary>Set by the player controller each frame while the winch button is held.</summary>
        public void SetReel(bool on) => Reeling = Attached && on;

        void FixedUpdate()
        {
            if (!Attached) return;
            float dt = Time.fixedDeltaTime;
            var body = _vehicle.Body;
            Vector3 from = FairleadWorld;
            Vector3 anchor = AnchorPoint;
            Vector3 to = anchor - from;
            float dist = to.magnitude;
            if (dist > range * 1.6f) { Release(); return; }      // snapped / dragged off
            Vector3 dir = to / Mathf.Max(dist, 1e-3f);

            float stretch = dist - _length;
            float closing = -Vector3.Dot(body.GetPointVelocity(from), dir);   // + when moving away from the anchor
            float force = stretch > 0f ? stretch * cableStiffness + Mathf.Max(0f, closing) * cableDamping : 0f;
            force = Mathf.Min(force, ratedPull * 1.6f);                          // the brake slips beyond this
            Tension = force;
            if (force > 0f) body.AddForceAtPosition(dir * force, from);

            if (Reeling)
            {
                // The motor slows under load and stalls at its rating.
                float speed = reelSpeed * Mathf.Clamp01(1f - Tension / ratedPull);
                _length = Mathf.Max(1.2f, _length - speed * dt);
            }
            // Slack cable: take it up so it stays just taut.
            if (stretch < -0.5f) _length = dist + 0.3f;
        }

        void LateUpdate()
        {
            if (!Attached || _line == null) return;
            Vector3 a = FairleadWorld, b = AnchorPoint;
            float slack = Mathf.Clamp01(1f - Tension / 4000f);
            for (int i = 0; i < _line.positionCount; i++)
            {
                float t = i / (float)(_line.positionCount - 1);
                Vector3 p = Vector3.Lerp(a, b, t);
                p.y -= slack * 0.6f * 4f * t * (1f - t) * Mathf.Min(1f, Vector3.Distance(a, b) / 10f);
                _line.SetPosition(i, p);
            }
        }

        void EnsureLine()
        {
            if (_line) return;
            var go = new GameObject("WinchCable");
            go.transform.SetParent(transform, false);
            _line = go.AddComponent<LineRenderer>();
            _line.positionCount = 12;
            _line.widthMultiplier = 0.035f;
            _line.useWorldSpace = true;
            _line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _line.sharedMaterial = cableMaterial != null ? cableMaterial : DefaultCableMaterial();
        }

        static Material _defaultMat;
        static Material DefaultCableMaterial()
        {
            if (_defaultMat) return _defaultMat;
            var shader = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default");
            _defaultMat = new Material(shader) { name = "WinchCable" };
            _defaultMat.color = new Color(0.08f, 0.08f, 0.07f);
            return _defaultMat;
        }

        void OnDisable() => Release();
    }
}
