using System;
using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>Meshes and materials for every body, tyre and accessory (built by the editor from Fleet.fbx).</summary>
    public class VehicleArt : ScriptableObject
    {
        [Serializable]
        public class Part
        {
            public string id;
            public Mesh mesh;
            public Material[] materials;
        }

        [Serializable]
        public class BodyArt
        {
            public string id;
            public Part body;
            public Vector3[] wheelPositions = new Vector3[4];   // FL, FR, RL, RR wheel centres at rest
            public Vector3 spareMount;
            public Part[] accessories;
        }

        public BodyArt[] bodies;
        public Part[] tires;
        public Material dustMaterial;
        public PhysicsMaterial bodyPhysics;

        public BodyArt Body(string id) => Array.Find(bodies, b => string.Equals(b.id, id, StringComparison.OrdinalIgnoreCase)) ?? bodies[0];
        public Part Tire(string mesh) => Array.Find(tires, t => t.id == mesh) ?? tires[0];
    }
}
