using System;
using UnityEngine;

namespace Offroad.Garage
{
    /// <summary>
    /// Everything the garage sells, with the trade-offs that make choices matter.
    /// Surface order everywhere: x = sand, y = gravel, z = packed soil, w = rock.
    /// </summary>
    public static class Catalog
    {
        [Serializable]
        public class TireDef
        {
            public string id, name, blurb, mesh;
            public int price;
            public Vector4 grip;          // multiplier per surface
            public float sandDrag;        // multiplies soft-sand drag (lower floats over sand)
            public float rolling;         // multiplies rolling resistance (top speed / efficiency)
            public float mudGrip = 1f;    // grip multiplier in mud and quicksand
            public float radius;
            public float width = 0.3f;    // tread width (m): the track it leaves in soft ground
            public int[] upgradeCost;     // per level above 0
            public float GripPerLevel => 0.06f;
        }

        [Serializable]
        public class BodyDef
        {
            public string id, name, blurb, mesh;
            public int price;
            public float mass;
            public float steerAngle;
            public Vector3 centerOfMass;
            public BoxDef[] colliders;
            public float cameraDistance;
        }

        [Serializable]
        public struct BoxDef
        {
            public Vector3 center, size;
            public BoxDef(Vector3 c, Vector3 s) { center = c; size = s; }
        }

        [Serializable]
        public class AccessoryDef
        {
            public string id, name, blurb;
            public int price;
            public float mass;
        }

        [Serializable]
        public class UpgradeTrack
        {
            public string id, name, blurb;
            public int[] cost;            // cost of level 1, 2, 3...
            public int MaxLevel => cost.Length;
        }

        [Serializable]
        public struct PaintDef
        {
            public string name;
            public Color color;          // linear
            public PaintDef(string n, float r, float g, float b) { name = n; color = new Color(r, g, b); }
        }

        public static readonly TireDef[] Tires =
        {
            new TireDef
            {
                id = "rock", name = "Rockjaw 37 Beadlock", mesh = "Wheel_Bead", price = 0, radius = 0.47f, width = 0.34f,
                blurb = "37-inch crawler tyre on beadlocks: aired down, it wraps over rock and claws up ledges.",
                grip = new Vector4(0.85f, 1.02f, 1.05f, 1.3f), sandDrag = 1.15f, rolling = 1.1f, mudGrip = 1.2f,
                upgradeCost = new[] { 250, 420 },
            },
            new TireDef
            {
                id = "at", name = "Trailhound A/T", mesh = "Wheel_AT", price = 0, radius = 0.43f, width = 0.3f,
                blurb = "All-terrain all-rounder. Good everywhere, best nowhere.",
                grip = new Vector4(0.92f, 1.0f, 1.0f, 1.0f), sandDrag = 1.0f, rolling = 1.0f, mudGrip = 0.95f,
                upgradeCost = new[] { 180, 320 },
            },
            new TireDef
            {
                id = "mt", name = "Gripjaw M/T", mesh = "Wheel_MT", price = 450, radius = 0.44f, width = 0.34f,
                blurb = "Big-block crawler. Claws up rock and through mud, but digs into soft sand.",
                grip = new Vector4(0.76f, 1.0f, 1.08f, 1.25f), sandDrag = 1.3f, rolling = 1.15f, mudGrip = 1.3f,
                upgradeCost = new[] { 220, 380 },
            },
            new TireDef
            {
                id = "dune", name = "Dunerunner", mesh = "Wheel_Dune", price = 400, radius = 0.44f, width = 0.42f,
                blurb = "Wide paddle tyre. Floats over dunes; slides around on bare rock and in mud.",
                grip = new Vector4(1.2f, 0.9f, 0.95f, 0.76f), sandDrag = 0.5f, rolling = 0.95f, mudGrip = 0.75f,
                upgradeCost = new[] { 200, 350 },
            },
        };

