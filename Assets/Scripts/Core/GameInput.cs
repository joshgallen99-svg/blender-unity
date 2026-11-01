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
        public static bool SwapSparePressed { get; private set; }
        public static bool AnyPressed { get; private set; }
        public static bool ConfirmPressed { get; private set; }
        public static bool GaragePressed { get; private set; }
        public static bool TourPressed { get; private set; }
        /// <summary>Menu navigation: -1 up, +1 down this frame (arrows, W/S, d-pad).</summary>
        public static int NavVertical { get; private set; }
        public static bool PhotoPressed { get; private set; }
        /// <summary>Photo-mode zoom: Q (in) / E (out).</summary>
        public static float Zoom { get; private set; }
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
            bool handbrake = false, reset = false, menu = false, fps = false, swap = false, any = false, confirm = false, garage = false, tour = false;
            int nav = 0;
            bool photo = false;
            float zoom = 0f;
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
                swap = kb.tKey.wasPressedThisFrame;
                any = kb.anyKey.wasPressedThisFrame;
                confirm = kb.enterKey.wasPressedThisFrame || kb.numpadEnterKey.wasPressedThisFrame;
                garage = kb.gKey.wasPressedThisFrame;
                tour = kb.f9Key.wasPressedThisFrame;
                photo = kb.f2Key.wasPressedThisFrame;
                if (kb.qKey.isPressed) zoom -= 1f;
                if (kb.eKey.isPressed) zoom += 1f;
                if (kb.upArrowKey.wasPressedThisFrame || kb.wKey.wasPressedThisFrame) nav = -1;
                if (kb.downArrowKey.wasPressedThisFrame || kb.sKey.wasPressedThisFrame) nav = 1;
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
                swap |= gp.buttonWest.wasPressedThisFrame;
                any |= gp.buttonSouth.wasPressedThisFrame || gp.startButton.wasPressedThisFrame;
                confirm |= gp.buttonSouth.wasPressedThisFrame;
                garage |= gp.selectButton.wasPressedThisFrame;
                if (gp.dpad.up.wasPressedThisFrame) nav = -1;
                if (gp.dpad.down.wasPressedThisFrame) nav = 1;
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
            swap = Input.GetKeyDown(KeyCode.T);
            any = Input.anyKeyDown;
            confirm = Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter);
            garage = Input.GetKeyDown(KeyCode.G);
            tour = Input.GetKeyDown(KeyCode.F9);
            photo = Input.GetKeyDown(KeyCode.F2);
            if (Input.GetKey(KeyCode.Q)) zoom -= 1f;
            if (Input.GetKey(KeyCode.E)) zoom += 1f;
            if (Input.GetKeyDown(KeyCode.UpArrow) || Input.GetKeyDown(KeyCode.W)) nav = -1;
            if (Input.GetKeyDown(KeyCode.DownArrow) || Input.GetKeyDown(KeyCode.S)) nav = 1;
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
            SwapSparePressed = swap;
            AnyPressed = any;
            ConfirmPressed = confirm;
            GaragePressed = garage;
            TourPressed = tour;
            NavVertical = nav;
            PhotoPressed = photo;
            Zoom = zoom;
            UsingGamepad = pad || (UsingGamepad && look == Vector2.zero && throttle == 0 && steer == 0);
        }
    }
}
