// Ground trails (see GroundTrails.cs). Pass 0 stamps tyre contact patches into the trail map with
// max blending: R = how deep the ground was pressed, G = the rim squeezed up beside the tyre.
// Pass 1 shifts the map when it is re-centred on the vehicle.
Shader "Hidden/Offroad/TrailStamp"
{
    Properties { _MainTex ("Source", 2D) = "black" {} }
    SubShader
    {
        Tags { "RenderType" = "Opaque" }
        ZTest Always ZWrite Off Cull Off

        Pass
        {
            BlendOp Max
            Blend One One
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata { float4 vertex : POSITION; float3 uv : TEXCOORD0; };
            struct v2f { float4 pos : SV_POSITION; float3 uv : TEXCOORD0; };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float x = abs(i.uv.x);                       // across, in tyre half-widths
                float pressure = i.uv.y;
                float churn = i.uv.z;                        // > 1 when the tyre is spinning or sliding
                float rut = (1.0 - smoothstep(0.72, 1.08, x)) * pressure * min(churn, 1.25) / 1.25;
                float rim = exp(-pow((x - 1.28) / 0.22, 2.0)) * pressure * saturate(0.55 + (churn - 1.0));
                return fixed4(rut, rim, 0, 0);
            }
            ENDCG
        }

        Pass
        {
            Blend Off
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            float4 _Shift;

            fixed4 frag(v2f_img i) : SV_Target
            {
                float2 uv = i.uv + _Shift.xy;
                if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return 0;
                return tex2D(_MainTex, uv);
            }
            ENDCG
        }
    }
}
