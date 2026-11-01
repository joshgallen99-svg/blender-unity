using System.Collections.Generic;
using Offroad.Vehicles;
using UnityEngine;

namespace Offroad.World
{
    /// <summary>
    /// Tyre tracks pressed into the ground. Keeps a trail map (a small render texture that follows the
    /// player, ~8 cm per texel) into which every grounded wheel stamps its contact patch each frame:
    /// R = how deep the ground was pushed down, G = the rim of soil squeezed up beside the tyre.
    /// Ground shaders read it (see Trails.hlsl) to sink ruts with parallax, shade their walls and darken
    /// or wet them; how deep a rut looks depends on the ground (sand and mud deep, gravel shallow,
    /// rock none). When the vehicle nears the edge, the map is re-centred and its contents shifted.
    /// </summary>
    [DefaultExecutionOrder(200)]
    public class GroundTrails : MonoBehaviour
    {
        [Tooltip("Area covered by the trail map (metres).")]
        public float size = 80f;
        public int resolution = 1024;
        [Tooltip("Re-centre once the vehicle is this far from the centre (metres).")]
        public float recenterDistance = 18f;
        public Shader stampShader;

        static readonly int TrailMapId = Shader.PropertyToID("_OffroadTrailMap");
        static readonly int TrailRectId = Shader.PropertyToID("_OffroadTrailRect");
        static readonly int ShiftId = Shader.PropertyToID("_Shift");

        RenderTexture _rt, _swap;
        Material _mat;
        Vector2 _origin;           // world xz of the map's lower-left corner
        readonly List<OffroadVehicle> _vehicles = new List<OffroadVehicle>();
        readonly Dictionary<OffroadVehicle.Wheel, Vector3> _last = new Dictionary<OffroadVehicle.Wheel, Vector3>();
        bool _supported = true;

        public RenderTexture Map => _rt;

        void OnEnable()
        {
            if (stampShader == null) stampShader = Shader.Find("Hidden/Offroad/TrailStamp");
            if (stampShader == null || !stampShader.isSupported) { _supported = false; Disable(); return; }
            var fmt = SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.RG16) ? RenderTextureFormat.RG16 : RenderTextureFormat.ARGB32;
            _rt = Create(fmt, "Ground Trails");
            _swap = Create(fmt, "Ground Trails (swap)");
            _mat = new Material(stampShader) { hideFlags = HideFlags.HideAndDontSave };
            Clear(_rt);
            Clear(_swap);
            _vehicles.Clear();
            _vehicles.AddRange(FindObjectsByType<OffroadVehicle>(FindObjectsSortMode.None));
            if (_vehicles.Count > 0) Center(_vehicles[0].transform.position);
            Publish();
        }

        void OnDisable()
        {
            Disable();
            if (_rt) { _rt.Release(); Destroy(_rt); }
            if (_swap) { _swap.Release(); Destroy(_swap); }
            if (_mat) Destroy(_mat);
            _last.Clear();
        }

        static void Disable()
        {
            Shader.SetGlobalVector(TrailRectId, Vector4.zero);
            Shader.SetGlobalTexture(TrailMapId, Texture2D.blackTexture);
        }

        RenderTexture Create(RenderTextureFormat fmt, string name)
        {
            var rt = new RenderTexture(resolution, resolution, 0, fmt, RenderTextureReadWrite.Linear)
            {
                name = name, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, useMipMap = false,
            };
            rt.Create();
            return rt;
        }

