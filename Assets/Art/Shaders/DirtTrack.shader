// Dirt track decal: a ribbon draped over the terrain (see PrototypeSceneBuilder.CreateTracks) that
// draws two compacted wheel ruts, a raised crown, loose sand at ragged edges, washboard corrugations
// and wet mud / water in the ruts where the hazard map says so. Alpha-blended over the terrain, no
// depth write, drawn right after the terrain so everything else sorts against the terrain's depth.
//
// Vertex data: uv0 = (metres from the centre line, metres along), uv1.x = half width (m),
// colour = (washboard 0..1, wear 0..1, fade 0..1), tangent = the across-track direction.
Shader "Offroad/DirtTrack"
{
    Properties
    {
        _DirtTex ("Track Dirt (height in A)", 2D) = "white" {}
        [Normal] _DirtNrm ("Track Dirt Normal", 2D) = "bump" {}
        _SandTex ("Loose Sand", 2D) = "white" {}
        _Macro ("Macro Variation", 2D) = "gray" {}
        _DirtScale ("Dirt Tile (m)", Float) = 3
        _SandScale ("Sand Tile (m)", Float) = 3.5
        _RutGauge ("Rut Offset From Centre (m)", Float) = 0.8
        _RutWidth ("Rut Width (m)", Float) = 0.26
        _RutDepth ("Rut Depth (m)", Float) = 0.07
        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry-50" "IgnoreProjector" = "True" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Offset -1, -1

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Desert.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float _DirtScale, _SandScale;
                float _RutGauge, _RutWidth, _RutDepth;
                half _NormalStrength;
            CBUFFER_END

            TEXTURE2D(_DirtTex); SAMPLER(sampler_DirtTex);
            TEXTURE2D(_DirtNrm); SAMPLER(sampler_DirtNrm);
            TEXTURE2D(_SandTex); SAMPLER(sampler_SandTex);
            TEXTURE2D(_Macro); SAMPLER(sampler_Macro);

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv0 : TEXCOORD0;
                float2 uv1 : TEXCOORD1;
                half4 color : COLOR;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 acrossWS : TEXCOORD2;
                float4 track : TEXCOORD3;      // lateral m, along m, half width m, fog
                half4 color : COLOR;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs pos = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = pos.positionCS;
                o.positionWS = pos.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.acrossWS = TransformObjectToWorldDir(v.tangentOS.xyz);
                o.track = float4(v.uv0.x, v.uv0.y, max(v.uv1.x, 0.5), ComputeFogFactor(pos.positionCS.z));
                o.color = v.color;
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS);
                half3 across = normalize(i.acrossWS - n * dot(i.acrossWS, n));
                half3 alongDir = cross(across, n);
                float lat = i.track.x;
                float along = i.track.y;
                float halfW = i.track.z;
                half wash = i.color.r;
                half wear = i.color.g;
                half fade = i.color.b;

                half4 macro = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 256.0);
                half4 macro2 = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 37.0 + 0.37);
                half4 macroS = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 9.0 + 0.13);

                // Ragged edges where loose sand creeps in.
                float e = abs(lat) / halfW + ((macroS.r - 0.5) * 0.5 + (macro2.b - 0.5) * 0.4) * 0.35;
                half alpha = (1.0 - smoothstep(0.74, 1.15, e)) * fade;

                // --- Profile across the track: two ruts, a crown between them, berms at the edges.
                float g = _RutGauge;
                float dl = abs(lat) - g;
                float w2 = _RutWidth * _RutWidth;
                float rut = exp(-dl * dl / w2) * (0.75 + 0.25 * wear);
                float crown = exp(-lat * lat / 0.2025);
                float sgn = lat < 0 ? -1.0 : 1.0;
                float dhdlat = -_RutDepth * rut * (-2.0 * dl / w2) * sgn + 0.025 * crown * (-2.0 * lat / 0.2025);

                // Washboard corrugations along the track (faded out before they alias).
                float phase = along / 0.75;
                half washFade = wash * saturate(1.5 - fwidth(phase) * 2.5);
                float dhdalong = 0.1 * cos(phase * 6.2831853) * washFade;

                // --- Textures: hex-tiled packed dirt, loose sand on the crown and edges.
                float2 dpx = ddx(p.xz);
                float2 dpy = ddy(p.xz);
                HexTiles hd = HexSetup(p.xz / _DirtScale + 0.21, dpx / _DirtScale, dpy / _DirtScale, 1.0);
                half3 hw;
                half4 dirt = HexSample(TEXTURE2D_ARGS(_DirtTex, sampler_DirtTex), hd, 0.6, hw);
                half3 dirtN = HexNormal(TEXTURE2D_ARGS(_DirtNrm, sampler_DirtNrm), hd, hw, _NormalStrength);
                half4 sand = SAMPLE_TEXTURE2D(_SandTex, sampler_SandTex, p.xz / _SandScale);

                half loose = saturate(crown * (1.25 - wear) + smoothstep(0.5, 0.95, e) + (macroS.g - 0.5) * 0.4);
                half3 col = lerp(dirt.rgb, sand.rgb, loose * 0.85);
                col *= lerp(1.0, 0.8, rut * wear);                              // compacted, darker ruts
                // Tread marks in the ruts (close up only).
                float tread = frac(along * 3.4 + abs(dl) * 2.2);
                half treadAA = saturate(1.0 - fwidth(along * 3.4) * 3.0);
                col *= 1.0 - 0.07 * smoothstep(0.35, 0.5, tread) * smoothstep(0.85, 0.7, tread) * rut * treadAA;
                // Side tracks: dry grass and weeds on the crown.
                half weeds = crown * (1.0 - wear) * smoothstep(0.35, 0.7, macroS.b);
                col = lerp(col, half3(0.55, 0.50, 0.31), weeds * 0.55);
                // Washboard: crests catch a little more light-coloured dust.
                col *= 1.0 + 0.05 * sin(phase * 6.2831853) * washFade;
                col *= lerp(0.88, 1.08, macro.r);

                // --- Wet ground from the hazard map: mud darkens, water collects in the ruts.
                half smooth = 0.08;
                float2 huv = (p.xz - _OffroadTerrainRect.xy) / max(_OffroadTerrainRect.zw, 1.0);
                half4 hz = SAMPLE_TEXTURE2D(_OffroadHazard, sampler_OffroadHazard, huv) * _OffroadHazardOn;
                half wet = saturate(hz.r * 1.4 + hz.g + hz.a);
                col = lerp(col, col * half3(0.42, 0.40, 0.38), wet);
                smooth = lerp(smooth, 0.5, wet);
                half puddle = saturate((hz.a * 1.6 + hz.r * 0.7 - 0.35) * 2.0) * saturate(rut * 1.6 - 0.2);
                col = lerp(col, half3(0.045, 0.045, 0.05), puddle);
                smooth = lerp(smooth, 0.95, puddle);

                // --- Normal: base terrain normal, bent by the profile and the dirt texture.
                half3 nrm = normalize(n - across * dhdlat - alongDir * dhdalong);
                half3 tn = dirtN;
                nrm = normalize(nrm + (across * tn.x + alongDir * tn.y) * (1.0 - loose * 0.5) * (1.0 - puddle));

                SurfaceData s = (SurfaceData)0;
                s.albedo = col;
                s.smoothness = smooth;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(1.0, 0.8, rut * wear);
                s.alpha = alpha;

                InputData d = (InputData)0;
                d.positionWS = p;
                d.positionCS = i.positionCS;
                d.normalWS = nrm;
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(p);
                d.shadowCoord = TransformWorldToShadowCoord(p);
                d.fogCoord = i.track.w;
                d.bakedGI = SampleSH(nrm);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                half4 color = UniversalFragmentPBR(d, s);
                color.rgb = MixFog(color.rgb, d.fogCoord);
                return half4(color.rgb, alpha);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
