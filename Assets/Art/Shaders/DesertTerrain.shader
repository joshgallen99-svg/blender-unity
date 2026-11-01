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
        _SandScale ("Sand Tile (m)", Float) = 3.5
        _MudScale ("Mud Tile (m)", Float) = 4.5
        _PaveScale ("Pavement Tile (m)", Float) = 3
        _RockScale ("Rock Tile (m)", Float) = 9
        _BlendDepth ("Height Blend Depth", Range(0.02, 1)) = 0.18
        _RockSlope ("Rock Slope Start/End (1 - n.y)", Vector) = (0.24, 0.42, 0, 0)
        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
        _RippleStrength ("Wind Ripples", Range(0, 1)) = 1
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
            half _RippleStrength;
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
            #include "Trails.hlsl"

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
                half4 macroL = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 1400.0 + 0.71);   // region-scale zones
                half4 macroS = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 9.0 + 0.13);      // ripple warp
                float2 dpx = ddx(p.xz);
                float2 dpy = ddy(p.xz);
                half3 w = max(mask.rgb, 0.0001);
                half4 hz = SAMPLE_TEXTURE2D(_OffroadHazard, sampler_OffroadHazard, i.uvFog.xy) * _OffroadHazardOn;

                // Tyre trails: how deep this ground lets a tyre sink (sand deep, dry mud and pavement
                // shallow, rock not at all), then look into the ruts with parallax.
                half softP = (w.x * 0.06 + w.y * 0.015 + w.z * 0.02) * (1.0 - mask.a) + hz.r * 0.06 + hz.g * 0.04;
                p.xz = TrailParallax(p.xz, GetWorldSpaceNormalizeViewDir(i.positionWS), softP);

                // --- Ground layers (top-down, hex-tiled so they never visibly repeat). Layers the mask
                // doesn't use here are skipped (the branch is coherent: the mask changes slowly).
                half4 sand = half4(0.6, 0.4, 0.3, 0.5);
                half3 sandN = half3(0, 0, 1);
                [branch] if (w.x + mask.a > 0.004)   // sand also pools in slickrock hollows
                {
                    HexTiles hs = HexSetup(p.xz / _SandScale, dpx / _SandScale, dpy / _SandScale, 1.0);
                    half3 hw;
                    sand = HexSample(TEXTURE2D_ARGS(_SandTex, sampler_SandTex), hs, 0.6, hw);
                    sandN = HexNormal(TEXTURE2D_ARGS(_SandNrm, sampler_SandNrm), hs, hw, _NormalStrength);
                }
                half4 mud = half4(0.6, 0.5, 0.4, 0.5);
                half3 mudN = half3(0, 0, 1);
                [branch] if (w.y > 0.004)
                {
                    HexTiles hm = HexSetup(p.xz / _MudScale + 0.31, dpx / _MudScale, dpy / _MudScale, 1.0);
                    half3 hw;
                    mud = HexSample(TEXTURE2D_ARGS(_MudTex, sampler_MudTex), hm, 0.5, hw);
                    mudN = HexNormal(TEXTURE2D_ARGS(_MudNrm, sampler_MudNrm), hm, hw, _NormalStrength);
                }
                half4 pave = half4(0.5, 0.35, 0.25, 0.5);
                half3 paveN = half3(0, 0, 1);
                [branch] if (w.z > 0.004)
                {
                    HexTiles hp = HexSetup(p.xz / _PaveScale + 0.67, dpx / _PaveScale, dpy / _PaveScale, 1.0);
                    half3 hw;
                    pave = HexSample(TEXTURE2D_ARGS(_PaveTex, sampler_PaveTex), hp, 0.7, hw);
                    paveN = HexNormal(TEXTURE2D_ARGS(_PaveNrm, sampler_PaveNrm), hp, hw, _NormalStrength);
                }

                // Break up mask edges with the textures' own heights (sand fills the cracks).
                half3 hb = w + half3(sand.a * 0.5, mud.a, pave.a) * _BlendDepth * 2.0 + (macro2.b - 0.5) * 0.15;
                half mx = max(hb.x, max(hb.y, hb.z));
                half3 bw = max(hb - (mx - _BlendDepth), 0);
                bw /= max(bw.x + bw.y + bw.z, 1e-4);
                half3 groundCol = sand.rgb * bw.x + mud.rgb * bw.y + pave.rgb * bw.z;
                half groundH = sand.a * 0.5 * bw.x + mud.a * bw.y + pave.a * bw.z;
                half3 groundTN = sandN * bw.x + mudN * bw.y + paveN * bw.z;

                // Wind ripples on open, flat sand (patchy, drawn in world space).
                half rippleAmt = bw.x * smoothstep(0.35, 0.62, macro2.g) * saturate(n.y * 5.0 - 4.0) * _RippleStrength;
                half2 rippleN;
                half ripple = SandRipples(p.xz, macroS.r + macro2.b * 0.5, rippleAmt, rippleN);
                groundTN.xy += rippleN;
                groundCol *= 1.0 + 0.08 * (ripple - 0.5 * rippleAmt);
                half3 groundNormal = TopNormal(groundTN, n);

                // --- Sandstone: steep slopes, or slickrock exposed by the mask. Triplanar + strata colour.
                half steep = 1.0 - n.y;
                half rockW = saturate(max(mask.a, smoothstep(_RockSlope.x, _RockSlope.y, steep)));
                half4 rockTex = half4(0.66, 0.66, 0.66, 0.5);
                half3 rockNormal = n;
                float3 pr = p / _RockScale;
                float3 prdx = ddx(pr);
                float3 prdy = ddy(pr);
                [branch] if (rockW > 0.002)
                {
                    half3 tw = TriplanarWeights(n, 4);
                    rockTex = TriplanarSampleGrad(TEXTURE2D_ARGS(_RockTex, sampler_RockTex), pr, prdx, prdy, tw);
                    rockNormal = TriplanarNormalGrad(TEXTURE2D_ARGS(_RockNrm, sampler_RockNrm), pr, prdx, prdy, n, tw, _NormalStrength);
                }
                half3 strata = StrataColor(p, macro.g * 0.7 + macro2.r * 0.3, macroL.r);
                half3 rockCol = rockTex.rgb * strata * 1.55;

                // Height blend ground vs rock: sand pools in the hollows of slickrock.
                half rb = HeightBlend(1.0 - rockW, groundH, rockW, rockTex.a * 0.8, 0.12);
                rb = saturate(rb * 1.15 - 0.05);

                half3 albedo = lerp(groundCol, rockCol, rb);
                half3 normalWS = normalize(lerp(groundNormal, rockNormal, rb));

                // Macro colour variation at three scales: light/dark patches, iron-red sand in some
                // areas and paler, greyer wash deposits in others.
                albedo *= lerp(0.80, 1.12, macro.r) * lerp(0.93, 1.05, macro2.g);
                half ground = 1.0 - rb;
                albedo = lerp(albedo, albedo * half3(1.12, 0.90, 0.82), smoothstep(0.45, 0.8, macroL.b) * 0.65 * ground);
                albedo = lerp(albedo, albedo * half3(1.0, 1.03, 1.08), smoothstep(0.55, 0.85, macro.b) * 0.5 * ground);

                // --- Hazards from the hazard map: wet mud, standing water, quicksand, each with a damp rim.
                half edgeN = (macroS.g - 0.5) * 0.35 + (macro2.r - 0.5) * 0.2;
                half mudW = smoothstep(0.35, 0.65, hz.r + edgeN) * ground;
                half quickW = smoothstep(0.3, 0.6, hz.g + edgeN * 0.6) * ground;
                half waterW = smoothstep(0.35, 0.6, hz.a + edgeN * 0.5) * ground;
                half damp = saturate((hz.r + hz.g) * 2.5) * (1.0 - mudW) * (1.0 - quickW) * ground;
                half smooth = lerp(0.06, 0.12, rb);
                float tm = _Time.y;

                albedo *= 1.0 - 0.32 * damp;
                smooth += 0.12 * damp;

                half3 mudCol = lerp(half3(0.13, 0.085, 0.06), half3(0.24, 0.16, 0.11), saturate(mud.a * 1.2));
                albedo = lerp(albedo, mudCol * lerp(0.85, 1.1, macroS.b), mudW);
                smooth = lerp(smooth, 0.55, mudW);
                normalWS = normalize(lerp(normalWS, n, mudW * 0.6));

                half3 qn = half3(sin(p.x * 0.9 + tm * 0.6) + sin(p.z * 1.3 - tm * 0.45), 0,
                                 cos(p.x * 0.7 - p.z * 0.8 + tm * 0.5) * 2.0) * 0.02;
                albedo = lerp(albedo, half3(0.50, 0.38, 0.27) * lerp(0.92, 1.06, sand.a), quickW);
                smooth = lerp(smooth, 0.42, quickW);
                normalWS = normalize(lerp(normalWS, normalize(n + qn), quickW));

                half3 wn = half3(sin(p.x * 3.1 + tm * 1.7) + sin(p.z * 2.3 - tm * 1.3), 0,
                                 cos(p.x * 2.7 - tm * 1.1) + cos(p.z * 3.7 + tm * 1.9)) * 0.012;
                albedo = lerp(albedo, half3(0.035, 0.04, 0.045), waterW);
                smooth = lerp(smooth, 0.96, waterW);
                normalWS = normalize(lerp(normalWS, normalize(half3(0, 1, 0) + wn), waterW));

                // Tyre trails: rut walls and rims bend the normal; ruts are darker (compacted, damp),
                // rims a little lighter (loose); in mud the ruts hold water.
                half soft = (bw.x * 0.06 + bw.y * 0.015 + bw.z * 0.02) * ground + mudW * 0.04 + quickW * 0.03;
                TrailInfo trail = SampleTrail(i.positionWS.xz, soft);
                normalWS = normalize(normalWS + half3(-trail.grad.x, 0, -trail.grad.y));
                albedo *= 1.0 - (0.16 + 0.25 * mudW) * trail.depth * saturate(soft * 25.0);
                albedo *= 1.0 + 0.06 * trail.rim * saturate(soft * 25.0);
                smooth = lerp(smooth, 0.75, trail.depth * mudW);

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.smoothness = smooth;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(0.66, 1.0, saturate(lerp(groundH, rockTex.a, rb) * 1.5));
                s.alpha = 1;

                InputData d = (InputData)0;
                d.positionWS = i.positionWS;
                d.positionCS = i.positionCS;
                d.normalWS = normalWS;
                d.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                d.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                d.fogCoord = i.uvFog.z;
                d.bakedGI = SampleSH(normalWS);
                d.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                d.shadowMask = half4(1, 1, 1, 1);

                half4 color = UniversalFragmentPBR(d, s);
                color.rgb = OffroadFog(color.rgb, i.positionWS, d.fogCoord);
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