        static void Clear(RenderTexture rt)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            GL.Clear(false, true, Color.clear);
            RenderTexture.active = prev;
        }

        void Center(Vector3 p)
        {
            float texel = size / resolution;
            _origin = new Vector2(Mathf.Round((p.x - size * 0.5f) / texel) * texel, Mathf.Round((p.z - size * 0.5f) / texel) * texel);
        }

        void Publish()
        {
            Shader.SetGlobalTexture(TrailMapId, _rt);
            Shader.SetGlobalVector(TrailRectId, new Vector4(_origin.x, _origin.y, size, 1f));
        }

        void LateUpdate()
        {
            if (!_supported || _rt == null || _vehicles.Count == 0) return;
            var lead = _vehicles[0];
            if (!lead) return;

            // Keep the map centred on the vehicle: shift the existing tracks when re-centring.
            Vector3 vp = lead.transform.position;
            Vector2 c = _origin + Vector2.one * (size * 0.5f);
            if (Mathf.Abs(vp.x - c.x) > recenterDistance || Mathf.Abs(vp.z - c.y) > recenterDistance)
            {
                Vector2 old = _origin;
                Center(vp);
                Vector2 shift = (_origin - old) / size;      // in uv
                if (Mathf.Abs(shift.x) >= 1f || Mathf.Abs(shift.y) >= 1f) Clear(_swap);
                else
                {
                    _mat.SetVector(ShiftId, new Vector4(shift.x, shift.y, 0f, 0f));
                    Graphics.Blit(_rt, _swap, _mat, 1);
                }
                (_rt, _swap) = (_swap, _rt);
                Publish();
            }

            // Stamp every grounded wheel: a quad from where it touched last frame to where it is now.
            var prev = RenderTexture.active;
            RenderTexture.active = _rt;
            GL.PushMatrix();
            GL.LoadOrtho();
            _mat.SetPass(0);
            GL.Begin(GL.QUADS);
            foreach (var v in _vehicles)
            {
                if (!v) continue;
                float halfW = Mathf.Max(0.1f, v.tireWidth * 0.5f);
                float staticLoad = v.Body ? v.Body.mass * 9.81f / Mathf.Max(1, v.wheels.Length) : 4000f;
                foreach (var w in v.wheels)
                {
                    if (!w.grounded || w.load <= 1f) { _last.Remove(w); continue; }
                    Vector3 p = w.contactPoint;
                    bool seen = _last.TryGetValue(w, out var a);
                    if (seen && (a - p).sqrMagnitude < 0.0004f && w.slip < 0.05f) continue;   // parked: already stamped
                    if (!seen || (a - p).sqrMagnitude > 4f) a = p;
                    _last[w] = p;
                    float pressure = Mathf.Clamp01(0.55f + 0.45f * w.load / staticLoad);
                    Vector3 heading = w.front ? Quaternion.AngleAxis(v.SteerAngle, Vector3.up) * v.transform.forward : v.transform.forward;
                    Stamp(a, p, heading, halfW, pressure, 1f + Mathf.Clamp01(w.slip) * 0.6f);
                }
            }
            GL.End();
            GL.PopMatrix();
            RenderTexture.active = prev;
        }

        /// <summary>One tyre stamp from a to b. TexCoord.x = across (-1.6..1.6 half-widths), .y = pressure, .z = churn.</summary>
        void Stamp(Vector3 a, Vector3 b, Vector3 heading, float halfW, float pressure, float churn)
        {
            Vector2 dir = new Vector2(b.x - a.x, b.z - a.z);
            float len = dir.magnitude;
            if (len < 0.02f) dir = new Vector2(heading.x, heading.z);
            dir.Normalize();
            if (dir.sqrMagnitude < 0.5f) dir = Vector2.up;
            Vector2 side = new Vector2(dir.y, -dir.x) * (halfW * 1.6f);
            Vector2 ext = dir * 0.16f;                       // half the contact patch beyond each end
            Vector2 A = new Vector2(a.x, a.z) - ext, B = new Vector2(b.x, b.z) + ext;
            Vertex(A - side, -1.6f, pressure, churn);
            Vertex(A + side, 1.6f, pressure, churn);
            Vertex(B + side, 1.6f, pressure, churn);
            Vertex(B - side, -1.6f, pressure, churn);
        }

        void Vertex(Vector2 world, float across, float pressure, float churn)
        {
            GL.TexCoord3(across, pressure, churn);
            GL.Vertex3((world.x - _origin.x) / size, (world.y - _origin.y) / size, 0f);
        }
    }
}
