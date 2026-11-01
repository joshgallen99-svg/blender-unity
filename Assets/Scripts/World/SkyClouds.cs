using UnityEngine;
using UnityEngine.Rendering;

namespace Offroad.World
{
    /// <summary>
    /// Draws the procedural cloud layer (Clouds.shader) on a dome that follows the camera. The shader
    /// projects each view ray onto a high cloud plane, so the dome's size doesn't matter.
    /// </summary>
    public class SkyClouds : MonoBehaviour
    {
        public Material material;
        Mesh _dome;

        void Awake() => _dome = BuildDome(500f, 24, 10);

        void LateUpdate()
        {
            var cam = Camera.main;
            if (!cam || !material || _dome == null) return;
            var p = cam.transform.position;
            var rp = new RenderParams(material)
            {
                worldBounds = new Bounds(p, Vector3.one * 2000f),
                shadowCastingMode = ShadowCastingMode.Off,
                receiveShadows = false,
                layer = gameObject.layer,
            };
            Graphics.RenderMesh(rp, _dome, 0, Matrix4x4.Translate(p));
        }

        static Mesh BuildDome(float radius, int seg, int rings)
        {
            var verts = new Vector3[(rings + 1) * seg];
            var tris = new int[rings * seg * 6];
            for (int r = 0; r <= rings; r++)
            {
                float el = Mathf.Lerp(-0.05f, Mathf.PI / 2f, r / (float)rings);
                for (int s = 0; s < seg; s++)
                {
                    float az = s * Mathf.PI * 2f / seg;
                    verts[r * seg + s] = new Vector3(Mathf.Cos(el) * Mathf.Sin(az), Mathf.Sin(el), Mathf.Cos(el) * Mathf.Cos(az)) * radius;
                }
            }
            int t = 0;
            for (int r = 0; r < rings; r++)
            for (int s = 0; s < seg; s++)
            {
                int a = r * seg + s, b = r * seg + (s + 1) % seg, c = a + seg, d = b + seg;
                tris[t++] = a; tris[t++] = c; tris[t++] = d;
                tris[t++] = a; tris[t++] = d; tris[t++] = b;
            }
            var m = new Mesh { name = "Cloud Dome", vertices = verts, triangles = tris };
            m.RecalculateBounds();
            return m;
        }
    }
}
