// Rivers, lakes and the waterfall.
//
// The surface is shaded like real water instead of a tinted, see-through sheet:
//  - Refraction: the riverbed is read back from the camera's opaque texture (everything drawn before the
//    water), bent by the waves. Light is then absorbed along the path through the water, red first, so
//    shallow water stays clear and deep water turns blue-green. Water depth comes from the terrain
//    heightmap, so no depth texture is needed.
//  - In-scattering: deep water picks up its own colour, lit by the sky and the sun.
//  - Reflection: the sky reflection probe, weighted by Fresnel (strong at grazing angles), plus a tight
//    sun glint.
//  - Waves: two normal layers drift downstream (uv.y runs downstream in metres; tangent = across the
//    flow) and calm down with distance, so far water doesn't shimmer.
//  - Foam gathers along the shallow edges, in rapids and at the foot of the falls; the shoreline is
//    feathered exactly where the water meets the ground (per pixel, from the heightmap).
// Vertex colour: r turbulence (0 calm .. 1 rapids), g extra foam (waterfall: layer opacity),
// b waterfall sheet (flows down uv.y), a flow-speed multiplier.
Shader "Offroad/Water"
{
    Properties
    {
        [Normal] _NormalTex ("Wave Normals", 2D) = "bump" {}
        _FoamTex ("Foam", 2D) = "black" {}
        _ShallowColor ("Shallow Colour (sets absorption)", Color) = (0.30, 0.38, 0.30, 1)
        _DeepColor ("Deep Colour (in-scatter)", Color) = (0.02, 0.08, 0.09, 1)
        _Clarity ("Absorption per metre", Float) = 1.1
        _FlowSpeed ("Flow Speed (m/s)", Float) = 0.9
        _WaveScale ("Wave Tile (m)", Float) = 4
        _WaveStrength ("Wave Strength", Range(0, 2)) = 0.6
        _FoamScale ("Foam Tile (m)", Float) = 3
        _Refraction ("Refraction Strength", Range(0, 0.1)) = 0.035
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Transparent-10" "IgnoreProjector" = "True" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareOpaqueTexture.hlsl"
            #include "Desert.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _ShallowColor, _DeepColor;
                float _Clarity, _FlowSpeed, _WaveScale, _FoamScale;
                half _WaveStrength, _Refraction;
            CBUFFER_END

            TEXTURE2D(_NormalTex); SAMPLER(sampler_NormalTex);
            TEXTURE2D(_FoamTex); SAMPLER(sampler_FoamTex);

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float4 tangentWS : TEXCOORD2;
                float3 uvFog : TEXCOORD3;
                half4 color : COLOR;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs pos = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = pos.positionCS;
                o.positionWS = pos.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.tangentWS = float4(TransformObjectToWorldDir(v.tangentOS.xyz), v.tangentOS.w);
                o.uvFog = float3(v.uv, ComputeFogFactor(pos.positionCS.z));
                o.color = v.color;
                return o;
            }

            half4 Frag(Varyings i, FRONT_FACE_TYPE face : FRONT_FACE_SEMANTIC) : SV_Target
            {
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS) * IS_FRONT_VFACE(face, 1.0, -1.0);
                half3 t = normalize(i.tangentWS.xyz);
                half3 b = cross(n, t);
                float2 uv = i.uvFog.xy;
                half turb = i.color.r;
                half fall = i.color.b;
                float tm = _Time.y;
                float speed = _FlowSpeed * i.color.a * (1.0 + turb * 1.5 + fall * 5.0);
                half3 viewWS = GetWorldSpaceNormalizeViewDir(p);
                float camDist = distance(GetCameraPositionWS(), p);

                // Two wave layers drifting downstream; they flatten with distance (no far-off shimmer).
                half waveFade = lerp(1.0, 0.25, saturate(camDist / 220.0));
                float2 uvA = float2(uv.x, uv.y - tm * speed) / _WaveScale;
                float2 uvB = float2(uv.x * 0.7 + 0.37, uv.y - tm * speed * 0.55) / (_WaveScale * 1.9);
                half3 nA = UnpackNormalScale(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvA), _WaveStrength * (1.0 + turb) * waveFade);
                half3 nB = UnpackNormalScale(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvB), _WaveStrength * 0.7 * waveFade);
                half3 tn = normalize(half3(nA.xy + nB.xy, nA.z * nB.z));
                half3 normalWS = normalize(t * tn.x + b * tn.y + n * tn.z);

                Light sun = GetMainLight(TransformWorldToShadowCoord(p));
                half sunShadow = sun.shadowAttenuation;
                half3 sky = SampleSH(half3(0, 1, 0));
                half3 lightIn = sky + sun.color * sunShadow * saturate(sun.direction.y) * 0.55;

                // Foam: shallow edges, rapids, the falls and their plunge pool.
                float ground = TerrainHeightAt(p);
                float depth = fall > 0.5 ? 2.0 : max(p.y - ground, 0.0);
                float2 uvF = float2(uv.x, uv.y - tm * speed * 1.1) / _FoamScale;
                half foamTex = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvF).r;
                half foamTex2 = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvF * 0.6 + 0.5).r;
                half edgeFoam = saturate(1.0 - depth / 0.22) * 0.55;
                half foamAmt = saturate(edgeFoam + turb * 0.55 + i.color.g * (1.0 - fall) + fall * 0.9);
                half foam = saturate((foamTex * 0.7 + foamTex2 * 0.5) * foamAmt * 1.6);
                half3 foamCol = half3(0.86, 0.89, 0.9) * lightIn;

                [branch] if (fall > 0.5)
                {
                    // Falling water: aerated and nearly white, in two streams split by a rock in the notch,
                    // with long vertical streaks racing down. Vertex green = layer opacity (back sheet / veil).
                    float2 uvS = float2(uv.x * 2.4, (uv.y - tm * speed * 1.4) * 0.3) / _FoamScale;
                    half streak = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvS).r;
                    half streak2 = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvS * float2(0.55, 0.8) + 0.31).r;
                    half streams = saturate(1.8 - abs(abs(uv.x) - 2.6) / 1.25);
                    half body = saturate(streams * (0.5 + 0.7 * streak + 0.45 * streak2));
                    half3 sheet = lerp(half3(0.58, 0.67, 0.69), half3(0.95, 0.97, 0.97), saturate(0.35 + streak + streak2 * 0.6));
                    half3 lit = sheet * (sky + sun.color * sunShadow * (0.35 + 0.4 * saturate(dot(normalWS, sun.direction))));
                    return half4(OffroadFog(lit, p, i.uvFog.z), saturate(body) * i.color.g);
                }

                // --- Under the surface: the refracted bed, absorbed and tinted along the light path.
                half NdotV = saturate(dot(normalWS, viewWS));
                float path = depth / max(viewWS.y, 0.2);                // longer path at grazing angles
                float2 screenUV = GetNormalizedScreenSpaceUV(i.positionCS);
                float2 offset = normalWS.xz * _Refraction * saturate(depth * 1.2) * waveFade;
                half3 bed = SampleSceneColor(screenUV + offset);
                half3 absorb = _Clarity * max(1.1 - _ShallowColor.rgb * 1.2, 0.04);   // red goes first
                half3 transmit = exp(-absorb * path);
                half3 scatter = _DeepColor.rgb * lightIn * (1.0 - exp(-_Clarity * 0.8 * path));
                half3 under = bed * transmit + scatter;

                // --- Above: sky reflection with Fresnel, plus the sun's glint.
                half fresnel = 0.02 + 0.98 * pow(1.0 - NdotV, 5.0);
                half3 refl = GlossyEnvironmentReflection(reflect(-viewWS, normalWS), 0.06, 1.0);
                half3 h = normalize(sun.direction + viewWS);
                half glint = pow(saturate(dot(normalWS, h)), 900.0) * 60.0 + pow(saturate(dot(normalWS, h)), 120.0) * 0.6;
                half3 spec = sun.color * sunShadow * glint * (1.0 - foam);

                half3 color = lerp(under, refl, fresnel * (1.0 - foam)) + spec;
                color = lerp(color, foamCol, foam);
                color = OffroadFog(color, p, i.uvFog.z);

                // Fully opaque except a narrow feather where the water meets the shore.
                half alpha = saturate(depth * 10.0);
                return half4(color, alpha);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
