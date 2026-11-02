// Rivers, lakes and the waterfall. Transparent; depth comes from the global terrain heightmap (no
// depth texture needed): shallow water is clear and shows the bed, deep water turns dark green-blue.
// Two normal layers scroll along the flow (uv.y runs downstream, in metres), foam gathers along the
// shallow edges, in rapids and at the foot of the falls, and the sky is reflected with a Fresnel term.
// Vertex colour: r = turbulence (0 calm .. 1 rapids), g = extra foam, b = waterfall sheet (flows down uv.y).
Shader "Offroad/Water"
{
    Properties
    {
        [Normal] _NormalTex ("Wave Normals", 2D) = "bump" {}
        _FoamTex ("Foam", 2D) = "black" {}
        _ShallowColor ("Shallow Colour", Color) = (0.30, 0.38, 0.30, 1)
        _DeepColor ("Deep Colour", Color) = (0.02, 0.08, 0.09, 1)
        _Clarity ("Absorption per metre", Float) = 1.1
        _FlowSpeed ("Flow Speed (m/s)", Float) = 0.9
        _WaveScale ("Wave Tile (m)", Float) = 4
        _WaveStrength ("Wave Strength", Range(0, 2)) = 0.6
        _FoamScale ("Foam Tile (m)", Float) = 3
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
            #include "Desert.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _ShallowColor, _DeepColor;
                float _Clarity, _FlowSpeed, _WaveScale, _FoamScale;
                half _WaveStrength;
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

                // Two wave layers drifting downstream at different speeds and scales.
                float2 uvA = float2(uv.x, uv.y - tm * speed) / _WaveScale;
                float2 uvB = float2(uv.x * 0.7 + 0.37, uv.y - tm * speed * 0.55) / (_WaveScale * 1.9);
                half3 nA = UnpackNormalScale(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvA), _WaveStrength * (1.0 + turb));
                half3 nB = UnpackNormalScale(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvB), _WaveStrength * 0.7);
                half3 tn = normalize(half3(nA.xy + nB.xy, nA.z * nB.z));
                half3 normalWS = normalize(t * tn.x + b * tn.y + n * tn.z);

                // Depth from the terrain heightmap (water surface minus ground).
                float ground = TerrainHeightAt(p);
                float depth = fall > 0.5 ? 2.0 : max(p.y - ground, 0.0);
                half absorb = 1.0 - exp(-depth * _Clarity);
                half3 waterCol = lerp(_ShallowColor.rgb, _DeepColor.rgb, saturate(depth / 2.5));

                // Foam: shallow edges, rapids, the falls and their plunge pool.
                float2 uvF = float2(uv.x, uv.y - tm * speed * 1.1) / _FoamScale;
                half foamTex = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvF).r;
                half foamTex2 = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvF * 0.6 + 0.5).r;
                half edgeFoam = saturate(1.0 - depth / 0.18) * 0.7;
                half foamAmt = saturate(edgeFoam + turb * 0.55 + i.color.g + fall * 0.9);
                half foam = saturate((foamTex * 0.7 + foamTex2 * 0.5) * foamAmt * 1.6);

                half3 viewWS = GetWorldSpaceNormalizeViewDir(p);
                half fresnel = pow(1.0 - saturate(dot(normalWS, viewWS)), 5.0) * 0.9 + 0.03;
                half alpha = saturate(max(absorb, fresnel * 0.55) + foam);
                alpha *= saturate(depth * 12.0 + fall);                     // feather the shoreline
                half3 albedo = lerp(waterCol, half3(0.85, 0.88, 0.88), foam);
                half smooth = lerp(0.86, 0.35, foam);

                [branch] if (fall > 0.5)
                {
                    // Falling water: aerated and nearly white, in two streams split by a rock in the notch,
                    // with long vertical streaks racing down. Vertex green = layer opacity (back sheet / veil).
                    float2 uvS = float2(uv.x * 2.4, (uv.y - tm * speed * 1.4) * 0.3) / _FoamScale;
                    half streak = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvS).r;
                    half streak2 = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, uvS * float2(0.55, 0.8) + 0.31).r;
                    half streams = saturate(1.8 - abs(abs(uv.x) - 2.6) / 1.25);
                    half body = saturate(streams * (0.5 + 0.7 * streak + 0.45 * streak2));
                    albedo = lerp(half3(0.58, 0.67, 0.69), half3(0.95, 0.97, 0.97), saturate(0.35 + streak + streak2 * 0.6));
                    smooth = 0.55;
                    alpha = saturate(body) * i.color.g;
                }

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.smoothness = smooth;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = 1;
                s.alpha = alpha;

                InputData d = (InputData)0;
                d.positionWS = p;
                d.positionCS = i.positionCS;
                d.normalWS = normalWS;
                d.viewDirectionWS = viewWS;
                d.shadowCoord = TransformWorldToShadowCoord(p);
                d.fogCoord = i.uvFog.z;
                d.bakedGI = SampleSH(normalWS);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                half4 color = UniversalFragmentPBR(d, s);
                color.rgb = OffroadFog(color.rgb, p, d.fogCoord);
                return half4(color.rgb, alpha);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
