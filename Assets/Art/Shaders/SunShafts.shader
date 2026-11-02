// Screen-space light rays (crepuscular rays). Pass 0 keeps only the bright sky around the sun (where
// rocks, ridges or canopy block it, it stays dark), pass 1 streaks that toward the sun (run twice, at
// half resolution), pass 2 adds the rays onto the image. See SunShaftsFeature.cs.
Shader "Hidden/Offroad/SunShafts"
{
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" }
        ZWrite Off ZTest Always Cull Off

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl"
        float4 _SunScreen;     // xy sun position (uv), z visibility 0..1, w aspect
        float4 _ShaftParams;   // x brightness threshold, y radius around the sun (uv), z step fraction, w decay
        float4 _ShaftTint;     // rgb tint x intensity
        ENDHLSL

        Pass
        {
            Name "Prefilter"
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            half4 Frag(Varyings i) : SV_Target
            {
                float2 uv = i.texcoord;
                half3 c = SAMPLE_TEXTURE2D_X_LOD(_BlitTexture, sampler_LinearClamp, uv, 0).rgb;
                half lum = dot(c, half3(0.2126, 0.7152, 0.0722));
                float2 dv = (uv - _SunScreen.xy) * float2(_SunScreen.w, 1.0);
                half fall = saturate(1.0 - length(dv) / _ShaftParams.y);
                half bright = max(lum - _ShaftParams.x, 0.0) / max(lum, 1e-3);
                return half4(min(c, 4.0) * bright * fall * fall, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "Radial"
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            half4 Frag(Varyings i) : SV_Target
            {
                float2 uv = i.texcoord;
                float2 delta = (_SunScreen.xy - uv) * _ShaftParams.z;
                half3 sum = 0;
                half w = 1.0, total = 0.0;
                [unroll] for (int k = 0; k < 16; k++)
                {
                    sum += SAMPLE_TEXTURE2D_X_LOD(_BlitTexture, sampler_LinearClamp, uv, 0).rgb * w;
                    total += w;
                    w *= _ShaftParams.w;
                    uv += delta;
                }
                return half4(sum / total, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "Composite"
            Blend One One
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            half4 Frag(Varyings i) : SV_Target
            {
                half3 r = SAMPLE_TEXTURE2D_X_LOD(_BlitTexture, sampler_LinearClamp, i.texcoord, 0).rgb;
                return half4(r * _ShaftTint.rgb * _SunScreen.z, 0);
            }
            ENDHLSL
        }
    }
}
