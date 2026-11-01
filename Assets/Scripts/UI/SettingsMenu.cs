using System;
using Offroad.Core;
using Offroad.Settings;
using Offroad.Vehicles;
using UnityEngine;

namespace Offroad.UI
{
    /// <summary>
    /// Pause + settings menu (Esc / P / Start). Immediate-mode GUI so it needs no assets;
    /// it will move to UI Toolkit once the visual style is settled.
    /// </summary>
    public class SettingsMenu : MonoBehaviour
    {
        public OffroadVehicle vehicle;
        public bool IsOpen { get; private set; }

        GUIStyle _panel, _title, _label, _value, _button, _buttonOn, _small;
        Texture2D _panelTex, _btnTex, _btnOnTex, _btnHoverTex;
        float _uiScale = 1f;

        static readonly float[] ViewDistances = { 350f, 450f, 550f, 700f, 800f, 950f, 1100f, 1400f };
        static readonly float[] Details = { 0.4f, 0.5f, 0.7f, 1f, 1.3f, 1.6f, 2f };
        static readonly float[] Scales = { 0.5f, 0.6f, 0.7f, 0.8f, 0.9f, 1f };

        void Start()
        {
            GameSettings.Apply();
            SetOpen(false);
        }

        void Update()
        {
            GameInput.Poll();
            if (GameInput.MenuPressed) SetOpen(!IsOpen);
            if (GameInput.FpsTogglePressed) GameSettings.Modify(s => s.showFps = !s.showFps);
            if (!IsOpen && Input_LockCursorRequested()) LockCursor(true);
        }

        static bool Input_LockCursorRequested()
        {
#if ENABLE_INPUT_SYSTEM
            var m = UnityEngine.InputSystem.Mouse.current;
            return m != null && m.leftButton.wasPressedThisFrame && Cursor.lockState != CursorLockMode.Locked;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButtonDown(0) && Cursor.lockState != CursorLockMode.Locked;
#else
            return false;
#endif
        }

        public void SetOpen(bool open)
        {
            IsOpen = open;
            Time.timeScale = open ? 0f : 1f;
            AudioListener.pause = open;
            LockCursor(!open);
        }

        static void LockCursor(bool locked)
        {
            if (Application.isEditor && !Application.isFocused) return;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }

        void EnsureStyles()
        {
            if (_panel != null) return;
            _panelTex = Solid(new Color(0.06f, 0.07f, 0.08f, 0.86f));
            _btnTex = Solid(new Color(1f, 1f, 1f, 0.08f));
            _btnHoverTex = Solid(new Color(1f, 1f, 1f, 0.16f));
            _btnOnTex = Solid(new Color(0.95f, 0.55f, 0.2f, 0.9f));
            _panel = new GUIStyle { normal = { background = _panelTex }, padding = new RectOffset(28, 28, 22, 22) };
            _title = new GUIStyle { fontSize = 30, fontStyle = FontStyle.Bold, normal = { textColor = Color.white } };
            _label = new GUIStyle { fontSize = 17, alignment = TextAnchor.MiddleLeft, normal = { textColor = new Color(0.85f, 0.85f, 0.85f) } };
            _value = new GUIStyle(_label) { alignment = TextAnchor.MiddleCenter, normal = { textColor = Color.white }, fontStyle = FontStyle.Bold };
            _small = new GUIStyle(_label) { fontSize = 14, wordWrap = true, normal = { textColor = new Color(0.7f, 0.7f, 0.7f) } };
            _button = new GUIStyle
            {
                fontSize = 16, alignment = TextAnchor.MiddleCenter, padding = new RectOffset(10, 10, 6, 6),
                normal = { background = _btnTex, textColor = Color.white },
                hover = { background = _btnHoverTex, textColor = Color.white },
                active = { background = _btnOnTex, textColor = Color.white },
            };
            _buttonOn = new GUIStyle(_button) { normal = { background = _btnOnTex, textColor = Color.white }, hover = { background = _btnOnTex, textColor = Color.white } };
        }

        static Texture2D Solid(Color c)
        {
            var t = new Texture2D(1, 1) { hideFlags = HideFlags.HideAndDontSave };
            t.SetPixel(0, 0, c);
            t.Apply();
            return t;
        }

