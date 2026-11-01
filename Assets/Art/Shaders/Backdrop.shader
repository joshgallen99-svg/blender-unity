// Distant scenery (mountain ranges, far mesas) drawn at the very back of the depth buffer so it is
// never clipped by the camera's far plane. Cheap: unlit-ish lambert plus baked aerial-perspective haze.
Shader "Offroad/Backdrop"
{
    Properties
    {
        _LitColor ("Lit Colour", Color) = (0.55, 0.58, 0.68, 1)
        _ShadowColor ("Shadow Colour", Color) = (0.35, 0.40, 0.52, 1)
        _HazeColor ("Haze Colour", Color) = (0.72, 0.78, 0.86, 1)
        _Haze ("Haze Amount", Range(0, 1)) = 0.55
        _HazeHeight ("Haze Fades By Height (m)", Float) = 300
        _SnowLine ("Snow Line (m, 0 = none)", Float) = 0
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry+10" }
        Cull Off

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _LitColor, _ShadowColor, _HazeColor;
                half _Haze;
                float _HazeHeight;
                float _SnowLine;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float4 color : COLOR; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS : TEXCOORD0;
                float height : TEXCOORD1;
                half4 color : COLOR;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(positionWS);
            #if UNITY_REVERSED_Z
                o.positionCS.z = o.positionCS.w * 1e-6;
            #else
                o.positionCS.z = o.positionCS.w * (1 - 1e-6);
            #endif
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.height = positionWS.y;
                o.color = v.color;
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                Light sun = GetMainLight();
                half3 n = normalize(i.normalWS);
                half ndl = saturate(dot(n, sun.direction) * 0.8 + 0.2);
                half3 col = lerp(_ShadowColor.rgb, _LitColor.rgb, ndl) * i.color.rgb;
                // Snow on the high, gentler slopes.
                half snow = _SnowLine > 0 ? smoothstep(_SnowLine - 30.0, _SnowLine + 30.0, i.height + (n.y - 0.6) * 80.0) : 0;
                col = lerp(col, lerp(half3(0.50, 0.58, 0.72), half3(0.94, 0.95, 0.98), ndl), snow);
                // Thicker haze near the base of the ranges, clearer toward the peaks.
                half haze = saturate(_Haze * (1.15 - saturate(i.height / _HazeHeight) * 0.5));
                return half4(lerp(col, _HazeColor.rgb, haze), 1);
            }
            ENDHLSL
        }
    }
}
