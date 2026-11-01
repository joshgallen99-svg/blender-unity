// Forest valley terrain: forest floor (moss, needles), meadow, packed soil and river gravel from a
// painted mask, granite on steep ground. Layers are hex-tiled and height-blended; wet mud and
// puddles come from the hazard map; tyre trails (Trails.hlsl) press into the soft ground.
// Used as the Unity Terrain material (drawInstanced off).
Shader "Offroad/ForestTerrain"
{
    Properties
    {
        _Mask ("Mask (R forest floor, G meadow, B soil, A gravel)", 2D) = "red" {}
        _Macro ("Macro Variation", 2D) = "gray" {}
        _FloorTex ("Forest Floor", 2D) = "white" {}
        [Normal] _FloorNrm ("Forest Floor Normal", 2D) = "bump" {}
        _MeadowTex ("Meadow", 2D) = "white" {}
        [Normal] _MeadowNrm ("Meadow Normal", 2D) = "bump" {}
        _SoilTex ("Soil", 2D) = "white" {}
        [Normal] _SoilNrm ("Soil Normal", 2D) = "bump" {}
        _GravelTex ("River Gravel", 2D) = "white" {}
        [Normal] _GravelNrm ("River Gravel Normal", 2D) = "bump" {}
        _WetMudTex ("Wet Mud", 2D) = "white" {}
        _RockTex ("Granite", 2D) = "white" {}
        [Normal] _RockNrm ("Granite Normal", 2D) = "bump" {}
        _FloorScale ("Forest Floor Tile (m)", Float) = 4
        _MeadowScale ("Meadow Tile (m)", Float) = 4
        _SoilScale ("Soil Tile (m)", Float) = 3
        _GravelScale ("Gravel Tile (m)", Float) = 2.5
        _RockScale ("Rock Tile (m)", Float) = 7
        _BlendDepth ("Height Blend Depth", Range(0.02, 1)) = 0.2
        _RockSlope ("Rock Slope Start/End (1 - n.y)", Vector) = (0.3, 0.5, 0, 0)
        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry-100" "TerrainCompatible" = "True" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _Mask_ST;
            float _FloorScale, _MeadowScale, _SoilScale, _GravelScale, _RockScale;
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
            #include "Trails.hlsl"

            TEXTURE2D(_Mask); SAMPLER(sampler_Mask);
            TEXTURE2D(_Macro); SAMPLER(sampler_Macro);
            TEXTURE2D(_FloorTex); SAMPLER(sampler_FloorTex);
            TEXTURE2D(_FloorNrm); SAMPLER(sampler_FloorNrm);
            TEXTURE2D(_MeadowTex); SAMPLER(sampler_MeadowTex);
            TEXTURE2D(_MeadowNrm); SAMPLER(sampler_MeadowNrm);
            TEXTURE2D(_SoilTex); SAMPLER(sampler_SoilTex);
            TEXTURE2D(_SoilNrm); SAMPLER(sampler_SoilNrm);
            TEXTURE2D(_GravelTex); SAMPLER(sampler_GravelTex);
            TEXTURE2D(_GravelNrm); SAMPLER(sampler_GravelNrm);
            TEXTURE2D(_WetMudTex); SAMPLER(sampler_WetMudTex);
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

            // One hex-tiled ground layer (albedo with height in alpha, and its tangent normal).
            void GroundLayer(TEXTURE2D_PARAM(tex, ts), TEXTURE2D_PARAM(nrm, ns), float2 xz, float2 dpx, float2 dpy,
                             float scale, float offset, half contrast, inout half4 col, inout half3 tn)
            {
                HexTiles h = HexSetup(xz / scale + offset, dpx / scale, dpy / scale, 1.0);
                half3 hw;
                col = HexSample(TEXTURE2D_ARGS(tex, ts), h, contrast, hw);
                tn = HexNormal(TEXTURE2D_ARGS(nrm, ns), h, hw, _NormalStrength);
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS);
                half4 mask = SAMPLE_TEXTURE2D(_Mask, sampler_Mask, i.uvFog.xy);
                half4 macro = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 256.0);
                half4 macro2 = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 37.0 + 0.37);
                half4 macroS = SAMPLE_TEXTURE2D(_Macro, sampler_Macro, p.xz / 9.0 + 0.13);
                float2 dpx = ddx(p.xz);
                float2 dpy = ddy(p.xz);
                half4 w = max(mask, 0.0001);
                half4 hz = SAMPLE_TEXTURE2D(_OffroadHazard, sampler_OffroadHazard, i.uvFog.xy) * _OffroadHazardOn;

                // Tyre trails: soil and mud take deep ruts, the forest floor and meadow a little less,
                // gravel hardly any. Parallax looks into the ruts.
                half softP = w.x * 0.05 + w.y * 0.045 + w.z * 0.07 + w.w * 0.015 + hz.r * 0.05;
                p.xz = TrailParallax(p.xz, GetWorldSpaceNormalizeViewDir(i.positionWS), softP);

                // --- Ground layers, hex-tiled; layers the mask doesn't use here are skipped.
                half4 floorC = half4(0.25, 0.27, 0.12, 0.5), meadowC = half4(0.25, 0.33, 0.12, 0.5);
                half4 soilC = half4(0.20, 0.13, 0.09, 0.5), gravelC = half4(0.45, 0.42, 0.37, 0.5);
                half3 floorN = half3(0, 0, 1), meadowN = half3(0, 0, 1), soilN = half3(0, 0, 1), gravelN = half3(0, 0, 1);
                [branch] if (w.x > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_FloorTex, sampler_FloorTex), TEXTURE2D_ARGS(_FloorNrm, sampler_FloorNrm), p.xz, dpx, dpy, _FloorScale, 0.0, 0.6, floorC, floorN);
                [branch] if (w.y > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_MeadowTex, sampler_MeadowTex), TEXTURE2D_ARGS(_MeadowNrm, sampler_MeadowNrm), p.xz, dpx, dpy, _MeadowScale, 0.43, 0.5, meadowC, meadowN);
                [branch] if (w.z > 0.004 || hz.r > 0.01)
                    GroundLayer(TEXTURE2D_ARGS(_SoilTex, sampler_SoilTex), TEXTURE2D_ARGS(_SoilNrm, sampler_SoilNrm), p.xz, dpx, dpy, _SoilScale, 0.17, 0.6, soilC, soilN);
                [branch] if (w.w > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_GravelTex, sampler_GravelTex), TEXTURE2D_ARGS(_GravelNrm, sampler_GravelNrm), p.xz, dpx, dpy, _GravelScale, 0.71, 0.75, gravelC, gravelN);

                // Height blend: moss and litter sit on top, soil shows through in the low spots.
                half4 hb = w + half4(floorC.a, meadowC.a * 0.8, soilC.a * 0.6, gravelC.a) * _BlendDepth * 2.0 + (macro2.b - 0.5) * 0.15;
                half mx = max(max(hb.x, hb.y), max(hb.z, hb.w));
                half4 bw = max(hb - (mx - _BlendDepth), 0);
                bw /= max(bw.x + bw.y + bw.z + bw.w, 1e-4);
                half3 groundCol = floorC.rgb * bw.x + meadowC.rgb * bw.y + soilC.rgb * bw.z + gravelC.rgb * bw.w;
                half groundH = floorC.a * bw.x + meadowC.a * bw.y + soilC.a * bw.z + gravelC.a * bw.w;
                half3 groundTN = floorN * bw.x + meadowN * bw.y + soilN * bw.z + gravelN * bw.w;
                half3 groundNormal = TopNormal(groundTN, n);

                // --- Granite on steep ground (triplanar), mossy where it is not too steep.
                half steep = 1.0 - n.y;
                half rockW = smoothstep(_RockSlope.x, _RockSlope.y, steep);
                half4 rockTex = half4(0.45, 0.45, 0.45, 0.5);
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
                half3 rockCol = rockTex.rgb * lerp(0.85, 1.05, macro2.r);
                half mossOnRock = smoothstep(0.55, 0.3, steep) * smoothstep(0.35, 0.65, macro2.g + (rockTex.a - 0.5) * 0.4);
                rockCol = lerp(rockCol, floorC.rgb * half3(0.85, 1.05, 0.8), mossOnRock * 0.8);

                half rb = HeightBlend(1.0 - rockW, groundH, rockW, rockTex.a * 0.8, 0.12);
                rb = saturate(rb * 1.15 - 0.05);
                half3 albedo = lerp(groundCol, rockCol, rb);
                half3 normalWS = normalize(lerp(groundNormal, rockNormal, rb));
                half ground = 1.0 - rb;

                // Macro variation: light/dark patches, greener damp hollows, browner dry ground.
                albedo *= lerp(0.82, 1.1, macro.r) * lerp(0.94, 1.05, macro2.g);
                albedo = lerp(albedo, albedo * half3(0.9, 1.08, 0.86), smoothstep(0.5, 0.8, macro.g) * 0.6 * ground);
                albedo = lerp(albedo, albedo * half3(1.08, 0.98, 0.86), smoothstep(0.55, 0.85, macro.b) * 0.5 * ground);

                // --- Wet mud and puddles from the hazard map, with damp rims.
                half edgeN = (macroS.g - 0.5) * 0.35 + (macro2.r - 0.5) * 0.2;
                half mudW = smoothstep(0.35, 0.65, hz.r + edgeN) * ground;
                half waterW = smoothstep(0.35, 0.6, hz.a + edgeN * 0.5) * ground;
                half damp = saturate(hz.r * 2.5) * (1.0 - mudW) * ground;
                half smooth = lerp(0.08, 0.14, rb) + 0.05 * bw.y;
                float tm = _Time.y;
                albedo *= 1.0 - 0.3 * damp;
                smooth += 0.12 * damp;
                [branch] if (mudW > 0.002)
                {
                    half4 wm = SAMPLE_TEXTURE2D_GRAD(_WetMudTex, sampler_WetMudTex, p.xz / _SoilScale, dpx / _SoilScale, dpy / _SoilScale);
                    albedo = lerp(albedo, wm.rgb * lerp(0.8, 1.05, macroS.b), mudW);
                }
                smooth = lerp(smooth, 0.6, mudW);
                normalWS = normalize(lerp(normalWS, n, mudW * 0.6));
                half3 wn = half3(sin(p.x * 3.1 + tm * 1.7) + sin(p.z * 2.3 - tm * 1.3), 0,
                                 cos(p.x * 2.7 - tm * 1.1) + cos(p.z * 3.7 + tm * 1.9)) * 0.012;
                albedo = lerp(albedo, half3(0.03, 0.035, 0.03), waterW);
                smooth = lerp(smooth, 0.96, waterW);
                normalWS = normalize(lerp(normalWS, normalize(half3(0, 1, 0) + wn), waterW));

                // --- Tyre trails: rut walls bend the normal, ruts darker; in mud they hold water.
                half soft = (bw.x * 0.05 + bw.y * 0.045 + bw.z * 0.07 + bw.w * 0.015) * ground + mudW * 0.05;
                TrailInfo trail = SampleTrail(i.positionWS.xz, soft);
                normalWS = normalize(normalWS + half3(-trail.grad.x, 0, -trail.grad.y));
                albedo *= 1.0 - (0.2 + 0.25 * mudW) * trail.depth * saturate(soft * 25.0);
                albedo *= 1.0 + 0.05 * trail.rim * saturate(soft * 25.0);
                smooth = lerp(smooth, 0.8, trail.depth * saturate(mudW + damp * 0.5));

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.smoothness = smooth;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(0.6, 1.0, saturate(lerp(groundH, rockTex.a, rb) * 1.5));
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