        public static readonly BodyDef[] Bodies =
        {
            new BodyDef
            {
                id = "crawler", name = "Ironbark", mesh = "Crawler", price = 0, mass = 1950f, steerAngle = 38f,
                blurb = "Open-top rock crawler on solid axles and 37s. Huge articulation, stubby bumpers, sliders.",
                centerOfMass = new Vector3(0f, 0.82f, 0.05f), cameraDistance = 7.2f,
                colliders = new[]
                {
                    new BoxDef(new Vector3(0f, 1.18f, 0f), new Vector3(1.64f, 0.46f, 3.45f)),        // tub
                    new BoxDef(new Vector3(0f, 0.71f, 0f), new Vector3(1.04f, 0.12f, 2.3f)),         // belly skid
                    new BoxDef(new Vector3(0f, 0.86f, 0.1f), new Vector3(1.04f, 0.2f, 3.8f)),        // frame rails
                    new BoxDef(new Vector3(0f, 0.95f, 1.91f), new Vector3(1.48f, 0.3f, 0.36f)),      // winch bumper
                    new BoxDef(new Vector3(0f, 0.91f, -1.81f), new Vector3(1.4f, 0.24f, 0.24f)),     // rear bumper
                    new BoxDef(new Vector3(0f, 1.74f, -0.1f), new Vector3(1.56f, 0.66f, 2.2f)),      // cage
                },
            },
            new BodyDef
            {
                id = "ridgeback", name = "Ridgeback", mesh = "Ridgeback", price = 0, mass = 1800f, steerAngle = 34f,
                blurb = "Short-wheelbase wagon. Nimble, clears crests easily, a little twitchy at speed.",
                centerOfMass = new Vector3(0f, 0.72f, 0.05f), cameraDistance = 6.8f,
                colliders = new[]
                {
                    new BoxDef(new Vector3(0f, 0.95f, 0.01f), new Vector3(1.80f, 0.56f, 3.98f)),
                    new BoxDef(new Vector3(0f, 0.68f, 0f), new Vector3(1.90f, 0.26f, 4.50f)),
                    new BoxDef(new Vector3(0f, 1.61f, -0.65f), new Vector3(1.70f, 0.72f, 2.50f)),
                },
            },
            new BodyDef
            {
                id = "packhorse", name = "Packhorse", mesh = "Packhorse", price = 900, mass = 2150f, steerAngle = 31f,
                blurb = "Long-wheelbase pickup. Planted and stable at speed, but can high-centre on sharp crests.",
                centerOfMass = new Vector3(0f, 0.76f, 0.15f), cameraDistance = 7.6f,
                colliders = new[]
                {
                    new BoxDef(new Vector3(0f, 0.95f, -0.15f), new Vector3(1.80f, 0.56f, 4.80f)),
                    new BoxDef(new Vector3(0f, 0.68f, -0.15f), new Vector3(1.90f, 0.26f, 5.30f)),
                    new BoxDef(new Vector3(0f, 1.61f, 0.12f), new Vector3(1.70f, 0.72f, 1.45f)),
                    new BoxDef(new Vector3(0f, 1.42f, -1.6f), new Vector3(1.80f, 0.40f, 1.90f)),
                },
            },
        };

        public static readonly AccessoryDef[] Accessories =
        {
            new AccessoryDef { id = "RoofRack", name = "Roof rack & light bar", price = 150, mass = 60f,
                blurb = "Jerry cans, a recovery case and a light bar. Raises the centre of mass a touch." },
            new AccessoryDef { id = "Snorkel", name = "Raised air intake", price = 120, mass = 8f,
                blurb = "Breathes clean air above the dust. Looks the part." },
            new AccessoryDef { id = "BullBar", name = "Bull bar & spotlights", price = 180, mass = 35f,
                blurb = "Steel nudge bar with a pair of spotlights." },
        };

        public static readonly UpgradeTrack Engine = new UpgradeTrack
        {
            id = "engine", name = "Engine", blurb = "More power for climbing dunes and pulling out of sand. +12% per stage.",
            cost = new[] { 250, 450, 700 },
        };

        public static readonly UpgradeTrack Suspension = new UpgradeTrack
        {
            id = "suspension", name = "Suspension", blurb = "Longer travel keeps tyres on the ground over rough rock. Stiffer anti-roll.",
            cost = new[] { 200, 400, 650 },
        };

        public static readonly PaintDef[] Paints =
        {
            new PaintDef("Lagoon Teal", 0.055f, 0.25f, 0.27f),
            new PaintDef("Desert Sand", 0.55f, 0.42f, 0.27f),
            new PaintDef("Rescue Orange", 0.75f, 0.20f, 0.03f),
            new PaintDef("Bush Green", 0.10f, 0.17f, 0.07f),
            new PaintDef("Chalk White", 0.72f, 0.72f, 0.68f),
            new PaintDef("Midnight Blue", 0.02f, 0.05f, 0.14f),
            new PaintDef("Oxide Red", 0.30f, 0.05f, 0.03f),
        };

        public static TireDef Tire(string id) => Array.Find(Tires, t => t.id == id) ?? Tires[0];
        public static BodyDef Body(string id) => Array.Find(Bodies, b => b.id == id) ?? Bodies[0];

        /// <summary>How well a tyre suits a surface mix (layer weights), 1 = neutral.</summary>
        public static float Suitability(TireDef tire, Vector4 layers, int level = 0)
        {
            float total = layers.x + layers.y + layers.z + layers.w;
            float g = total > 1e-3f ? Vector4.Dot(layers, tire.grip) / total : 1f;
            return g * (1f + tire.GripPerLevel * level);
        }
    }
}
