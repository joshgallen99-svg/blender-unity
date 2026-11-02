using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Offroad.Rendering
{
    /// <summary>
    /// Has the engine draw the screen-space UI natively, straight to the screen after URP has finished,
    /// instead of inside URP's frame graph. With a reduced render scale (FSR upscaling) on Metal, URP's
    /// own UI pass could land the menus tiny, upside down and in a corner while their click targets stayed
    /// full size, so nothing seemed to respond. This is URP's documented opt-out: set the flag in a
    /// beginContextRendering callback, after URP has decided ownership for the frame.
    /// </summary>
    static class UIOverlayOwnership
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Install()
        {
            RenderPipelineManager.beginContextRendering -= OnBeginContext;
            RenderPipelineManager.beginContextRendering += OnBeginContext;
        }

        static void OnBeginContext(ScriptableRenderContext context, List<Camera> cameras)
        {
            SupportedRenderingFeatures.active.rendersUIOverlay = false;
        }
    }
}