        void OnGUI()
        {
            if (!IsOpen) return;
            EnsureStyles();
            _uiScale = Mathf.Clamp(Screen.height / 1080f, 0.6f, 2f);
            GUI.matrix = Matrix4x4.Scale(new Vector3(_uiScale, _uiScale, 1f));
            float w = 560f, h = 660f;
            float sw = Screen.width / _uiScale, sh = Screen.height / _uiScale;
            GUILayout.BeginArea(new Rect((sw - w) / 2f, (sh - h) / 2f, w, h), _panel);

            GUILayout.Label("Paused", _title);
            GUILayout.Space(14);

            var s = GameSettings.Current;
            GUILayout.Label("Graphics preset", _label);
            GUILayout.BeginHorizontal();
            foreach (QualityPreset p in new[] { QualityPreset.BatterySaver, QualityPreset.Low, QualityPreset.Medium, QualityPreset.High })
                if (GUILayout.Button(GameSettings.Describe(p), s.preset == p ? _buttonOn : _button, GUILayout.Height(36)))
                    GameSettings.ApplyPreset(p);
            GUILayout.EndHorizontal();
            if (s.preset == QualityPreset.Custom) GUILayout.Label("Custom settings", _small);
            GUILayout.Space(12);

            Row("Resolution scale", $"{Mathf.RoundToInt(s.renderScale * 100)}%",
                d => GameSettings.Modify(x => x.renderScale = Step(Scales, x.renderScale, d)));
            Row("Shadows", s.shadows.ToString(),
                d => GameSettings.Modify(x => x.shadows = Cycle(x.shadows, d)));
            Row("View distance", $"{Mathf.RoundToInt(s.viewDistance)} m",
                d => GameSettings.Modify(x => x.viewDistance = Step(ViewDistances, x.viewDistance, d)));
            Row("Scenery detail", $"{s.detail:0.0}x",
                d => GameSettings.Modify(x => x.detail = Step(Details, x.detail, d)));
            Row("Post effects", s.postEffects ? "On" : "Off",
                d => GameSettings.Modify(x => x.postEffects = !x.postEffects));
            Row("Anti-aliasing", s.antiAliasing.ToString(),
                d => GameSettings.Modify(x => x.antiAliasing = Cycle(x.antiAliasing, d)));
            Row("Frame cap", s.frameCap == FrameCap.Fps30 ? "30 FPS" : s.frameCap == FrameCap.Fps60 ? "60 FPS" : "Display",
                d => GameSettings.Modify(x => x.frameCap = Cycle(x.frameCap, d)));
            Row("FPS counter (F1)", s.showFps ? "On" : "Off",
                d => GameSettings.Modify(x => x.showFps = !x.showFps));

            GUILayout.Space(16);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Resume", _buttonOn, GUILayout.Height(40))) SetOpen(false);
            if (vehicle && GUILayout.Button("Reset vehicle", _button, GUILayout.Height(40)))
            {
                vehicle.ResetUpright();
                SetOpen(false);
            }
            if (Application.platform != RuntimePlatform.WebGLPlayer && GUILayout.Button("Quit", _button, GUILayout.Height(40)))
                Application.Quit();
            GUILayout.EndHorizontal();
            GUILayout.Space(10);
            GUILayout.Label("Drive: W/S or arrows · Steer: A/D · Handbrake: Space · Reset: R · Look: mouse · " +
                            "Gamepad: triggers, left stick, B handbrake, Y reset", _small);
            GUILayout.EndArea();
        }

        void Row(string name, string value, Action<int> change)
        {
            GUILayout.BeginHorizontal(GUILayout.Height(34));
            GUILayout.Label(name, _label, GUILayout.Width(220));
            if (GUILayout.Button("<", _button, GUILayout.Width(40), GUILayout.Height(30))) change(-1);
            GUILayout.Label(value, _value, GUILayout.Width(170), GUILayout.Height(30));
            if (GUILayout.Button(">", _button, GUILayout.Width(40), GUILayout.Height(30))) change(1);
            GUILayout.EndHorizontal();
        }

        static float Step(float[] options, float current, int dir)
        {
            int best = 0;
            for (int i = 1; i < options.Length; i++)
                if (Mathf.Abs(options[i] - current) < Mathf.Abs(options[best] - current)) best = i;
            return options[Mathf.Clamp(best + dir, 0, options.Length - 1)];
        }

        static T Cycle<T>(T current, int dir) where T : Enum
        {
            var values = (T[])Enum.GetValues(typeof(T));
            int i = Array.IndexOf(values, current);
            return values[(i + dir + values.Length) % values.Length];
        }

        void OnDestroy()
        {
            Time.timeScale = 1f;
            foreach (var t in new[] { _panelTex, _btnTex, _btnOnTex, _btnHoverTex })
                if (t) Destroy(t);
        }
    }
}
