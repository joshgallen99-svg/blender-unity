// Cinematic sky: smooth zenith-to-horizon gradient, a soft haze band on the horizon (the same colour
// the distance fog fades into, so land and sky meet seamlessly), a warm Mie-style glow around the sun
// that grows near the horizon, and an HDR sun disc that blooms. The sun direction and colour come from
// the main light, so the sky always agrees with the lighting.
Shader "Offroad/Sky"
{
    Properties
    {
        _ZenithColor ("Zenith", Color) = (0.16, 0.30, 0.58, 1)
        _HorizonColor ("Horizon", Color) = (0.62, 0.72, 0.84, 1)
        _HazeColor ("Horizon Haze (= fog colour)", Color) = (0.74, 0.79, 0.86, 1)
        _GroundColor ("Below Horizon", Color) = (0.45, 0.40, 0.36, 1)
        _SunGlowColor ("Sun Glow", Color) = (1.0, 0.72, 0.45, 1)
        _GradientPower ("Gradient Curve", Range(0.2, 2)) = 0.55
        _HazeHeight ("Haze Band Height", Range(1, 40)) = 11
        _HazeAmount ("Haze Amount", Range(0, 1)) = 0.85
        _GlowAmount ("Glow Amount", Range(0, 2)) = 0.9
        _SunSize ("Sun Size (radians)", Range(0.005, 0.08)) = 0.022
        _SunIntensity ("Sun Disc Intensity", Float) = 14
        _Exposure ("Exposure", Float) = 1
    }

    SubShader
    {
        Tags { "Queue" = "Background" "RenderType" = "Background" "PreviewType" = "Skybox" "RenderPipeline" = "UniversalPipeline" }
        Cull Off ZWrite Off

        Pass
        {
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _ZenithColor, _HorizonColor, _HazeColor, _GroundColor, _SunGlowColor;
                half _GradientPower, _HazeHeight, _HazeAmount, _GlowAmount, _SunSize, _SunIntensity, _Exposure;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.dir = v.positionOS.xyz;
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 d = normalize(i.dir);
                Light sun = GetMainLight();
                float3 s = sun.direction;
                float mu = dot(d, s);
                float up = saturate(d.y);

                // Gradient, a little lower and warmer on the sun's side of the sky.
                half3 col = lerp(_HorizonColor.rgb, _ZenithColor.rgb, pow(up, _GradientPower));
                half sunSide = pow(saturate(mu * 0.5 + 0.5), 3.0) * (1.0 - up);
                col = lerp(col, col * lerp(half3(1, 1, 1), _SunGlowColor.rgb * 1.15, 0.45), sunSide);

                // Haze band hugging the horizon (matches the fog), and the ground below it.
                half haze = exp(-abs(d.y) * _HazeHeight) * _HazeAmount;
                col = lerp(col, _HazeColor.rgb, haze);
                if (d.y < 0.0) col = lerp(_HazeColor.rgb, _GroundColor.rgb, saturate(-d.y * 4.0));

                // Sun: broad Mie glow (stronger when the sun is low), a tight halo and the disc itself.
                half lowSun = 1.0 - saturate(s.y * 2.5);
                half glow = pow(saturate(mu), 6.0) * (0.25 + 0.55 * lowSun) + pow(saturate(mu), 48.0) * 0.6;
                col += _SunGlowColor.rgb * glow * _GlowAmount * (0.6 + 0.4 * (1.0 - up));
                half disc = smoothstep(cos(_SunSize * 1.35), cos(_SunSize), mu) * step(-0.01, d.y);
                col += sun.color * disc * _SunIntensity;

                return half4(col * _Exposure, 1);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
