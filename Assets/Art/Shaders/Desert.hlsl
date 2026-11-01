// Shared desert look for terrain and rock shaders: sandstone strata colours, triplanar helpers,
// and access to the terrain heightmap so rocks can blend into the sand where they meet the ground.
#ifndef OFFROAD_DESERT_INCLUDED
#define OFFROAD_DESERT_INCLUDED

// Linear-space palette sampled from Valley of Fire / The Wave sandstone.
static const half3 kStrataRed    = half3(0.26, 0.040, 0.018);
static const half3 kStrataRust   = half3(0.48, 0.100, 0.032);
static const half3 kStrataOrange = half3(0.68, 0.240, 0.085);
static const half3 kStrataSalmon = half3(0.76, 0.400, 0.200);
static const half3 kStrataCream  = half3(0.82, 0.620, 0.400);
static const half3 kStrataPale   = half3(0.88, 0.760, 0.620);

// Globals set by TerrainGlobals.cs.
TEXTURE2D(_OffroadTerrainHeight); SAMPLER(sampler_OffroadTerrainHeight);
float4 _OffroadTerrainRect;     // xz origin, xz size
float4 _OffroadTerrainHeightParams; // x: height range, y: terrain y position, z: has heightmap (0/1)
float _OffroadStrataFreq;       // bands per metre
float _OffroadStrataWarp;
// Hazards over the terrain rect: R wet mud, G quicksand, B washboard, A standing water.
TEXTURE2D(_OffroadHazard); SAMPLER(sampler_OffroadHazard);
float _OffroadHazardOn;

// Aerial perspective: distance haze that turns towards the sun's glow colour when looking sunward
// (matching the sky's glow) and thins out higher up, so distant peaks stay crisper than the valley.
float4 _OffroadSunFogColor;     // rgb: haze colour toward the sun, a: strength (set by Atmosphere.cs)

half3 OffroadFog(half3 col, float3 positionWS, half fogCoord)
{
#if defined(FOG_LINEAR) || defined(FOG_EXP) || defined(FOG_EXP2)
    half visible = ComputeFogIntensity(fogCoord);
    float3 v = normalize(positionWS - _WorldSpaceCameraPos);
    half sunward = pow(saturate(dot(v, _MainLightPosition.xyz)), 5.0) * _OffroadSunFogColor.a;
    half3 fogCol = lerp(unity_FogColor.rgb, _OffroadSunFogColor.rgb, sunward);
    visible = lerp(visible, 1.0, saturate((positionWS.y - _WorldSpaceCameraPos.y) / 450.0) * 0.35);
    return lerp(fogCol, col, visible);
#else
    return col;
#endif
}

float OffroadHash(float n) { return frac(sin(n * 12.9898) * 43758.5453); }

half3 StrataBand(float i)
{
    float h = OffroadHash(i * 1.37 + 0.11);
    if (h < 0.24) return kStrataRed;
    if (h < 0.55) return kStrataRust;
    if (h < 0.79) return kStrataOrange;
    if (h < 0.91) return kStrataSalmon;
    if (h < 0.975) return kStrataCream;
    return kStrataPale;
}

/// Bleached (Aztec-style) sandstone: mostly cream and pale, the odd salmon bed.
half3 StrataBandBleached(float i)
{
    float h = OffroadHash(i * 2.11 + 0.7);
    if (h < 0.45) return kStrataPale;
    if (h < 0.85) return kStrataCream;
    return kStrataSalmon;
}

