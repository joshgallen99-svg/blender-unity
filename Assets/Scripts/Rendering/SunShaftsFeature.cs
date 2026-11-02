using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.RenderGraphModule;
using UnityEngine.Rendering.RenderGraphModule.Util;
using UnityEngine.Rendering.Universal;

namespace Offroad.Rendering
{
    /// <summary>Region and settings knobs for the light rays (set by Atmosphere and GameSettings).</summary>
    public static class SunShafts
    {
        public static bool Enabled = true;
        public static Color Tint = new Color(1f, 0.86f, 0.66f);
        public static float Intensity = 0.55f;
        public static float Threshold = 1.1f;
        public static float Radius = 0.55f;
    }

    /// <summary>
    /// Light rays: where something partly blocks the sun (rocks, ridges, tree canopy), beams fan out from
    /// it. Three cheap passes at half resolution (see SunShafts.shader); skipped when the sun is behind
    /// the camera or the effect is off (Battery Saver, post effects off).
    /// </summary>
    public class SunShaftsFeature : ScriptableRendererFeature
    {
        public Shader shader;
        Material _material;
        SunShaftsPass _pass;

        public override void Create()
        {
            _pass = new SunShaftsPass { renderPassEvent = RenderPassEvent.BeforeRenderingPostProcessing };
        }

        public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
        {
            if (!SunShafts.Enabled || SunShafts.Intensity <= 0f) return;
            var cam = renderingData.cameraData.camera;
            if (cam == null || renderingData.cameraData.cameraType != CameraType.Game) return;
            if (_material == null)
            {
                if (shader == null) shader = Shader.Find("Hidden/Offroad/SunShafts");
                if (shader == null || !shader.isSupported) return;
                _material = CoreUtils.CreateEngineMaterial(shader);
            }
            if (_pass.Setup(_material, cam)) renderer.EnqueuePass(_pass);
        }

        protected override void Dispose(bool disposing) => CoreUtils.Destroy(_material);

        class SunShaftsPass : ScriptableRenderPass
        {
            static readonly int SunScreenId = Shader.PropertyToID("_SunScreen");
            static readonly int ParamsId = Shader.PropertyToID("_ShaftParams");
            static readonly int TintId = Shader.PropertyToID("_ShaftTint");
            Material _mat;

            public bool Setup(Material mat, Camera cam)
            {
                _mat = mat;
                var sun = RenderSettings.sun;
                if (sun == null || !sun.isActiveAndEnabled) return false;
                Vector3 toSun = -sun.transform.forward;
                if (toSun.y < -0.05f) return false;                       // sun below the horizon
                Vector3 vp = cam.WorldToViewportPoint(cam.transform.position + toSun * 1000f);
                if (vp.z <= 0f) return false;                             // behind the camera
                // Fade out as the sun leaves the screen.
                float off = Mathf.Max(Mathf.Abs(vp.x - 0.5f), Mathf.Abs(vp.y - 0.5f)) - 0.5f;
                float visible = Mathf.Clamp01(1f - off * 2.5f);
                if (visible <= 0.01f) return false;
                mat.SetVector(SunScreenId, new Vector4(vp.x, vp.y, visible, cam.aspect));
                mat.SetVector(ParamsId, new Vector4(SunShafts.Threshold, SunShafts.Radius, 1f / 16f, 0.94f));
                var tint = SunShafts.Tint.linear * SunShafts.Intensity;
                mat.SetVector(TintId, new Vector4(tint.r, tint.g, tint.b, 1f));
                return true;
            }

            public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)
            {
                var resources = frameData.Get<UniversalResourceData>();
                if (resources.isActiveTargetBackBuffer) return;
                var source = resources.activeColorTexture;
                var desc = renderGraph.GetTextureDesc(source);
                desc.width = Mathf.Max(1, desc.width / 2);
                desc.height = Mathf.Max(1, desc.height / 2);
                desc.depthBufferBits = DepthBits.None;
                desc.msaaSamples = MSAASamples.None;
                desc.clearBuffer = false;
                desc.filterMode = FilterMode.Bilinear;
                desc.name = "Sun Shafts A";
                var a = renderGraph.CreateTexture(desc);
                desc.name = "Sun Shafts B";
                var b = renderGraph.CreateTexture(desc);

                renderGraph.AddBlitPass(new RenderGraphUtils.BlitMaterialParameters(source, a, _mat, 0), "Sun Shafts Prefilter");
                renderGraph.AddBlitPass(new RenderGraphUtils.BlitMaterialParameters(a, b, _mat, 1), "Sun Shafts Radial 1");
                renderGraph.AddBlitPass(new RenderGraphUtils.BlitMaterialParameters(b, a, _mat, 1), "Sun Shafts Radial 2");
                // Additive composite onto the scene. ReadWrite keeps the scene (a plain blit pass declares
                // Write-only, and tile-based GPUs such as Apple's then don't load what was there).
                using (var builder = renderGraph.AddRasterRenderPass<CompositeData>("Sun Shafts Composite", out var data))
                {
                    data.rays = a;
                    data.material = _mat;
                    builder.UseTexture(a, AccessFlags.Read);
                    builder.SetRenderAttachment(source, 0, AccessFlags.ReadWrite);
                    builder.SetRenderFunc((CompositeData d, RasterGraphContext ctx) =>
                        Blitter.BlitTexture(ctx.cmd, d.rays, new Vector4(1f, 1f, 0f, 0f), d.material, 2));
                }
            }

            class CompositeData
            {
                public TextureHandle rays;
                public Material material;
            }
        }
    }
}
