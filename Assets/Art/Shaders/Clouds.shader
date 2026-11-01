// Procedural cloud layer: a dome around the camera, drawn after the sky at the far plane, blending
// fluffy cumulus over the procedural skybox. Clouds live on a virtual plane high above the region
// (projected from the view ray), drift with the wind, are lit from the sun side and fade to haze at
// the horizon. Fragment noise only where sky shows.
Shader "Offroad/Clouds"
{
    Properties
    {
        _Coverage ("Coverage", Range(0, 1)) = 0.42
        _Softness ("Edge Softness", Range(0.02, 0.5)) = 0.16
        _Scale ("Cloud Size (m)", Float) = 2600
        _Height ("Cloud Height (m)", Float) = 1800
        _Wind ("Wind (m/s, xz)", Vector) = (6, 0, 2.5, 0)
        _LitColor ("Lit Colour", Color) = (1.0, 0.98, 0.95, 1)
        _ShadeColor ("Shade Colour", Color) = (0.62, 0.68, 0.78, 1)
        _HorizonColor ("Horizon Haze", Color) = (0.74, 0.79, 0.86, 1)
        _Opacity ("Opacity", Range(0, 1)) = 0.92
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Transparent-100" "IgnoreProjector" = "True" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half _Coverage, _Softness, _Opacity;
                float _Scale, _Height;
                float4 _Wind;
                half4 _LitColor, _ShadeColor, _HorizonColor;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dirWS : TEXCOORD0; };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(positionWS);
            #if UNITY_REVERSED_Z
                o.positionCS.z = o.positionCS.w * 1e-6;          // at the far plane, behind all scenery
            #else
                o.positionCS.z = o.positionCS.w * (1 - 1e-6);
            #endif
                o.dirWS = positionWS - _WorldSpaceCameraPos;
                return o;
            }

            float Hash(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }

            float Noise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(Hash(i), Hash(i + float2(1, 0)), u.x), lerp(Hash(i + float2(0, 1)), Hash(i + float2(1, 1)), u.x), u.y);
            }

            float Fbm(float2 p)
            {
                float s = 0.0, a = 0.5;
                [unroll] for (int k = 0; k < 5; k++) { s += a * Noise(p); p = p * 2.03 + 17.1; a *= 0.5; }
                return s;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 d = normalize(i.dirWS);
                if (d.y < 0.015) return 0;
                // Where the view ray meets the cloud plane, drifting with the wind.
                float2 q = (d.xz / d.y * _Height + _WorldSpaceCameraPos.xz + _Wind.xz * _Time.y) / _Scale;
                float shape = Fbm(q * 2.0);
                float detail = Fbm(q * 9.0 + 3.7);
                float density = saturate((shape * 0.8 + detail * 0.28 - (1.0 - _Coverage)) / _Softness);
                // Light: brighter toward the sun, darker undersides where the cloud is thick.
                Light sun = GetMainLight();
                float2 toSun = normalize(sun.direction.xz + 1e-4);
                float lit = saturate(0.55 + 0.45 * (Fbm(q * 2.0 + toSun * 0.06) < shape ? 1.0 : 0.2));
                half3 sunTint = sun.color / max(max(sun.color.r, sun.color.g), max(sun.color.b, 1e-3));
                half3 litCol = _LitColor.rgb * lerp(half3(1, 1, 1), sunTint, 0.65);
                half3 col = lerp(_ShadeColor.rgb, litCol, lit * (1.0 - density * 0.35));
                col += pow(saturate(dot(d, sun.direction)), 8.0) * 0.25 * sun.color;   // silver lining near the sun
                half horizon = saturate(d.y * 6.0);
                col = lerp(_HorizonColor.rgb, col, horizon);
                return half4(col, density * _Opacity * horizon * horizon);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
