// Tyre trails pressed into the ground (written by GroundTrails.cs). Ground shaders call SampleTrail
// with how deep the local ground lets a tyre sink (sand/mud ~6-10 cm, gravel ~2 cm, rock 0) and get
// back the trail height (negative in ruts, positive on the rims) and its slope for lighting.
#ifndef OFFROAD_TRAILS_INCLUDED
#define OFFROAD_TRAILS_INCLUDED

TEXTURE2D(_OffroadTrailMap); SAMPLER(sampler_OffroadTrailMap);
float4 _OffroadTrailMap_TexelSize;
float4 _OffroadTrailRect;      // origin x, origin z, size (m), enabled

struct TrailInfo
{
    half height;    // metres relative to the untouched ground (negative in ruts)
    half depth;     // 0..1 how pressed the ground is here
    half rim;       // 0..1 squeezed-up rim
    half2 grad;     // d height / d (x, z)
};

half TrailHeight(half2 c, half maxDepth) { return (c.g * 0.4 * (1.0 - c.r) - c.r) * maxDepth; }

float2 TrailUV(float2 xz) { return (xz - _OffroadTrailRect.xy) / max(_OffroadTrailRect.z, 1.0); }

bool TrailActive(float2 xz)
{
    float2 uv = TrailUV(xz);
    return _OffroadTrailRect.w > 0.5 && uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0;
}

TrailInfo SampleTrail(float2 xz, half maxDepth)
{
    TrailInfo t = (TrailInfo)0;
    if (maxDepth <= 0.001 || !TrailActive(xz)) return t;
    float2 uv = TrailUV(xz);
    half2 c = SAMPLE_TEXTURE2D_LOD(_OffroadTrailMap, sampler_OffroadTrailMap, uv, 0).rg;
    if (c.r + c.g < 0.004) return t;
    float step = max(_OffroadTrailMap_TexelSize.x, 1.0 / 2048.0) * 1.5;
    half2 cx = SAMPLE_TEXTURE2D_LOD(_OffroadTrailMap, sampler_OffroadTrailMap, uv + float2(step, 0), 0).rg;
    half2 cz = SAMPLE_TEXTURE2D_LOD(_OffroadTrailMap, sampler_OffroadTrailMap, uv + float2(0, step), 0).rg;
    // Fade out towards the edge of the map so re-centring never shows a seam.
    float2 e = min(uv, 1.0 - uv);
    half fade = saturate(min(e.x, e.y) * 16.0);
    half h = TrailHeight(c, maxDepth);
    float metres = step * _OffroadTrailRect.z;
    t.height = h * fade;
    t.depth = c.r * fade;
    t.rim = c.g * (1.0 - c.r) * fade;
    t.grad = half2(TrailHeight(cx, maxDepth) - h, TrailHeight(cz, maxDepth) - h) / metres * fade;
    return t;
}

/// Parallax: where the visible point of a rut floor lies, seen along the view ray (2 refinement steps).
float2 TrailParallax(float2 xz, float3 viewDirWS, half maxDepth)
{
    if (maxDepth <= 0.001 || !TrailActive(xz)) return xz;
    float2 slope = viewDirWS.xz / max(viewDirWS.y, 0.3);
    float2 q = xz;
    [unroll] for (int k = 0; k < 2; k++)
    {
        half2 c = SAMPLE_TEXTURE2D_LOD(_OffroadTrailMap, sampler_OffroadTrailMap, TrailUV(q), 0).rg;
        q = xz + slope * TrailHeight(c, maxDepth);
    }
    return q;
}

#endif
