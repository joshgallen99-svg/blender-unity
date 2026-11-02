using System;
using Offroad.Garage;
using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>
    /// Fits a garage loadout to a vehicle: body, colliders, tyres (look and grip), spare wheel,
    /// accessories, paint and upgrade levels. Works in the editor (prefab building) and at runtime.
    /// </summary>
    [RequireComponent(typeof(OffroadVehicle))]
    public class VehicleAssembler : MonoBehaviour
    {
        public VehicleArt art;

        public string ActiveTire { get; private set; } = "at";
        public string ActiveSpare { get; private set; } = "at";
        public float CameraDistance { get; private set; } = 6.8f;
        public event Action Assembled;

        const float BaseMass = 1800f;

        OffroadVehicle _vehicle;
        Material _paint;
        Loadout _last;

        OffroadVehicle Vehicle => _vehicle ? _vehicle : (_vehicle = GetComponent<OffroadVehicle>());

        public void Apply(Loadout l)
        {
            if (art == null || l == null) return;
            _last = l;
            var body = Catalog.Body(l.body);
            var bodyArt = art.Body(body.mesh);
            ApplyBody(body, bodyArt, l);
            ActiveTire = l.tire;
            ActiveSpare = l.spare;
            ApplyTires(l);
            ApplyUpgrades(body, l);
            Assembled?.Invoke();
        }

        /// <summary>Swap the fitted tyres with the spare on the back (one per expedition).</summary>
        public void SwapToSpare()
        {
            (ActiveTire, ActiveSpare) = (ActiveSpare, ActiveTire);
            if (_last != null) ApplyTires(_last);
            Assembled?.Invoke();
        }

        void ApplyBody(Catalog.BodyDef def, VehicleArt.BodyArt a, Loadout l)
        {
            // Body mesh + paint.
            var bodyGo = Child(transform, "Body");
            var mf = GetOrAdd<MeshFilter>(bodyGo);
            var mr = GetOrAdd<MeshRenderer>(bodyGo);
            mf.sharedMesh = a.body.mesh;
            mr.sharedMaterials = Painted(a.body.materials, l.paint);

            // Colliders.
            var col = Child(transform, "Colliders");
            for (int i = col.transform.childCount - 1; i >= 0; i--) Kill(col.transform.GetChild(i).gameObject);
            for (int i = 0; i < def.colliders.Length; i++)
            {
                var go = new GameObject("Box" + i);
                go.transform.SetParent(col.transform, false);
                var box = go.AddComponent<BoxCollider>();
                box.center = def.colliders[i].center;
                box.size = def.colliders[i].size;
                box.sharedMaterial = art.bodyPhysics;
            }

            // Accessories.
            var accRoot = Child(transform, "Accessories");
            foreach (var acc in a.accessories)
            {
                var go = Child(accRoot.transform, acc.id);
                GetOrAdd<MeshFilter>(go).sharedMesh = acc.mesh;
                var r = GetOrAdd<MeshRenderer>(go);
                r.sharedMaterials = acc.materials;
                go.SetActive(l.Fitted(acc.id.Split('_')[0]));
            }
            // Accessories for other bodies are not children of this body: clear stale ones.
            for (int i = accRoot.transform.childCount - 1; i >= 0; i--)
            {
                var c = accRoot.transform.GetChild(i).gameObject;
                if (Array.Find(a.accessories, x => x.id == c.name) == null) Kill(c);
            }

            // Wheel positions.
            var v = Vehicle;
            var wheelsRoot = Child(transform, "Wheels");
            for (int i = 0; i < v.wheels.Length && i < a.wheelPositions.Length; i++)
            {
                v.wheels[i].restPosition = a.wheelPositions[i];
                if (v.wheels[i].visual) v.wheels[i].visual.localPosition = a.wheelPositions[i];
            }
            // Solid axles, links and coilovers (crawler), posed every frame from the wheels.
            var axles = GetComponent<SolidAxleVisuals>();
            if (a.solidAxles && art.axleHousing != null && art.axleHousing.mesh != null)
            {
                if (!axles) axles = gameObject.AddComponent<SolidAxleVisuals>();
                axles.housing = art.axleHousing.mesh;
                axles.housingMaterials = art.axleHousing.materials;
                axles.link = art.link.mesh;
                axles.linkMaterials = art.link.materials;
                axles.coilover = art.coilover.mesh;
                axles.coiloverMaterials = art.coilover.materials;
                axles.Build();
            }
            else if (axles)
            {
                var susp = transform.Find("Suspension");
                if (susp) Kill(susp.gameObject);
                if (Application.isPlaying) Destroy(axles); else DestroyImmediate(axles);
            }

            var spare = Child(transform, "Spare");
            spare.transform.localPosition = a.spareMount;
            spare.transform.localRotation = Quaternion.Euler(0f, -90f, 0f);   // show face to the rear
            CameraDistance = def.cameraDistance;
        }

        void ApplyTires(Loadout l)
        {
            var v = Vehicle;
            var tire = Catalog.Tire(ActiveTire);
            var tireArt = art.Tire(tire.mesh);
            foreach (var w in v.wheels)
            {
                if (!w.visual) continue;
                var mesh = Child(w.visual, "Mesh");
                mesh.transform.localRotation = w.left ? Quaternion.identity : Quaternion.Euler(0f, 180f, 0f);
                GetOrAdd<MeshFilter>(mesh).sharedMesh = tireArt.mesh;
                GetOrAdd<MeshRenderer>(mesh).sharedMaterials = tireArt.materials;
            }
            float lvl = 1f + tire.GripPerLevel * l.TireLevel(tire.id);
            v.tire = new TireProfile { grip = tire.grip * lvl, sandDrag = tire.sandDrag, rolling = tire.rolling, mudGrip = tire.mudGrip * lvl };
            v.wheelRadius = tire.radius;
            v.tireWidth = tire.width;

            var spareDef = Catalog.Tire(ActiveSpare);
            var spareArt = art.Tire(spareDef.mesh);
            var spare = Child(transform, "Spare");
            GetOrAdd<MeshFilter>(spare).sharedMesh = spareArt.mesh;
            GetOrAdd<MeshRenderer>(spare).sharedMaterials = spareArt.materials;
        }

        void ApplyUpgrades(Catalog.BodyDef body, Loadout l)
        {
            var v = Vehicle;
            float extra = 0f;
            foreach (var a in Catalog.Accessories) if (l.Fitted(a.id)) extra += a.mass;
            float mass = body.mass + extra;
            var rb = GetComponent<Rigidbody>();
            if (rb) rb.mass = mass;
            v.centerOfMass = body.centerOfMass + (l.Fitted("RoofRack") ? new Vector3(0f, 0.04f, 0f) : Vector3.zero);
            if (rb) rb.centerOfMass = v.centerOfMass;
            float massRatio = mass / BaseMass;
            v.torqueScale = massRatio * (1f + 0.1f * l.engineLevel);
            v.suspensionTravel = 0.5f + 0.04f * l.suspensionLevel;
            v.antiRoll = Mathf.Max(0.15f, 0.3f - 0.05f * l.suspensionLevel);   // better suspension: more flex
            v.maxSteerAngle = body.steerAngle;
        }

        Material[] Painted(Material[] mats, int paintIndex)
        {
            var result = (Material[])mats.Clone();
            if (!Application.isPlaying) return result;   // keep prefab materials as assets
            var colour = Catalog.Paints[Mathf.Clamp(paintIndex, 0, Catalog.Paints.Length - 1)].color;
            for (int i = 0; i < result.Length; i++)
            {
                if (result[i] == null || result[i].name.Replace(" (Instance)", "") != "Paint") continue;
                if (_paint == null) _paint = new Material(result[i]) { name = "Paint" };
                _paint.SetColor("_BaseColor", colour.gamma);
                result[i] = _paint;
            }
            return result;
        }

        static GameObject Child(Transform parent, string name)
        {
            var t = parent.Find(name);
            if (t) return t.gameObject;
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            return go;
        }

        static T GetOrAdd<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            return c != null ? c : go.AddComponent<T>();
        }

        static void Kill(GameObject go)
        {
            if (Application.isPlaying) Destroy(go);
            else DestroyImmediate(go);
        }

        void OnDestroy()
        {
            if (_paint) Destroy(_paint);
        }
    }
}
