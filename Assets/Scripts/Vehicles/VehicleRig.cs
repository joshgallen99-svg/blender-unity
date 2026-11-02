using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>
    /// Assembles a drivable vehicle (rigidbody, colliders, wheels, visuals) on a GameObject.
    /// Used by the editor scene builder to make the prefab and by tests to make a bare vehicle.
    /// </summary>
    public static class VehicleRig
    {
        public class Parts
        {
            public Mesh body;
            public Material[] bodyMaterials;
            public Mesh wheel;
            public Material[] wheelMaterials;
            public Vector3[] wheelPositions;   // FL, FR, RL, RR (vehicle-local wheel centres at rest)
            public Material dustMaterial;
            public PhysicsMaterial bodyPhysicsMaterial;   // must be an asset when saving prefabs
        }

        /// <summary>Ridgeback defaults (match blender/vehicles/ridgeback.py).</summary>
        public static readonly Vector3[] DefaultWheelPositions =
        {
            new Vector3(-0.86f, 0.43f, 1.25f), new Vector3(0.86f, 0.43f, 1.25f),
            new Vector3(-0.86f, 0.43f, -1.25f), new Vector3(0.86f, 0.43f, -1.25f),
        };

        static readonly string[] WheelNames = { "WheelFL", "WheelFR", "WheelRL", "WheelRR" };

        public static OffroadVehicle Assemble(GameObject root, Parts parts = null, float mass = 1800f)
        {
            bool wasActive = root.activeSelf;
            root.SetActive(false);   // defer Awake until fully configured

            var rb = GetOrAdd<Rigidbody>(root);
            rb.mass = mass;
            rb.linearDamping = 0.02f;
            rb.angularDamping = 0.4f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.Continuous;

            // Body colliders: lower tub + bumpers, and the cabin. Slippery so walls don't grab.
            var physMat = parts?.bodyPhysicsMaterial != null ? parts.bodyPhysicsMaterial : CreateBodyPhysicsMaterial();
            var colliders = Child(root.transform, "Colliders");
            AddBox(colliders, "Tub", new Vector3(0f, 0.95f, 0.01f), new Vector3(1.80f, 0.56f, 3.98f), physMat);
            AddBox(colliders, "Bumpers", new Vector3(0f, 0.68f, 0f), new Vector3(1.90f, 0.26f, 4.50f), physMat);
            AddBox(colliders, "Cabin", new Vector3(0f, 1.61f, -0.65f), new Vector3(1.70f, 0.72f, 2.50f), physMat);

            if (parts?.body != null)
            {
                var body = Child(root.transform, "Body");
                body.AddComponent<MeshFilter>().sharedMesh = parts.body;
                body.AddComponent<MeshRenderer>().sharedMaterials = parts.bodyMaterials;
            }

            var positions = parts?.wheelPositions != null && parts.wheelPositions.Length == 4
                ? parts.wheelPositions : DefaultWheelPositions;
            var wheelsRoot = Child(root.transform, "Wheels");
            var wheels = new OffroadVehicle.Wheel[4];
            for (int i = 0; i < 4; i++)
            {
                var p = positions[i];
                var pivot = Child(wheelsRoot.transform, WheelNames[i]);
                pivot.transform.localPosition = p;
                if (parts?.wheel != null)
                {
                    var mesh = Child(pivot.transform, "Mesh");
                    // The wheel mesh's show face points -X (vehicle left); turn right-side wheels around.
                    if (p.x > 0f) mesh.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
                    mesh.AddComponent<MeshFilter>().sharedMesh = parts.wheel;
                    mesh.AddComponent<MeshRenderer>().sharedMaterials = parts.wheelMaterials;
                }
                wheels[i] = new OffroadVehicle.Wheel
                {
                    name = WheelNames[i], restPosition = p, front = p.z > 0f, left = p.x < 0f, visual = pivot.transform,
                };
            }

            var vehicle = GetOrAdd<OffroadVehicle>(root);
            vehicle.wheels = wheels;
            vehicle.wheelRadius = 0.43f;

            if (parts?.dustMaterial != null)
            {
                var fx = GetOrAdd<VehicleEffects>(root);
                fx.dustMaterial = parts.dustMaterial;
            }
            if (Application.isPlaying || parts != null) GetOrAdd<VehicleAudio>(root);
            GetOrAdd<Winch>(root);

            root.SetActive(wasActive);
            return vehicle;
        }

        public static PhysicsMaterial CreateBodyPhysicsMaterial() => new PhysicsMaterial("VehicleBody")
        {
            dynamicFriction = 0.3f, staticFriction = 0.35f, bounciness = 0f,
            frictionCombine = PhysicsMaterialCombine.Minimum, bounceCombine = PhysicsMaterialCombine.Minimum,
        };

        static T GetOrAdd<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            return c != null ? c : go.AddComponent<T>();
        }

        static GameObject Child(Transform parent, string name)
        {
            var t = parent.Find(name);
            if (t != null) return t.gameObject;
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            return go;
        }

        static void AddBox(GameObject parent, string name, Vector3 center, Vector3 size, PhysicsMaterial mat)
        {
            var go = Child(parent.transform, name);
            var box = go.AddComponent<BoxCollider>();
            box.center = center;
            box.size = size;
            box.sharedMaterial = mat;
        }
    }
}
