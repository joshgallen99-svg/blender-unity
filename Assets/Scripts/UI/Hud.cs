using Offroad.Settings;
using Offroad.Vehicles;
using UnityEngine;

namespace Offroad.UI
{
    /// <summary>Minimal driving HUD: speed, gear, FPS counter and a fading controls hint.</summary>
    public class Hud : MonoBehaviour
    {
        public OffroadVehicle vehicle;
        public SettingsMenu menu;
        public float hintDuration = 10f;

        GUIStyle _speed, _unit, _hint, _fps;
        float _fpsSmoothed = 60f, _fpsTimer;
        string _fpsText = "";
        float _startTime;

        void Start() => _startTime = Time.unscaledTime;

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            if (dt > 0f) _fpsSmoothed = Mathf.Lerp(_fpsSmoothed, 1f / dt, 0.05f);
            _fpsTimer += dt;
            if (_fpsTimer > 0.25f)
            {
                _fpsTimer = 0f;
                _fpsText = $"{_fpsSmoothed:0} FPS  ({1000f / Mathf.Max(_fpsSmoothed, 1f):0.0} ms)";
            }
        }

        void EnsureStyles()
        {
            if (_speed != null) return;
            _speed = new GUIStyle { fontSize = 64, fontStyle = FontStyle.Bold, alignment = TextAnchor.LowerRight, normal = { textColor = Color.white } };
            _unit = new GUIStyle { fontSize = 20, alignment = TextAnchor.LowerRight, normal = { textColor = new Color(1f, 1f, 1f, 0.75f) } };
            _hint = new GUIStyle { fontSize = 18, alignment = TextAnchor.LowerLeft, normal = { textColor = Color.white } };
            _fps = new GUIStyle { fontSize = 16, fontStyle = FontStyle.Bold, normal = { textColor = new Color(0.6f, 1f, 0.6f) } };
        }

        void OnGUI()
        {
            if (menu && menu.IsOpen) return;
            EnsureStyles();
            float scale = Mathf.Clamp(Screen.height / 1080f, 0.6f, 2f);
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
            float sw = Screen.width / scale, sh = Screen.height / scale;

            if (vehicle)
            {
                float kmh = Mathf.Abs(vehicle.ForwardSpeed) * 3.6f;
                Shadowed(new Rect(sw - 260, sh - 120, 220, 80), Mathf.RoundToInt(kmh).ToString(), _speed);
                string gear = vehicle.IsReversing ? "R" : kmh < 1f ? "N" : "D";
                Shadowed(new Rect(sw - 260, sh - 50, 220, 30), $"km/h   {gear}", _unit);
            }

            if (GameSettings.Current.showFps) Shadowed(new Rect(16, 12, 300, 24), _fpsText, _fps);

            float age = Time.unscaledTime - _startTime;
            if (age < hintDuration)
            {
                float a = Mathf.Clamp01(hintDuration - age);
                var c = GUI.color;
                GUI.color = new Color(1, 1, 1, a);
                Shadowed(new Rect(28, sh - 110, 900, 90),
                    "W/S  drive & brake   ·   A/D  steer   ·   Space  handbrake   ·   R  reset\n" +
                    "Mouse  look around   ·   Esc  settings & graphics presets   ·   F1  FPS counter", _hint);
                GUI.color = c;
            }
        }

        static void Shadowed(Rect r, string text, GUIStyle style)
        {
            var c = style.normal.textColor;
            style.normal.textColor = new Color(0, 0, 0, 0.55f * GUI.color.a);
            GUI.Label(new Rect(r.x + 2, r.y + 2, r.width, r.height), text, style);
            style.normal.textColor = c;
            GUI.Label(r, text, style);
        }
    }
}
