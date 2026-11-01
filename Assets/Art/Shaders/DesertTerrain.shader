// Desert terrain: sand, cracked playa mud and desert pavement from a painted mask, with layered
// sandstone wherever the ground is steep (or the mask exposes slickrock). Layers blend by their
// height maps so sand settles into cracks, and large-scale noise breaks up texture tiling.
// Used as the Unity Terrain material (drawInstanced off).
Shader "Offroad/DesertTerrain"
{
    Properties
    {
        _Mask ("Mask (R sand, G mud, B pavement, A slickrock)", 2D) = "red" {}
        _Macro ("Macro Variation", 2D) = "gray" {}
        _SandTex ("Sand", 2D) = "white" {}
        [Normal] _SandNrm ("Sand Normal", 2D) = "bump" {}
        _MudTex ("Mud", 2D) = "white" {}
        [Normal] _MudNrm ("Mud Normal", 2D) = "bump" {}
        _PaveTex ("Pavement", 2D) = "white" {}
        [Normal] _PaveNrm ("Pavement Normal", 2D) = "bump" {}
        _RockTex ("Sandstone", 2D) = "white" {}
        [Normal] _RockNrm ("Sandstone Normal", 2D) = "bump" {}
        _SandScale ("Sand Tile (m)", Float) = 6
        _MudScale ("Mud Tile (m)", Float) = 4.5
        _PaveScale ("Pavement Tile (m)", Float) = 3
        _RockScale ("Rock Tile (m)", Float) = 9
        _BlendDepth ("Height Blend Depth", Range(0.02, 1)) = 0.18
        _RockSlope ("Rock Slope Start/End (1 - n.y)", Vector) = (0.24, 0.42, 0, 0)
        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry-100" "TerrainCompatible" = "True" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _Mask_ST;
            float _SandScale, _MudScale, _PaveScale, _RockScale;
            half _BlendDepth;
            float4 _RockSlope;
            half _NormalStrength;
        CBUFFER_END
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

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Desert.hlsl"

            TEXTURE2D(_Mask); SAMPLER(sampler_Mask);
            TEXTURE2D(_Macro); SAMPLER(sampler_Macro);
            TEXTURE2D(_SandTex); SAMPLER(sampler_SandTex);
            TEXTURE2D(_SandNrm); SAMPLER(sampler_SandNrm);
            TEXTURE2D(_MudTex); SAMPLER(sampler_MudTex);
            TEXTURE2D(_MudNrm); SAMPLER(sampler_MudNrm);
            TEXTURE2D(_PaveTex); SAMPLER(sampler_PaveTex);
            TEXTURE2D(_PaveNrm); SAMPLER(sampler_PaveNrm);
            TEXTURE2D(_RockTex); SAMPLER(sampler_RockTex);
            TEXTURE2D(_RockNrm); SAMPLER(sampler_RockNrm);

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 uvFog : TEXCOORD2;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs pos = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = pos.positionCS;
                o.positionWS = pos.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uvFog = float3(v.uv, ComputeFogFactor(pos.positionCS.z));
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS);
                half4 mask = SAMPLE_TEXTURE2D(_Mask, sampler_Mask, i.uvFog.xy);
                half4 macro = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 256.0);
                half4 macro2 = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 37.0 + 0.37);

                // --- Ground layers (top-down projection). Sand is sampled at two scales to hide tiling.
                float2 uvSand = p.xz / _SandScale;
                half4 sandA = SAMPLE_TEXTURE2D(_SandTex, sampler_SandTex, uvSand);
                half4 sandB = SAMPLE_TEXTURE2D(_SandTex, sampler_SandTex, uvSand * 0.27 + 0.5);
                half4 sand = lerp(sandA, sandB, 0.35 + 0.3 * macro.g);
                half3 sandN = UnpackNormalScale(SAMPLE_TEXTURE2D(_SandNrm, sampler_SandNrm, uvSand), _NormalStrength);
                half4 mud = SAMPLE_TEXTURE2D(_MudTex, sampler_MudTex, p.xz / _MudScale);
                half3 mudN = UnpackNormalScale(SAMPLE_TEXTURE2D(_MudNrm, sampler_MudNrm, p.xz / _MudScale), _NormalStrength);
                half4 pave = SAMPLE_TEXTURE2D(_PaveTex, sampler_PaveTex, p.xz / _PaveScale);
                half3 paveN = UnpackNormalScale(SAMPLE_TEXTURE2D(_PaveNrm, sampler_PaveNrm, p.xz / _PaveScale), _NormalStrength);

                half3 w = max(mask.rgb, 0.0001);
                // Break up mask edges with the textures' own heights (sand fills the cracks).
                half3 hb = w + half3(sand.a * 0.5, mud.a, pave.a) * _BlendDepth * 2.0 + (macro2.b - 0.5) * 0.15;
                half mx = max(hb.x, max(hb.y, hb.z));
                half3 bw = max(hb - (mx - _BlendDepth), 0);
                bw /= max(bw.x + bw.y + bw.z, 1e-4);
                half3 groundCol = sand.rgb * bw.x + mud.rgb * bw.y + pave.rgb * bw.z;
                half groundH = sand.a * 0.5 * bw.x + mud.a * bw.y + pave.a * bw.z;
                half3 groundTN = sandN * bw.x + mudN * bw.y + paveN * bw.z;
                half3 groundNormal = TopNormal(groundTN, n);

                // --- Sandstone: steep slopes, or slickrock exposed by the mask. Triplanar + strata colour.
                half steep = 1.0 - n.y;
                half rockW = saturate(max(mask.a, smoothstep(_RockSlope.x, _RockSlope.y, steep)));
                float3 pr = p / _RockScale;
                half3 tw = TriplanarWeights(n, 4);
                half4 rockTex = TriplanarSample(TEXTURE2D_ARGS(_RockTex, sampler_RockTex), pr, tw);
                half3 rockNormal = TriplanarNormal(TEXTURE2D_ARGS(_RockNrm, sampler_RockNrm), pr, n, tw, _NormalStrength);
                half3 strata = StrataColor(p, macro.g * 0.7 + macro2.r * 0.3);
                half3 rockCol = rockTex.rgb * strata * 1.55;

                // Height blend ground vs rock: sand pools in the hollows of slickrock.
                half rb = HeightBlend(1.0 - rockW, groundH, rockW, rockTex.a * 0.8, 0.12);
                rb = saturate(rb * 1.15 - 0.05);

                half3 albedo = lerp(groundCol, rockCol, rb);
                half3 normalWS = normalize(lerp(groundNormal, rockNormal, rb));

                // Macro colour variation (large patches lighter/darker, a little redder in places).
                albedo *= lerp(0.86, 1.1, macro.r);
                albedo = lerp(albedo, albedo * half3(1.08, 0.95, 0.9), macro.b * 0.45);

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.smoothness = lerp(0.06, 0.12, rb);
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(0.72, 1.0, saturate(lerp(groundH, rockTex.a, rb) * 1.4));
                s.alpha = 1;

                InputData d = (InputData)0;
                d.positionWS = p;
                d.positionCS = i.positionCS;
                d.normalWS = normalWS;
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(p);
                d.shadowCoord = TransformWorldToShadowCoord(p);
                d.fogCoord = i.uvFog.z;
                d.bakedGI = SampleSH(normalWS);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                half4 color = UniversalFragmentPBR(d, s);
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

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/CommonMaterial.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings ShadowVert(Attributes v)
            {
                Varyings o;
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

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings DepthVert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                return o;
            }

            half DepthFrag(Varyings i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
