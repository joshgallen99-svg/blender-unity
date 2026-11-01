using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>How a ground surface feels to a tyre.</summary>
    public struct SurfaceInfo
    {
        public float grip;       // multiplies tyre friction
        public float traction;   // multiplies drive force (soft ground wastes power)
        public float drag;       // extra rolling drag (sand, mud)
        public float dust;       // how much dust/spray wheels kick up (0..1)
        public Color dustColor;
        public Vector4 layers;   // surface mix: x sand, y gravel, z packed soil, w rock (zero = unknown)
        public float mud;        // 0..1 wet mud / standing water: slippery, sticky, wheels sink a little
        public float quicksand;  // 0..1 quicksand: wheels sink steadily unless the vehicle keeps moving
        public float washboard;  // 0..1 corrugations: rattles the suspension, costs grip at speed

        public static readonly SurfaceInfo Default = new SurfaceInfo
        {
            grip = 1f, traction = 1f, drag = 0f, dust = 0.3f, dustColor = new Color(0.75f, 0.6f, 0.45f, 1f)
        };

        public static SurfaceInfo Lerp(in SurfaceInfo a, in SurfaceInfo b, float t) => new SurfaceInfo
        {
            grip = Mathf.Lerp(a.grip, b.grip, t),
            traction = Mathf.Lerp(a.traction, b.traction, t),
            drag = Mathf.Lerp(a.drag, b.drag, t),
            dust = Mathf.Lerp(a.dust, b.dust, t),
            dustColor = Color.Lerp(a.dustColor, b.dustColor, t),
            layers = Vector4.Lerp(a.layers, b.layers, t),
            mud = Mathf.Lerp(a.mud, b.mud, t),
            quicksand = Mathf.Lerp(a.quicksand, b.quicksand, t),
            washboard = Mathf.Lerp(a.washboard, b.washboard, t),
        };
    }

    /// <summary>How a tyre behaves on each surface (x sand, y gravel, z soil, w rock).</summary>
    [System.Serializable]
    public struct TireProfile
    {
        public Vector4 grip;
        public float sandDrag;
        public float rolling;
        public float mudGrip;    // grip multiplier in mud and quicksand (0 = treat as 1)

        public static readonly TireProfile Neutral = new TireProfile { grip = Vector4.one, sandDrag = 1f, rolling = 1f, mudGrip = 1f };

        public float GripOn(in SurfaceInfo s)
        {
            float total = s.layers.x + s.layers.y + s.layers.z + s.layers.w;
            float fit = total > 1e-3f ? Vector4.Dot(s.layers, grip) / total : 1f;
            float wet = Mathf.Clamp01(s.mud + s.quicksand);
            return Mathf.Lerp(fit, mudGrip > 0f ? mudGrip : 1f, wet);
        }

        public float DragOn(in SurfaceInfo s)
        {
            float total = s.layers.x + s.layers.y + s.layers.z + s.layers.w;
            float sand = total > 1e-3f ? s.layers.x / total : 0f;
            return Mathf.Lerp(1f, sandDrag, sand);
        }
    }

    /// <summary>Anything that can tell a wheel what it is driving on.</summary>
    public interface ISurfaceProvider
    {
        SurfaceInfo GetSurface(Vector3 worldPoint, Collider collider);
    }
}
