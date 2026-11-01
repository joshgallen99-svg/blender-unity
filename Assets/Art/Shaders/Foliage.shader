// Desert vegetation: alpha-cut leaf cards, two-sided, with soft wrapped lighting and wind sway.
// Sway is weighted by height above the plant's pivot so the base stays planted.
Shader "Offroad/Foliage"
{
    Properties
    {
        [MainTexture] _BaseMap ("Leaves (RGBA)", 2D) = "white" {}
        [MainColor] _BaseColor ("Tint", Color) = (1, 1, 1, 1)
        _Cutoff ("Alpha Cutoff", Range(0, 1)) = 0.45
        _WindStrength ("Wind Strength", Range(0, 0.5)) = 0.08
        _WindSpeed ("Wind Speed", Float) = 1.6
        _WindHeight ("Height for Full Sway (m)", Float) = 1.2
        _Translucency ("Back-lit Glow", Range(0, 1)) = 0.35
        _Smoothness ("Smoothness", Range(0, 1)) = 0.15
    }

    SubShader
    {
        Tags { "RenderType" = "TransparentCutout" "RenderPipeline" = "UniversalPipeline" "Queue" = "AlphaTest" }
        Cull Off

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            half _Cutoff;
            float _WindStrength;
            float _WindSpeed;
            float _WindHeight;
            half _Translucency;
            half _Smoothness;
        CBUFFER_END

        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);

        float3 ApplyWind(float3 positionWS, float3 pivotWS)
        {
            float h = saturate((positionWS.y - pivotWS.y) / max(_WindHeight, 0.01));
            float t = _Time.y * _WindSpeed + dot(pivotWS.xz, float2(0.13, 0.21));
            float gust = 0.6 + 0.4 * sin(t * 0.37 + pivotWS.x * 0.01);
            float2 sway = float2(sin(t), cos(t * 1.31)) * gust;
            float flutter = sin(t * 4.3 + positionWS.x * 3.0 + positionWS.z * 2.0) * 0.25;
            positionWS.xz += (sway + flutter) * _WindStrength * h * h;
            return positionWS;
        }
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
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 uvFog : TEXCOORD2;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            Varyings Vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                float3 pivot = TransformObjectToWorld(float3(0, 0, 0));
                float3 positionWS = ApplyWind(TransformObjectToWorld(v.positionOS.xyz), pivot);
                o.positionWS = positionWS;
                o.positionCS = TransformWorldToHClip(positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uvFog = float3(TRANSFORM_TEX(v.uv, _BaseMap), ComputeFogFactor(o.positionCS.z));
                return o;
            }

            half4 Frag(Varyings i, bool frontFace : SV_IsFrontFace) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half4 tex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uvFog.xy) * _BaseColor;
                clip(tex.a - _Cutoff);

                half3 n = normalize(i.normalWS);   // mesh normals are bent outward from the plant centre
                InputData d = (InputData)0;
                d.positionWS = i.positionWS;
                d.positionCS = i.positionCS;
                d.normalWS = n;
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                d.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                d.fogCoord = i.uvFog.z;
                d.bakedGI = SampleSH(n);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = tex.rgb;
                s.smoothness = _Smoothness;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = 1;
                s.alpha = 1;
                half4 color = UniversalFragmentPBR(d, s);

                // Light shining through leaves when looking toward the sun.
                Light mainLight = GetMainLight(d.shadowCoord);
                half back = saturate(dot(-d.viewDirectionWS, mainLight.direction));
                color.rgb += tex.rgb * mainLight.color * back * back * _Translucency * mainLight.shadowAttenuation;

                color.rgb = MixFog(color.rgb, d.fogCoord);
                return half4(color.rgb, 1);
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
            Cull Off

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

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings ShadowVert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 pivot = TransformObjectToWorld(float3(0, 0, 0));
                float3 positionWS = ApplyWind(TransformObjectToWorld(v.positionOS.xyz), pivot);
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
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                return o;
            }

            half4 ShadowFrag(Varyings i) : SV_Target
            {
                clip(SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).a * _BaseColor.a - _Cutoff);
                return 0;
            }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
