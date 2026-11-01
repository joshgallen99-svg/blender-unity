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
        };
    }

    /// <summary>Anything that can tell a wheel what it is driving on.</summary>
    public interface ISurfaceProvider
    {
        SurfaceInfo GetSurface(Vector3 worldPoint, Collider collider);
    }
}
