// High alpine terrain: tundra turf, scree, snow and the gravel pass track from a painted mask, dark
// gneiss on steep ground (with snow lying on its ledges above the snowline). Layers are hex-tiled and
// height-blended. From the hazard map: deep snow drifts (R), damp shores (G = water depth), sheet ice
// (B) and slushy meltwater (A). Tyres cut deep ruts in snow and shallow ones elsewhere (Trails.hlsl);
// snow sparkles in the sun. Used as the Unity Terrain material (drawInstanced off).
Shader "Offroad/AlpineTerrain"
{
    Properties
    {
        _Mask ("Mask (R tundra, G scree, B snow, A track)", 2D) = "red" {}
        _Macro ("Macro Variation", 2D) = "gray" {}
        _GrassTex ("Tundra", 2D) = "white" {}
        [Normal] _GrassNrm ("Tundra Normal", 2D) = "bump" {}
        _ScreeTex ("Scree", 2D) = "white" {}
        [Normal] _ScreeNrm ("Scree Normal", 2D) = "bump" {}
        _SnowTex ("Snow", 2D) = "white" {}
        [Normal] _SnowNrm ("Snow Normal", 2D) = "bump" {}
        _TrackTex ("Track Gravel", 2D) = "white" {}
        [Normal] _TrackNrm ("Track Gravel Normal", 2D) = "bump" {}
        _RockTex ("Rock", 2D) = "white" {}
        [Normal] _RockNrm ("Rock Normal", 2D) = "bump" {}
        _GrassScale ("Tundra Tile (m)", Float) = 4
        _ScreeScale ("Scree Tile (m)", Float) = 3
        _SnowScale ("Snow Tile (m)", Float) = 6
        _TrackScale ("Track Tile (m)", Float) = 3
        _RockScale ("Rock Tile (m)", Float) = 9
        _BlendDepth ("Height Blend Depth", Range(0.02, 1)) = 0.2
        _RockSlope ("Rock Slope Start/End (1 - n.y)", Vector) = (0.28, 0.46, 0, 0)
        _SnowHeight ("Snow on Rock Start/Full (world Y)", Vector) = (235, 290, 0, 0)
        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
        _Sparkle ("Snow Sparkle", Range(0, 4)) = 1.5
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry-100" "TerrainCompatible" = "True" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _Mask_ST;
            float _GrassScale, _ScreeScale, _SnowScale, _TrackScale, _RockScale;
            half _BlendDepth;
            float4 _RockSlope;
            float4 _SnowHeight;
            half _NormalStrength;
            half _Sparkle;
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

            // One shared repeat sampler for all tiling textures (WebGL: 16 sampler slots).
            TEXTURE2D(_Mask); SAMPLER(sampler_Mask);
            TEXTURE2D(_GrassTex); SAMPLER(sampler_GrassTex);
            TEXTURE2D(_Macro);
            TEXTURE2D(_GrassNrm);
            TEXTURE2D(_ScreeTex);
            TEXTURE2D(_ScreeNrm);
            TEXTURE2D(_SnowTex);
            TEXTURE2D(_SnowNrm);
            TEXTURE2D(_TrackTex);
            TEXTURE2D(_TrackNrm);
            TEXTURE2D(_RockTex);
            TEXTURE2D(_RockNrm);
            #define S_REPEAT sampler_GrassTex

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

            void GroundLayer(TEXTURE2D_PARAM(tex, ts), TEXTURE2D_PARAM(nrm, ns), float2 xz, float2 dpx, float2 dpy,
                             float scale, float offset, half contrast, inout half4 col, inout half3 tn)
            {
                HexTiles h = HexSetup(xz / scale + offset, dpx / scale, dpy / scale, 1.0);
                half3 hw;
                col = HexSample(TEXTURE2D_ARGS(tex, ts), h, contrast, hw);
                tn = HexNormal(TEXTURE2D_ARGS(nrm, ns), h, hw, _NormalStrength);
            }

            float Hash21(float2 p)
            {
                p = frac(p * float2(123.34, 456.21));
                p += dot(p, p + 45.32);
                return frac(p.x * p.y);
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 p = i.positionWS;
                half3 n = normalize(i.normalWS);
                half4 mask = SAMPLE_TEXTURE2D(_Mask, sampler_Mask, i.uvFog.xy);
                half4 macro = SAMPLE_TEXTURE2D(_Macro, S_REPEAT, p.xz / 256.0);
                half4 macro2 = SAMPLE_TEXTURE2D(_Macro, S_REPEAT, p.xz / 37.0 + 0.37);
                half4 macroS = SAMPLE_TEXTURE2D(_Macro, S_REPEAT, p.xz / 9.0 + 0.13);
                float2 dpx = ddx(p.xz);
                float2 dpy = ddy(p.xz);
                half4 hz = SAMPLE_TEXTURE2D(_OffroadHazard, sampler_OffroadHazard, i.uvFog.xy) * _OffroadHazardOn;
                half edgeN = (macroS.g - 0.5) * 0.35 + (macro2.r - 0.5) * 0.2;
                half driftW = smoothstep(0.3, 0.6, hz.r + edgeN * 0.6);
                half iceW = smoothstep(0.35, 0.6, hz.b + edgeN * 0.4);
                // Drifts are snow: fold them into the mask.
                half4 w = max(mask, 0.0001);
                w.z = max(w.z, driftW * 1.5);

                // Tyre trails: snow takes deep ruts (deeper still in drifts), gravel and scree shallow ones.
                half softP = w.x * 0.04 + w.y * 0.02 + w.z * 0.12 + w.w * 0.03 + driftW * 0.08 + hz.a * 0.04;
                softP *= 1.0 - iceW;
                p.xz = TrailParallax(p.xz, GetWorldSpaceNormalizeViewDir(i.positionWS), softP);

                // --- Ground layers, hex-tiled; layers the mask doesn't use here are skipped.
                half4 grassC = half4(0.30, 0.29, 0.16, 0.5), screeC = half4(0.38, 0.37, 0.36, 0.5);
                half4 snowC = half4(0.88, 0.91, 0.95, 0.5), trackC = half4(0.40, 0.38, 0.35, 0.5);
                half3 grassN = half3(0, 0, 1), screeN = half3(0, 0, 1), snowN = half3(0, 0, 1), trackN = half3(0, 0, 1);
                [branch] if (w.x > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_GrassTex, sampler_GrassTex), TEXTURE2D_ARGS(_GrassNrm, S_REPEAT), p.xz, dpx, dpy, _GrassScale, 0.0, 0.6, grassC, grassN);
                [branch] if (w.y > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_ScreeTex, S_REPEAT), TEXTURE2D_ARGS(_ScreeNrm, S_REPEAT), p.xz, dpx, dpy, _ScreeScale, 0.43, 0.7, screeC, screeN);
                [branch] if (w.z > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_SnowTex, S_REPEAT), TEXTURE2D_ARGS(_SnowNrm, S_REPEAT), p.xz, dpx, dpy, _SnowScale, 0.17, 0.4, snowC, snowN);
                [branch] if (w.w > 0.004)
                    GroundLayer(TEXTURE2D_ARGS(_TrackTex, S_REPEAT), TEXTURE2D_ARGS(_TrackNrm, S_REPEAT), p.xz, dpx, dpy, _TrackScale, 0.71, 0.6, trackC, trackN);

                // Height blend: snow fills the hollows first (low snow lies between the stones and tussocks).
                half4 hb = w + half4(grassC.a, screeC.a, (1.0 - snowC.a) * 0.6 + 0.2, trackC.a * 0.8) * _BlendDepth * 2.0 + (macro2.b - 0.5) * 0.12;
                half mx = max(max(hb.x, hb.y), max(hb.z, hb.w));
                half4 bw = max(hb - (mx - _BlendDepth), 0);
                bw /= max(bw.x + bw.y + bw.z + bw.w, 1e-4);
                half3 groundCol = grassC.rgb * bw.x + screeC.rgb * bw.y + snowC.rgb * bw.z + trackC.rgb * bw.w;
                half groundH = grassC.a * bw.x + screeC.a * bw.y + snowC.a * bw.z + trackC.a * bw.w;
                half3 groundTN = grassN * bw.x + screeN * bw.y + snowN * bw.z + trackN * bw.w;
                half3 groundNormal = TopNormal(groundTN, n);

                // --- Rock on steep ground (triplanar); snow on its ledges above the snowline.
                half steep = 1.0 - n.y;
                half rockW = smoothstep(_RockSlope.x, _RockSlope.y, steep + (macro2.g - 0.5) * 0.08);
                half4 rockTex = half4(0.3, 0.3, 0.3, 0.5);
                half3 rockNormal = n;
                float3 pr = p / _RockScale;
                float3 prdx = ddx(pr);
                float3 prdy = ddy(pr);
                [branch] if (rockW > 0.002)
                {
                    half3 tw = TriplanarWeights(n, 4);
                    rockTex = TriplanarSampleGrad(TEXTURE2D_ARGS(_RockTex, S_REPEAT), pr, prdx, prdy, tw);
                    rockNormal = TriplanarNormalGrad(TEXTURE2D_ARGS(_RockNrm, S_REPEAT), pr, prdx, prdy, n, tw, _NormalStrength);
                }
                half3 rockCol = rockTex.rgb * lerp(0.82, 1.08, macro2.r);
                half lichen = smoothstep(0.6, 0.8, macro2.g + (rockTex.a - 0.5) * 0.35) * smoothstep(0.55, 0.3, steep);
                rockCol = lerp(rockCol, rockCol * half3(0.95, 1.02, 0.85) + half3(0.05, 0.05, 0.03), lichen * 0.6);
                half snowLine = smoothstep(_SnowHeight.x, _SnowHeight.y, p.y + (macro.g - 0.5) * 60.0);
                half rockUp = saturate(rockNormal.y * 0.6 + n.y * 0.4);
                half rockSnow = saturate((rockUp - 0.52 + (macro2.b - 0.5) * 0.3 + (0.5 - rockTex.a) * 0.3) * 5.0) * snowLine;
                rockCol = lerp(rockCol, half3(0.86, 0.89, 0.94) * lerp(0.92, 1.03, macroS.r), rockSnow);
                rockNormal = normalize(lerp(rockNormal, normalize(n + half3(0, 0.6, 0)), rockSnow));

                half rb = HeightBlend(1.0 - rockW, groundH, rockW, rockTex.a * 0.8, 0.12);
                rb = saturate(rb * 1.15 - 0.05);
                half3 albedo = lerp(groundCol, rockCol, rb);
                half3 normalWS = normalize(lerp(groundNormal, rockNormal, rb));
                half ground = 1.0 - rb;
                half snowAmt = saturate(bw.z * ground + rockSnow * rb);

                // Macro variation: lighter/darker patches on the turf and scree; snow stays clean.
                half3 varied = albedo * lerp(0.84, 1.1, macro.r) * lerp(0.94, 1.05, macro2.g);
                varied = lerp(varied, varied * half3(1.08, 1.0, 0.82), smoothstep(0.55, 0.85, macro.b) * 0.5 * ground);
                albedo = lerp(varied, albedo * lerp(0.96, 1.02, macro.r), snowAmt);

                // --- Hazards: damp shores, slushy meltwater, sheet ice.
                half smooth = lerp(0.06, 0.12, rb) + 0.22 * snowAmt;
                half shore = saturate(hz.g * 30.0) * ground * (1.0 - snowAmt);
                albedo *= 1.0 - 0.3 * shore;
                smooth += 0.25 * shore;
                half slushW = smoothstep(0.35, 0.65, hz.a + edgeN) * ground;
                float tm = _Time.y;
                half3 wn = half3(sin(p.x * 3.1 + tm * 1.7) + sin(p.z * 2.3 - tm * 1.3), 0,
                                 cos(p.x * 2.7 - tm * 1.1) + cos(p.z * 3.7 + tm * 1.9)) * 0.01;
                half slushWater = smoothstep(0.55, 0.8, hz.a + edgeN * 0.5) * ground;
                albedo = lerp(albedo, lerp(trackC.rgb * 0.5, half3(0.62, 0.66, 0.68), 0.35), slushW);
                smooth = lerp(smooth, 0.55, slushW);
                albedo = lerp(albedo, half3(0.05, 0.06, 0.065), slushWater);
                smooth = lerp(smooth, 0.95, slushWater);
                normalWS = normalize(lerp(normalWS, normalize(half3(0, 1, 0) + wn), slushWater));
                // Ice: glassy, blue-grey, with white cracks and trapped bubbles; the ground shows dimly through.
                half crack = 1.0 - smoothstep(0.0, 0.025, abs(macroS.r - 0.5)) ;
                crack = max(crack, 1.0 - smoothstep(0.0, 0.02, abs(macro2.b - 0.47)));
                half3 iceCol = lerp(albedo * 0.35, half3(0.42, 0.55, 0.64), 0.6) + crack * 0.25;
                albedo = lerp(albedo, iceCol, iceW * ground);
                smooth = lerp(smooth, 0.93 - crack * 0.4, iceW * ground);
                normalWS = normalize(lerp(normalWS, n, iceW * ground * 0.85));

                // --- Tyre trails: compacted, greyer ruts in snow, darker ruts in turf and gravel.
                half soft = (bw.x * 0.04 + bw.y * 0.02 + bw.z * 0.12 + bw.w * 0.03) * ground + driftW * 0.08 + slushW * 0.04;
                soft *= 1.0 - iceW;
                TrailInfo trail = SampleTrail(i.positionWS.xz, soft);
                normalWS = normalize(normalWS + half3(-trail.grad.x, 0, -trail.grad.y));
                half rutShade = (0.18 + 0.2 * slushW) * trail.depth * saturate(soft * 25.0);
                albedo = lerp(albedo * (1.0 - rutShade), albedo * half3(0.82, 0.85, 0.9), trail.depth * snowAmt * 0.6);
                albedo *= 1.0 + 0.06 * trail.rim * saturate(soft * 25.0);
                smooth = lerp(smooth, 0.45, trail.depth * snowAmt * 0.6);

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.smoothness = saturate(smooth);
                s.normalTS = half3(0, 0, 1);
                s.occlusion = lerp(lerp(0.8, 1.0, saturate(lerp(groundH, rockTex.a, rb) * 1.5)), 1.0, snowAmt * 0.7);
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

                // Snow sparkle: sparse grains catch the sun at the right angle (fades with distance).
                [branch] if (snowAmt > 0.3 && _Sparkle > 0.0)
                {
                    float2 cell = floor(i.positionWS.xz * 28.0);
                    float rnd = Hash21(cell);
                    float3 gn = normalize(float3(Hash21(cell + 7.1) - 0.5, 1.2, Hash21(cell + 3.7) - 0.5));
                    Light sun = GetMainLight(d.shadowCoord);
                    float3 hv = normalize(sun.direction + d.viewDirectionWS);
                    half glint = pow(saturate(dot(gn, hv)), 60.0) * step(0.9, rnd);
                    half dist = length(i.positionWS - _WorldSpaceCameraPos);
                    color.rgb += sun.color * glint * _Sparkle * snowAmt * sun.shadowAttenuation * saturate(1.0 - dist / 60.0);
                }

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
