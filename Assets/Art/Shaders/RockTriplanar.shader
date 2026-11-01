// Sandstone rocks and formations. World-space triplanar texturing with the same strata colours as the
// terrain (so formations look carved from the same bedrock), sand settling on upward faces, and a sand
// skirt where the rock meets the terrain (read from the global terrain heightmap).
Shader "Offroad/RockTriplanar"
{
    Properties
    {
        [MainTexture] _BaseMap ("Sandstone Detail", 2D) = "white" {}
        [Normal] _BumpMap ("Sandstone Normal", 2D) = "bump" {}
        _TopMap ("Sand", 2D) = "white" {}
        [Normal] _TopNormal ("Sand Normal", 2D) = "bump" {}
        _Macro ("Macro Variation", 2D) = "gray" {}
        [MainColor] _BaseColor ("Rock Tint", Color) = (1, 1, 1, 1)
        _TopColor ("Sand Tint", Color) = (1, 1, 1, 1)
        _Scale ("Rock Texture Scale (m)", Float) = 9
        _TopScale ("Sand Texture Scale (m)", Float) = 6
        _TopAmount ("Sand on Ledges", Range(0, 1)) = 0.35
        _TopSharpness ("Sand Edge Sharpness", Range(1, 16)) = 5
        _SkirtHeight ("Sand Skirt Height (m)", Float) = 1.2
        _BumpScale ("Normal Strength", Range(0, 2)) = 1
        _Smoothness ("Smoothness", Range(0, 1)) = 0.1
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }
        LOD 300

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            half4 _TopColor;
            float _Scale;
            float _TopScale;
            half _TopAmount;
            half _TopSharpness;
            float _SkirtHeight;
            half _BumpScale;
            half _Smoothness;
        CBUFFER_END

        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
        TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap);
        TEXTURE2D(_TopMap); SAMPLER(sampler_TopMap);
        TEXTURE2D(_TopNormal); SAMPLER(sampler_TopNormal);
        TEXTURE2D(_Macro); SAMPLER(sampler_Macro);
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Desert.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float4 originFog : TEXCOORD2;   // xyz object origin in world, w fog factor
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            Varyings Vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                VertexPositionInputs pos = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = pos.positionCS;
                o.positionWS = pos.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.originFog.xyz = TransformObjectToWorld(float3(0, 0, 0));
                o.originFog.w = ComputeFogFactor(pos.positionCS.z);
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS);
                half3 w = TriplanarWeights(n, 4);

                // Per-object offset so neighbouring rocks don't share the exact pattern.
                float3 seed = frac(i.originFog.xyz * 0.0137) * 53.0;
                float3 pr = (p + seed) / _Scale;
                half4 rockTex = TriplanarSample(TEXTURE2D_ARGS(_BaseMap, sampler_BaseMap), pr, w);
                half3 rockN = TriplanarNormal(TEXTURE2D_ARGS(_BumpMap, sampler_BumpMap), pr, n, w, _BumpScale);

                half4 macro = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 256.0);
                half4 macro2 = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 37.0 + 0.37);
                half4 macroL = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 1400.0 + 0.71);
                half3 strata = StrataColor(p, macro.g * 0.7 + macro2.r * 0.3, macroL.r);
                half3 rock = rockTex.rgb * strata * 1.55 * _BaseColor.rgb;
                rock *= lerp(0.84, 1.1, macro.r);

                // Sand: on upward-facing ledges, and as a skirt where the rock meets the terrain.
                float2 uvTop = p.xz / _TopScale;
                half4 sandTex = SAMPLE_TEXTURE2D(_TopMap, sampler_TopMap, uvTop);
                half3 sand = sandTex.rgb * _TopColor.rgb * lerp(0.86, 1.1, macro.r);
                half up = saturate(rockN.y * 0.65 + n.y * 0.35);
                half ledge = saturate((up - (1.0 - _TopAmount) + (macro2.b - 0.5) * 0.4 + (sandTex.a - rockTex.a) * 0.3) * _TopSharpness);

                float ground = TerrainHeightAt(p);
                float above = p.y - ground;
                half skirt = 1.0 - smoothstep(0.0, _SkirtHeight * (0.5 + macro2.b), above + (rockTex.a - 0.5) * 0.5);
                skirt *= saturate(0.55 + n.y);
                half sandW = saturate(max(ledge, skirt));

                // Contact darkening just above the sand line.
                half occlusion = lerp(0.62, 1.0, saturate((above - 0.1) / 2.5));

                SurfaceData s = (SurfaceData)0;
                s.albedo = lerp(rock, sand, sandW);
                s.smoothness = lerp(_Smoothness, 0.05, sandW);
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(occlusion, 1.0, sandW * 0.6);
                s.alpha = 1;

                InputData d = (InputData)0;
                d.positionWS = p;
                d.positionCS = i.positionCS;
                d.normalWS = normalize(lerp(rockN, normalize(lerp(n, half3(0, 1, 0), 0.4)), sandW));
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(p);
                d.shadowCoord = TransformWorldToShadowCoord(p);
                d.fogCoord = i.originFog.w;
                d.bakedGI = SampleSH(d.normalWS);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                half4 color = UniversalFragmentPBR(d, s);
                color.rgb = MixFog(color.rgb, d.fogCoord);
                return color;
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/CommonMaterial.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings ShadowVert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - positionWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                float4 positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, lightDir));
            #if UNITY_REVERSED_Z
                positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #else
                positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = positionCS;
                return o;
            }

            half4 ShadowFrag(Varyings i) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex DepthVert
            #pragma fragment DepthFrag
            #pragma multi_compile_instancing

            struct Attributes { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings DepthVert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                return o;
            }

            half DepthFrag(Varyings i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
