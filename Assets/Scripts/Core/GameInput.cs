using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Offroad.Core
{
    /// <summary>
    /// Polled input, readable from anywhere. Works with either Unity input backend:
    /// the Input System package (keyboard, mouse and gamepad) or the legacy Input Manager (keyboard and mouse).
    /// </summary>
    public static class GameInput
    {
        public static float Throttle { get; private set; }
        public static float Brake { get; private set; }
        public static float Steer { get; private set; }
        public static bool Handbrake { get; private set; }
        public static Vector2 Look { get; private set; }
        public static bool ResetPressed { get; private set; }
        public static bool MenuPressed { get; private set; }
        public static bool FpsTogglePressed { get; private set; }
        public static bool UsingGamepad { get; private set; }

        static int _lastFrame = -1;
#if !ENABLE_INPUT_SYSTEM && ENABLE_LEGACY_INPUT_MANAGER
        static bool _mouseAxesOk = true;
#endif

        /// <summary>Refreshes the values once per frame (safe to call more than once).</summary>
        public static void Poll()
        {
            if (_lastFrame == Time.frameCount) return;
            _lastFrame = Time.frameCount;

            float throttle = 0, brake = 0, steer = 0;
            bool handbrake = false, reset = false, menu = false, fps = false;
            Vector2 look = Vector2.zero;
            bool pad = false;

#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null)
            {
                if (kb.wKey.isPressed || kb.upArrowKey.isPressed) throttle = 1;
                if (kb.sKey.isPressed || kb.downArrowKey.isPressed) brake = 1;
                if (kb.aKey.isPressed || kb.leftArrowKey.isPressed) steer -= 1;
                if (kb.dKey.isPressed || kb.rightArrowKey.isPressed) steer += 1;
                handbrake = kb.spaceKey.isPressed;
                reset = kb.rKey.wasPressedThisFrame;
                menu = kb.escapeKey.wasPressedThisFrame || kb.pKey.wasPressedThisFrame;
                fps = kb.f1Key.wasPressedThisFrame;
            }
            var mouse = Mouse.current;
            if (mouse != null) look = mouse.delta.ReadValue() * 0.1f;

            var gp = Gamepad.current;
            if (gp != null)
            {
                float t = gp.rightTrigger.ReadValue(), b = gp.leftTrigger.ReadValue();
                float s = gp.leftStick.ReadValue().x;
                Vector2 r = gp.rightStick.ReadValue();
                if (t > 0.05f || b > 0.05f || Mathf.Abs(s) > 0.15f || r.sqrMagnitude > 0.04f) pad = true;
                throttle = Mathf.Max(throttle, t);
                brake = Mathf.Max(brake, b);
                if (Mathf.Abs(s) > 0.12f) steer = Mathf.Clamp(steer + s, -1, 1);
                if (r.sqrMagnitude > 0.02f) look += r * 4f;
                handbrake |= gp.buttonEast.isPressed;
                reset |= gp.buttonNorth.wasPressedThisFrame;
                menu |= gp.startButton.wasPressedThisFrame;
            }
#elif ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) throttle = 1;
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) brake = 1;
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) steer -= 1;
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) steer += 1;
            handbrake = Input.GetKey(KeyCode.Space);
            reset = Input.GetKeyDown(KeyCode.R);
            menu = Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.P);
            fps = Input.GetKeyDown(KeyCode.F1);
            if (_mouseAxesOk)
            {
                try { look = new Vector2(Input.GetAxisRaw("Mouse X"), Input.GetAxisRaw("Mouse Y")); }
                catch (System.ArgumentException) { _mouseAxesOk = false; }
            }
#endif
            Throttle = throttle;
            Brake = brake;
            Steer = steer;
            Handbrake = handbrake;
            Look = look;
            ResetPressed = reset;
            MenuPressed = menu;
            FpsTogglePressed = fps;
            UsingGamepad = pad || (UsingGamepad && look == Vector2.zero && throttle == 0 && steer == 0);
        }
    }
}
