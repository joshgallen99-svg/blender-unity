// Shared desert look for terrain and rock shaders: sandstone strata colours, triplanar helpers,
// and access to the terrain heightmap so rocks can blend into the sand where they meet the ground.
#ifndef OFFROAD_DESERT_INCLUDED
#define OFFROAD_DESERT_INCLUDED

// Linear-space palette sampled from Valley of Fire / The Wave sandstone.
static const half3 kStrataRed    = half3(0.30, 0.050, 0.020);
static const half3 kStrataRust   = half3(0.50, 0.110, 0.035);
static const half3 kStrataOrange = half3(0.68, 0.240, 0.090);
static const half3 kStrataSalmon = half3(0.74, 0.380, 0.190);
static const half3 kStrataCream  = half3(0.80, 0.590, 0.360);
static const half3 kStrataPale   = half3(0.85, 0.700, 0.560);

// Globals set by TerrainGlobals.cs.
TEXTURE2D(_OffroadTerrainHeight); SAMPLER(sampler_OffroadTerrainHeight);
float4 _OffroadTerrainRect;     // xz origin, xz size
float4 _OffroadTerrainHeightParams; // x: height range, y: terrain y position, z: has heightmap (0/1)
float _OffroadStrataFreq;       // bands per metre
float _OffroadStrataWarp;

float OffroadHash(float n) { return frac(sin(n * 12.9898) * 43758.5453); }

half3 StrataBand(float i)
{
    float h = OffroadHash(i);
    if (h < 0.22) return kStrataRed;
    if (h < 0.48) return kStrataRust;
    if (h < 0.70) return kStrataOrange;
    if (h < 0.84) return kStrataSalmon;
    if (h < 0.95) return kStrataCream;
    return kStrataPale;
}

/// World-space sandstone colour: soft horizontal bands, bent by large-scale noise (cross-bedding).
half3 StrataColor(float3 positionWS, half warpNoise)
{
    float freq = _OffroadStrataFreq > 0 ? _OffroadStrataFreq : 0.33;
    float warpAmp = _OffroadStrataWarp > 0 ? _OffroadStrataWarp : 1.6;
    float t = positionWS.y * freq
            + (warpNoise - 0.5) * warpAmp
            + sin(positionWS.x * 0.021 + positionWS.z * 0.013) * 0.35;
    float i = floor(t);
    float f = frac(t);
    half3 a = StrataBand(i);
    half3 b = StrataBand(i + 1);
    half3 c = lerp(a, b, smoothstep(0.72, 1.0, f));
    // Fine laminations inside each band.
    c *= 0.92 + 0.08 * sin(t * 6.2831 * 4.0 + warpNoise * 3.0);
    return c;
}

half3 TriplanarWeights(half3 n, half sharpness)
{
    half3 w = pow(abs(n), sharpness);
    return w / max(w.x + w.y + w.z, 1e-4);
}

half4 TriplanarSample(TEXTURE2D_PARAM(tex, samp), float3 p, half3 w)
{
    return SAMPLE_TEXTURE2D(tex, samp, p.zy) * w.x
         + SAMPLE_TEXTURE2D(tex, samp, p.xz) * w.y
         + SAMPLE_TEXTURE2D(tex, samp, p.xy) * w.z;
}

/// Triplanar normal map ("whiteout" blend) into world space.
half3 TriplanarNormal(TEXTURE2D_PARAM(tex, samp), float3 p, half3 n, half3 w, half strength)
{
    half3 tx = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.zy), strength);
    half3 ty = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xz), strength);
    half3 tz = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xy), strength);
    half3 s = sign(n);
    tx.z *= s.x; ty.z *= s.y; tz.z *= s.z;
    half3 nx = half3(tx.xy + n.zy, abs(tx.z) * n.x);
    half3 ny = half3(ty.xy + n.xz, abs(ty.z) * n.y);
    half3 nz = half3(tz.xy + n.xy, abs(tz.z) * n.z);
    return normalize(nx.zyx * w.x + ny.xzy * w.y + nz.xyz * w.z);
}

/// Top-down (XZ) projected normal map combined with the surface normal.
half3 TopNormal(half3 tn, half3 n)
{
    return normalize(half3(n.x + tn.x, n.y, n.z + tn.y));
}

/// Height of the terrain under a world position (or -1e5 if no heightmap is set).
float TerrainHeightAt(float3 positionWS)
{
    if (_OffroadTerrainHeightParams.z < 0.5) return -1e5;
    float2 uv = (positionWS.xz - _OffroadTerrainRect.xy) / _OffroadTerrainRect.zw;
    float h = SAMPLE_TEXTURE2D_LOD(_OffroadTerrainHeight, sampler_OffroadTerrainHeight, uv, 0).r;
    return _OffroadTerrainHeightParams.y + h * _OffroadTerrainHeightParams.x;
}

/// Height-aware blend of two layers: the higher texel (plus weight) wins, with a soft transition.
half HeightBlend(half wA, half hA, half wB, half hB, half depth)
{
    half a = wA + hA;
    half b = wB + hB;
    half m = max(a, b) - depth;
    half ba = max(a - m, 0);
    half bb = max(b - m, 0);
    return bb / max(ba + bb, 1e-4);   // weight of B
}

#endif
