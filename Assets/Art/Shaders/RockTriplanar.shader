// Rock surface for scenery: world-space triplanar texturing (no UV seams, no stretching on any
// face) with sandstone strata, plus wind-blown sand settling on upward faces. Uses the same
// textures as the terrain so rocks sit naturally in the ground.
Shader "Offroad/RockTriplanar"
{
    Properties
    {
        [MainTexture] _BaseMap ("Rock Albedo", 2D) = "white" {}
        [Normal] _BumpMap ("Rock Normal", 2D) = "bump" {}
        _TopMap ("Dust Albedo", 2D) = "white" {}
        [Normal] _TopNormal ("Dust Normal", 2D) = "bump" {}
        [MainColor] _BaseColor ("Rock Tint", Color) = (1, 1, 1, 1)
        _TopColor ("Dust Tint", Color) = (1, 1, 1, 1)
        _Scale ("Rock Texture Scale (m)", Float) = 4
        _TopScale ("Dust Texture Scale (m)", Float) = 6
        _StrataScale ("Strata Bands per Metre", Float) = 1.3
        _StrataStrength ("Strata Strength", Range(0, 1)) = 0.35
        _TopAmount ("Dust Coverage", Range(0, 1)) = 0.45
        _TopSharpness ("Dust Edge Sharpness", Range(1, 16)) = 6
        _BumpScale ("Normal Strength", Range(0, 2)) = 1
        _Smoothness ("Smoothness", Range(0, 1)) = 0.12
        _AOFromHeight ("Base Darkening Height (m)", Float) = 0.6
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
            float _StrataScale;
            half _StrataStrength;
            half _TopAmount;
            half _TopSharpness;
            half _BumpScale;
            half _Smoothness;
            float _AOFromHeight;
        CBUFFER_END

        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
        TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap);
        TEXTURE2D(_TopMap); SAMPLER(sampler_TopMap);
        TEXTURE2D(_TopNormal); SAMPLER(sampler_TopNormal);
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
                float4 baseWS : TEXCOORD2;   // xyz object origin in world, w fog factor
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
                o.baseWS.xyz = TransformObjectToWorld(float3(0, 0, 0));
                o.baseWS.w = ComputeFogFactor(pos.positionCS.z);
                return o;
            }

            // Triplanar normal blending ("whiteout" blend) for a tangent-space normal map.
            half3 TriplanarNormal(TEXTURE2D_PARAM(tex, samp), float3 p, half3 n, half3 w, half strength)
            {
                half3 tx = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.zy), strength);
                half3 ty = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xz), strength);
                half3 tz = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xy), strength);
                half3 axisSign = sign(n);
                tx.z *= axisSign.x; ty.z *= axisSign.y; tz.z *= axisSign.z;
                half3 nx = half3(tx.xy + n.zy, abs(tx.z) * n.x);
                half3 ny = half3(ty.xy + n.xz, abs(ty.z) * n.y);
                half3 nz = half3(tz.xy + n.xy, abs(tz.z) * n.z);
                return normalize(nx.zyx * w.x + ny.xzy * w.y + nz.xyz * w.z);
            }

            half3 Triplanar(TEXTURE2D_PARAM(tex, samp), float3 p, half3 w)
            {
                return SAMPLE_TEXTURE2D(tex, samp, p.zy).rgb * w.x
                     + SAMPLE_TEXTURE2D(tex, samp, p.xz).rgb * w.y
                     + SAMPLE_TEXTURE2D(tex, samp, p.xy).rgb * w.z;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half3 n = normalize(i.normalWS);
                half3 w = pow(abs(n), 4.0);
                w /= max(w.x + w.y + w.z, 1e-4);

                // Offset per instance so neighbouring rocks don't share the exact pattern.
                float3 seed = frac(i.baseWS.xyz * 0.137) * 37.0;
                float3 pRock = (i.positionWS + seed) / _Scale;
                half3 rock = Triplanar(TEXTURE2D_ARGS(_BaseMap, sampler_BaseMap), pRock, w) * _BaseColor.rgb;
                half3 rockN = TriplanarNormal(TEXTURE2D_ARGS(_BumpMap, sampler_BumpMap), pRock, n, w, _BumpScale);

                // Sandstone strata: soft horizontal bands, slightly wavy.
                float band = i.positionWS.y * _StrataScale + sin(i.positionWS.x * 0.35 + i.positionWS.z * 0.27) * 0.4 + seed.x;
                half strata = 0.5 + 0.5 * sin(band * 6.2831);
                rock *= lerp(1.0, lerp(0.78, 1.12, strata), _StrataStrength);

                // Sand settled on top faces, with a noisy edge from the dust texture.
                float3 pTop = i.positionWS / _TopScale;
                half3 top = SAMPLE_TEXTURE2D(_TopMap, sampler_TopMap, pTop.xz).rgb * _TopColor.rgb;
                half noise = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, pTop.xz * 3.1).g;
                half up = saturate(rockN.y * 0.7 + n.y * 0.3);
                half dust = saturate((up - (1.0 - _TopAmount) + (noise - 0.5) * 0.35) * _TopSharpness);
                half3 topN = normalize(lerp(n, half3(0, 1, 0), 0.5));

                // Darken where rocks meet the ground (fake contact occlusion).
                half heightAbove = saturate((i.positionWS.y - i.baseWS.y) / max(_AOFromHeight, 0.01));
                half occlusion = lerp(0.6, 1.0, heightAbove);

                SurfaceData s = (SurfaceData)0;
                s.albedo = lerp(rock, top, dust);
                s.metallic = 0;
                s.specular = 0;
                s.smoothness = lerp(_Smoothness, 0.05, dust);
                s.normalTS = half3(0, 0, 1);
                s.occlusion = occlusion;
                s.alpha = 1;

                InputData d = (InputData)0;
                d.positionWS = i.positionWS;
                d.positionCS = i.positionCS;
                d.normalWS = normalize(lerp(rockN, topN, dust));
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                d.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                d.fogCoord = i.baseWS.w;
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
