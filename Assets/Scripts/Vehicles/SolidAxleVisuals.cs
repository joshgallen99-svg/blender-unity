using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>
    /// Poses solid-axle suspension parts every frame from the wheel positions the physics produced: each
    /// axle housing spans its pair of wheels (so it tilts as the axle articulates), and four links and two
    /// coilovers per axle are stretched between their chassis mounts and the axle. Purely visual.
    /// Mount points match blender/preview/render_crawler.py.
    /// </summary>
    [DefaultExecutionOrder(100)]   // after OffroadVehicle.Update has placed the wheels
    public class SolidAxleVisuals : MonoBehaviour
    {
        public Mesh housing, link, coilover;
        public Material[] housingMaterials, linkMaterials, coiloverMaterials;

        // Vehicle-local; x is mirrored per side, and z is measured from the axle toward the middle.
        static readonly Vector3[] LinkChassis = { new Vector3(0.48f, 0.72f, 0.95f), new Vector3(0.26f, 1.02f, 0.70f) };
        // Axle-local (x along the axle toward each wheel).
        static readonly Vector3[] LinkAxle = { new Vector3(0.33f, -0.08f, 0f), new Vector3(0.20f, 0.17f, 0f) };
        static readonly Vector3 CoilChassis = new Vector3(0.66f, 1.34f, 0.10f);
        static readonly Vector3 CoilAxle = new Vector3(0.60f, 0.10f, 0f);

        OffroadVehicle _vehicle;
        Transform[] _axles = new Transform[2];
        Transform[,] _links = new Transform[2, 4];
        Transform[,] _coils = new Transform[2, 2];
        Transform _root;

        public void Build()
        {
            _vehicle = GetComponent<OffroadVehicle>();
            if (_root) DestroyImmediateSafe(_root.gameObject);
            _root = new GameObject("Suspension").transform;
            _root.SetParent(transform, false);
            for (int a = 0; a < 2; a++)
            {
                _axles[a] = Part(a == 0 ? "FrontAxle" : "RearAxle", housing, housingMaterials);
                for (int i = 0; i < 4; i++) _links[a, i] = Part("Link", link, linkMaterials);
                for (int i = 0; i < 2; i++) _coils[a, i] = Part("Coilover", coilover, coiloverMaterials);
            }
        }

        Transform Part(string name, Mesh mesh, Material[] mats)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterials = mats;
            return go.transform;
        }

        static void DestroyImmediateSafe(GameObject go)
        {
            if (Application.isPlaying) Destroy(go); else DestroyImmediate(go);
        }

        void Start()
        {
            if (_root == null) _root = transform.Find("Suspension");
            if (_root == null) Build();
            else
            {
                _vehicle = GetComponent<OffroadVehicle>();
                int k = 0;
                for (int a = 0; a < 2; a++)
                {
                    _axles[a] = _root.GetChild(k++);
                    for (int i = 0; i < 4; i++) _links[a, i] = _root.GetChild(k++);
                    for (int i = 0; i < 2; i++) _coils[a, i] = _root.GetChild(k++);
                }
            }
            Pose();
        }

        void LateUpdate() => Pose();

        void Pose()
        {
            if (_vehicle == null || _vehicle.wheels.Length < 4 || _axles[0] == null) return;
            for (int a = 0; a < 2; a++)
            {
                var wl = _vehicle.wheels[a * 2];          // FL / RL
                var wr = _vehicle.wheels[a * 2 + 1];      // FR / RR
                Vector3 pl = wl.visual ? wl.visual.localPosition : wl.restPosition;
                Vector3 pr = wr.visual ? wr.visual.localPosition : wr.restPosition;
                Vector3 mid = (pl + pr) * 0.5f;
                Vector3 axis = (pr - pl).normalized;     // toward the right wheel (+x)
                Quaternion rot = Quaternion.FromToRotation(Vector3.right, axis);
                var ax = _axles[a];
                ax.localPosition = mid;
                ax.localRotation = rot;
                float toMiddle = -Mathf.Sign(mid.z);
                int li = 0;
                for (int s = -1; s <= 1; s += 2)
                {
                    for (int k = 0; k < 2; k++)
                    {
                        var c = LinkChassis[k];
                        Vector3 chassis = new Vector3(s * c.x, c.y, mid.z + toMiddle * c.z);
                        Vector3 onAxle = mid + rot * new Vector3(s * LinkAxle[k].x, LinkAxle[k].y, LinkAxle[k].z);
                        Stretch(_links[a, li++], onAxle, chassis);
                    }
                    Vector3 top = new Vector3(s * CoilChassis.x, CoilChassis.y, mid.z + toMiddle * CoilChassis.z);
                    Vector3 bottom = mid + rot * new Vector3(s * CoilAxle.x, CoilAxle.y, CoilAxle.z);
                    Stretch(_coils[a, s < 0 ? 0 : 1], top, bottom);
                }
            }
        }

        /// <summary>Unit parts run 1 m along +z from their origin: point them from a to b and scale to fit.</summary>
        static void Stretch(Transform t, Vector3 a, Vector3 b)
        {
            Vector3 d = b - a;
            float len = d.magnitude;
            if (len < 1e-3f) return;
            t.localPosition = a;
            t.localRotation = Quaternion.LookRotation(d / len, Mathf.Abs(d.y / len) > 0.95f ? Vector3.forward : Vector3.up);
            t.localScale = new Vector3(1f, 1f, len);
        }
    }
}