/// World-space sandstone colour: horizontal beds of irregular thickness, bent by large-scale noise
/// (cross-bedding), with thin contrasting seams and fine laminations. zoneNoise (0..1, very large
/// scale) bleaches the upper parts of some areas to cream, like Valley of Fire's White Domes.
half3 StrataColor(float3 positionWS, half warpNoise, half zoneNoise)
{
    float freq = _OffroadStrataFreq > 0 ? _OffroadStrataFreq : 0.33;
    float warpAmp = _OffroadStrataWarp > 0 ? _OffroadStrataWarp : 1.6;
    float t = positionWS.y * freq
            + (warpNoise - 0.5) * warpAmp
            + sin(positionWS.x * 0.021 + positionWS.z * 0.013) * 0.35;
    // Monotonic warp (derivative stays > 0): bed thickness ranges from thin seams to thick beds.
    t += 0.42 * sin(t * 1.7 + 1.3) + 0.27 * sin(t * 0.61 + 4.1);
    float i = floor(t);
    float f = frac(t);
    half3 c = lerp(StrataBand(i), StrataBand(i + 1), smoothstep(0.80, 1.0, f));

    // Thin seams: a darker iron band or a pale bleached band inside some beds.
    float seamPick = OffroadHash(i + 91.7);
    float seamPos = 0.25 + 0.5 * OffroadHash(i + 13.3);
    half seam = 1.0 - smoothstep(0.015, 0.05, abs(f - seamPos));
    half3 seamCol = seamPick > 0.9 ? kStrataPale : kStrataRed * 0.85;
    c = lerp(c, seamCol, seam * step(0.7, seamPick) * 0.8);

    // Fine laminations inside each bed.
    c *= 0.9 + 0.1 * sin(t * 6.2831 * 5.0 + warpNoise * 3.0);

    // Bleached caps above a wavy line, only in some zones.
    half capY = 62.0 + 34.0 * (1.0 - zoneNoise) + (warpNoise - 0.5) * 14.0;
    half bleach = smoothstep(0.5, 0.7, zoneNoise) * smoothstep(capY - 4.0, capY + 6.0, positionWS.y);
    half3 capCol = lerp(StrataBandBleached(i), StrataBandBleached(i + 1), smoothstep(0.75, 1.0, f));
    c = lerp(c, capCol * (0.93 + 0.07 * sin(t * 31.4 + warpNoise * 3.0)), bleach * 0.9);
    return c;
}

// ---------------------------------------------------------------------------------------------
// Hex-tile stochastic texturing (Mikkelsen 2022, "Practical Real-Time Hex-Tiling", JCGT 11(2)).
// The plane is covered by hexagons; each samples the texture with its own random offset and
// rotation, and neighbours blend by barycentric weight sharpened by the texel height, so
// tiling repetition disappears. 3 taps per texture instead of 1.

struct HexTiles
{
    float2 uv1, uv2, uv3;
    float2 cs1, cs2, cs3;      // per-hexagon rotation (cos, sin)
    float2 dx, dy;             // screen-space derivatives of the unrotated uv
    float3 w;                  // barycentric weights
};

float2 HexHash22(float2 p)
{
    float3 p3 = frac(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.xx + p3.yz) * p3.zy);
}

float2 HexRotate(float2 v, float2 cs) { return float2(v.x * cs.x - v.y * cs.y, v.x * cs.y + v.y * cs.x); }

HexTiles HexSetup(float2 uv, float2 dx, float2 dy, float rotStrength)
{
    HexTiles h;
    const float scale = 3.4641016;   // 2 * sqrt(3)
    float2 st = uv * scale;
    float2 skewed = float2(st.x - 0.57735027 * st.y, 1.15470054 * st.y);
    float2 baseId = floor(skewed);
    float3 temp = float3(frac(skewed), 0);
    temp.z = 1.0 - temp.x - temp.y;
    float s = step(0.0, -temp.z);
    float s2 = 2.0 * s - 1.0;
    h.w = float3(-temp.z * s2, s - temp.y * s2, s - temp.x * s2);
    float2 v1 = baseId + float2(s, s);
    float2 v2 = baseId + float2(s, 1.0 - s);
    float2 v3 = baseId + float2(1.0 - s, s);

    float a1 = (HexHash22(v1 + 17.0).x - 0.5) * 6.2831853 * rotStrength;
    float a2 = (HexHash22(v2 + 17.0).x - 0.5) * 6.2831853 * rotStrength;
    float a3 = (HexHash22(v3 + 17.0).x - 0.5) * 6.2831853 * rotStrength;
    h.cs1 = float2(cos(a1), sin(a1));
    h.cs2 = float2(cos(a2), sin(a2));
    h.cs3 = float2(cos(a3), sin(a3));

    float2 c1 = float2(v1.x + 0.5 * v1.y, 0.8660254 * v1.y) / scale;
    float2 c2 = float2(v2.x + 0.5 * v2.y, 0.8660254 * v2.y) / scale;
    float2 c3 = float2(v3.x + 0.5 * v3.y, 0.8660254 * v3.y) / scale;
    h.uv1 = HexRotate(uv - c1, h.cs1) + c1 + HexHash22(v1);
    h.uv2 = HexRotate(uv - c2, h.cs2) + c2 + HexHash22(v2);
    h.uv3 = HexRotate(uv - c3, h.cs3) + c3 + HexHash22(v3);
    h.dx = dx;
    h.dy = dy;
    return h;
}

/// Hex-tiled sample of a texture with height in alpha. Returns the blend weights for HexNormal.
half4 HexSample(TEXTURE2D_PARAM(tex, samp), HexTiles h, half heightContrast, out half3 weights)
{
    half4 c1 = SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv1, HexRotate(h.dx, h.cs1), HexRotate(h.dy, h.cs1));
    half4 c2 = SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv2, HexRotate(h.dx, h.cs2), HexRotate(h.dy, h.cs2));
    half4 c3 = SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv3, HexRotate(h.dx, h.cs3), HexRotate(h.dy, h.cs3));
    float3 w = h.w * h.w;
    w = w * w * w * h.w;                                                   // ^7
    w *= lerp(1.0, float3(c1.a, c2.a, c3.a) + 0.05, heightContrast);
    w /= max(w.x + w.y + w.z, 1e-6);
    weights = (half3)w;
    return c1 * weights.x + c2 * weights.y + c3 * weights.z;
}

/// Matching hex-tiled tangent-space normal (xy rotated back into the unrotated uv frame).
half3 HexNormal(TEXTURE2D_PARAM(tex, samp), HexTiles h, half3 weights, half strength)
{
    half3 n1 = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv1, HexRotate(h.dx, h.cs1), HexRotate(h.dy, h.cs1)), strength);
    half3 n2 = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv2, HexRotate(h.dx, h.cs2), HexRotate(h.dy, h.cs2)), strength);
    half3 n3 = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, h.uv3, HexRotate(h.dx, h.cs3), HexRotate(h.dy, h.cs3)), strength);
    n1.xy = HexRotate(n1.xy, h.cs1 * float2(1, -1));
    n2.xy = HexRotate(n2.xy, h.cs2 * float2(1, -1));
    n3.xy = HexRotate(n3.xy, h.cs3 * float2(1, -1));
    return normalize(n1 * weights.x + n2 * weights.y + n3 * weights.z);
}

// ---------------------------------------------------------------------------------------------
// Wind ripples, drawn in world space so they never repeat. Asymmetric profile (long gentle
// windward slope, short steep lee), sinuous crests from a warp noise, faded out before they alias.
// Returns the ripple height (0..1) and writes a top-down tangent normal offset (xy).

half SandRipples(float2 xz, half warp, half amount, out half2 normalXY)
{
    const float2 windDir = float2(0.8, 0.6);
    const float wavelength = 0.34;
    float phase = dot(xz, windDir) / wavelength + warp * 9.0;
    float fw = fwidth(phase);
    half fade = amount * saturate(1.6 - fw * 3.0);
    float s = frac(phase);
    // Slope of the profile: rises over 75% of the period, drops over the last 25%.
    half lee = smoothstep(0.70, 0.80, s) * (1.0 - smoothstep(0.93, 1.0, s));
    half slope = lerp(1.0, -3.0, lee);
    half height = s < 0.75 ? s / 0.75 : (1.0 - s) / 0.25;
    // Height gradient = profile slope * windDir * (amplitude / wavelength), amplitude ~1.5 cm.
    normalXY = -windDir * (slope * 0.045 * fade);
    return height * fade;
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

/// Triplanar sampling with explicit derivatives (safe inside dynamic branches).
half4 TriplanarSampleGrad(TEXTURE2D_PARAM(tex, samp), float3 p, float3 dx, float3 dy, half3 w)
{
    return SAMPLE_TEXTURE2D_GRAD(tex, samp, p.zy, dx.zy, dy.zy) * w.x
         + SAMPLE_TEXTURE2D_GRAD(tex, samp, p.xz, dx.xz, dy.xz) * w.y
         + SAMPLE_TEXTURE2D_GRAD(tex, samp, p.xy, dx.xy, dy.xy) * w.z;
}

half3 TriplanarNormalGrad(TEXTURE2D_PARAM(tex, samp), float3 p, float3 dx, float3 dy, half3 n, half3 w, half strength)
{
    half3 tx = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, p.zy, dx.zy, dy.zy), strength);
    half3 ty = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, p.xz, dx.xz, dy.xz), strength);
    half3 tz = UnpackNormalScale(SAMPLE_TEXTURE2D_GRAD(tex, samp, p.xy, dx.xy, dy.xy), strength);
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
