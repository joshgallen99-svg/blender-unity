using System.Collections.Generic;
using Offroad.Game;
using Offroad.Garage;
using Offroad.Settings;
using Offroad.Vehicles;
using Offroad.World;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>Driving HUD: speedometer, compass with objective/landmark markers, objective, surface + tyre fit, spare wheel.</summary>
    public class HudView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly SpeedGauge _gauge;
        readonly Label _speed, _gear, _surface, _fitText, _objTitle, _objText, _objDist, _scrap, _fps, _spareName, _spareState, _hint, _warning;
        readonly VisualElement _fitDot, _spareFill, _compass, _objective, _spare, _speedo, _surfaceChip, _scrapBox;
        readonly List<Label> _ticks = new List<Label>();
        readonly List<float> _tickAngles = new List<float>();
        readonly List<Label> _markers = new List<Label>();
        VehicleAssembler _asm;
        float _shownAt, _fpsTimer, _textTimer, _fpsSmoothed = 60f;
        int _lastKmh = -1, _lastFitKey = -1;

        // Text is rebuilt at ~8 Hz (and only when it changes) so the HUD makes no garbage per frame.
        const float TextInterval = 0.125f;
        static readonly string[] SurfaceNames = { "SAND", "GRAVEL", "PACKED DIRT", "ROCK", "MUD", "QUICKSAND", "WASHBOARD" };
        static readonly string[] Numbers = BuildNumbers(400);
        readonly List<(float d, Landmark l)> _nearby = new List<(float, Landmark)>();
        readonly Vector3[] _markerTarget = new Vector3[8];
        readonly bool[] _markerObjective = new bool[8];
        int _markersUsed;

        static string[] BuildNumbers(int n)
        {
            var a = new string[n + 1];
            for (int i = 0; i <= n; i++) a[i] = i.ToString();
            return a;
        }

        static void SetText(Label l, string s)
        {
            if (l.text != s) l.text = s;
        }
        const float CompassWidth = 760f, CompassFov = 180f;

        public HudView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("hud");
            Root.pickingMode = PickingMode.Ignore;

            // Speedometer.
            _speedo = UIKit.Box("speedo", "slide-right");
            _gauge = new SpeedGauge();
            _gauge.AddToClassList("speedo-gauge");
            _speedo.Add(_gauge);
            _speed = UIKit.Heading("0", "speedo-value");
            _speedo.Add(_speed);
            _speedo.Add(UIKit.SubHeading("km/h", "speedo-unit"));
            _gear = UIKit.Heading("N", "speedo-gear");
            _speedo.Add(_gear);
            Root.Add(_speedo);

            _surfaceChip = UIKit.Box("surface-chip", "slide-right");
            _fitDot = UIKit.Box("fit-dot");
            _surfaceChip.Add(_fitDot);
            _surface = UIKit.SubHeading("Sand", "small");
            _surfaceChip.Add(_surface);
            _fitText = UIKit.Label("", "small");
            _fitText.style.marginLeft = 10;
            _surfaceChip.Add(_fitText);
            Root.Add(_surfaceChip);

            // Compass strip.
            _compass = UIKit.Box("compass", "drop");
            string[] names = { "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
            for (int a = 0; a < 360; a += 15)
            {
                bool cardinal = a % 45 == 0;
                var l = UIKit.SubHeading(cardinal ? names[a / 45] : "·", "compass-tick");
                if (cardinal && a % 90 == 0) l.AddToClassList("cardinal");
                _compass.Add(l);
                _ticks.Add(l);
                _tickAngles.Add(a);
            }
            for (int i = 0; i < 6; i++)
            {
                var m = UIKit.SubHeading("", "compass-marker");
                _compass.Add(m);
                _markers.Add(m);
            }
            _compass.Add(UIKit.Box("compass-center"));
            Root.Add(_compass);

            // Objective.
            _objective = UIKit.Box("objective", "slide-left");
            _objTitle = UIKit.SubHeading("", "objective-title");
            _objText = UIKit.Heading("", "objective-text");
            _objDist = UIKit.Label("", "objective-dist");
            _objective.Add(_objTitle);
            _objective.Add(_objText);
            _objective.Add(_objDist);
            Root.Add(_objective);

            _scrapBox = UIKit.Box("scrap", "slide-right");
            _scrapBox.Add(UIKit.Box("chip-dot"));
            _scrap = UIKit.Heading("0", "scrap-value");
            _scrapBox.Add(_scrap);
            Root.Add(_scrapBox);
            _fps = UIKit.Label("", "fps");
            Root.Add(_fps);

            // Spare wheel.
            _spare = UIKit.Box("spare", "slide-left");
            _spare.Add(UIKit.SubHeading("Spare wheel", "objective-title"));
            _spareName = UIKit.Heading("", "h2");
            _spareState = UIKit.Label("", "small");
            _spare.Add(_spareName);
            _spare.Add(_spareState);
            var bar = UIKit.Box("spare-bar");
            _spareFill = UIKit.Box("spare-fill");
            bar.Add(_spareFill);
            _spare.Add(bar);
            Root.Add(_spare);

            _hint = UIKit.Label("W/S drive & brake  ·  A/D steer  ·  Space handbrake  ·  R reset  ·  T swap to spare  ·  Esc pause", "hint", "anim");
            Root.Add(_hint);
            _warning = UIKit.Label("", "hazard-warning", "anim");
            Root.Add(_warning);
        }

        public void Show(MissionDef m)
        {
            _asm = _ui.vehicle ? _ui.vehicle.GetComponent<VehicleAssembler>() : null;
            _objTitle.text = m != null ? m.title.ToUpperInvariant() : "";
            UIKit.Show(Root);
            UIKit.Show(_speedo, 200);
            UIKit.Show(_surfaceChip, 300);
            UIKit.Show(_compass, 150);
            UIKit.Show(_objective, 250);
            UIKit.Show(_scrapBox, 300);
            UIKit.Show(_spare, 400);
            UIKit.Show(_hint, 900);
            _shownAt = Time.unscaledTime;
        }

        public void Tick()
        {
            if (Root.resolvedStyle.display == DisplayStyle.None) return;
            var v = _ui.vehicle;
            var runner = _ui.runner;
            if (!v) return;

            float kmh = Mathf.Abs(v.ForwardSpeed) * 3.6f;
            int kmhInt = Mathf.Clamp(Mathf.RoundToInt(kmh), 0, Numbers.Length - 1);
            if (kmhInt != _lastKmh) { _lastKmh = kmhInt; _speed.text = Numbers[kmhInt]; }
            _gauge.value = Mathf.Lerp(_gauge.value, kmh / 130f, 0.25f);
            _gauge.MarkDirtyRepaint();
            SetText(_gear, v.IsReversing ? "R" : kmh < 1f ? "N" : "D");
            _textTimer += Time.unscaledDeltaTime;
            bool refreshText = _textTimer >= TextInterval;
            if (refreshText) _textTimer = 0f;

            // Surface under the wheels and how well the fitted tyres suit it.
            Vector4 layers = Vector4.zero;
            float mud = 0f, quick = 0f, wash = 0f;
            int grounded = 0;
            foreach (var w in v.wheels)
            {
                if (!w.grounded) continue;
                layers += w.surface.layers;
                mud += w.surface.mud;
                quick += w.surface.quicksand;
                wash += w.surface.washboard;
                grounded++;
            }
            if (grounded > 0 && refreshText)
            {
                int best = 0;
                for (int i = 1; i < 4; i++) if (layers[i] > layers[best]) best = i;
                float inv = 1f / grounded;
                if (quick * inv > 0.3f) best = 5;
                else if (mud * inv > 0.4f) best = 4;
                else if (wash * inv > 0.3f) best = 6;
                var tireId = _asm ? _asm.ActiveTire : "at";
                float fit = v.tire.GripOn(new SurfaceInfo { layers = layers });
                bool good = fit >= 1.05f, poor = fit < 0.88f;
                int fitKey = best * 10 + (good ? 2 : poor ? 0 : 1) + (tireId.GetHashCode() & 0xffff) * 100;
                if (fitKey != _lastFitKey)
                {
                    _lastFitKey = fitKey;
                    _surface.text = SurfaceNames[best];
                    _fitText.text = $"{Catalog.Tire(tireId).name}: {(good ? "great grip" : poor ? "poor grip" : "ok")}";
                    _fitDot.style.backgroundColor = good ? new Color(0.52f, 0.81f, 0.44f) : poor ? new Color(0.92f, 0.38f, 0.3f) : new Color(0.95f, 0.75f, 0.3f);
                }
            }

            // Compass.
            var cam = Camera.main;
            float yaw = cam ? cam.transform.eulerAngles.y : v.transform.eulerAngles.y;
            float pxPerDeg = CompassWidth / CompassFov;
            for (int i = 0; i < _ticks.Count; i++)
            {
                float d = Mathf.DeltaAngle(yaw, _tickAngles[i]);
                var t = _ticks[i];
                bool visible = Mathf.Abs(d) < CompassFov * 0.5f - 6f;
                t.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
                if (visible)
                {
                    t.style.left = CompassWidth * 0.5f + d * pxPerDeg;
                    t.style.opacity = 1f - Mathf.Abs(d) / (CompassFov * 0.5f) * 0.7f;
                }
            }
            if (refreshText) AssignMarkers(v.transform.position, runner);
            for (int i = 0; i < _markersUsed; i++) Place(_markers[i], _markerTarget[i], v.transform.position, yaw, pxPerDeg, _markerObjective[i]);

            // FPS (smoothed every frame, shown at 4 Hz) and the spare-swap progress bar (every frame).
            float dt = Time.unscaledDeltaTime;
            if (dt > 0f) _fpsSmoothed = Mathf.Lerp(_fpsSmoothed, 1f / dt, 0.05f);
            _fpsTimer += dt;
            if (_fpsTimer > 0.25f)
            {
                _fpsTimer = 0f;
                SetText(_fps, GameSettings.Current.showFps ? $"{_fpsSmoothed:0} FPS  ·  {1000f / Mathf.Max(_fpsSmoothed, 1f):0.0} ms" : "");
            }
            if (_asm && runner && runner.Swapping) _spareFill.style.width = Length.Percent(runner.SwapProgress * 100f);

            if (!refreshText) return;

            // Sinking warning.
            bool sinking = v.QuicksandSink > 0.08f;
            if (sinking)
            {
                SetText(_warning, v.QuicksandSink > 0.3f ? "STUCK IN QUICKSAND  ·  press R to winch out" : "QUICKSAND  ·  keep moving!");
                _warning.AddToClassList("shown");
            }
            else _warning.RemoveFromClassList("shown");

            // Objective text and distance.
            if (runner && runner.Active != null)
            {
                SetText(_objText, runner.ObjectiveText);
                var target = runner.Target;
                SetText(_objDist, target.HasValue ? FormatDistance(Vector3.Distance(Flat(target.Value), Flat(v.transform.position))) : "");
            }
            SetText(_scrap, UIKit.Money(Progress.Scrap));

            // Spare wheel.
            if (_asm)
            {
                SetText(_spareName, Catalog.Tire(_asm.ActiveSpare).name.ToUpperInvariant());
                string state;
                if (runner && runner.Swapping) state = "Changing wheels...";
                else if (runner && runner.SpareUsed) state = "Used this expedition";
                else if (_asm.ActiveSpare == _asm.ActiveTire) state = "Same as fitted tyres";
                else state = Mathf.Abs(v.ForwardSpeed) > 1.5f ? "Stop, then press T to fit" : "Press T to fit";
                SetText(_spareState, state);
                _spareFill.style.width = Length.Percent((runner ? runner.SwapProgress : 0f) * 100f);
                _spare.style.opacity = runner && runner.SpareUsed && !runner.Swapping ? 0.45f : 1f;
            }

            // Hint fades after a while.
            if (Time.unscaledTime - _shownAt > 9f) _hint.RemoveFromClassList("shown");

        }

        /// <summary>Choose which targets the compass markers show and set their labels (at the text rate).</summary>
        void AssignMarkers(Vector3 pos, MissionRunner runner)
        {
            int used = 0;
            int max = Mathf.Min(_markers.Count, _markerTarget.Length);
            Vector3? objective = runner ? runner.Target : null;
            if (objective.HasValue)
            {
                SetMarker(used++, objective.Value, "•  " + FormatDistance(Vector3.Distance(Flat(objective.Value), Flat(pos))), true);
            }

            // Nearby landmarks: "?" until discovered.
            _nearby.Clear();
            foreach (var l in Landmark.All)
            {
                if (l.reward <= 0) continue;
                float d = Vector3.Distance(Flat(l.transform.position), Flat(pos));
                if (d < 700f) _nearby.Add((d, l));
            }
            _nearby.Sort((a, b) => a.d.CompareTo(b.d));
            foreach (var (d, l) in _nearby)
            {
                if (used >= max) break;
                if (objective.HasValue && Vector3.Distance(Flat(l.transform.position), Flat(objective.Value)) < 5f) continue;
                SetMarker(used++, l.transform.position, l.Discovered ? l.displayName : "?", false);
            }
            for (int i = used; i < _markers.Count; i++) _markers[i].style.display = DisplayStyle.None;
            _markersUsed = used;
        }

        void SetMarker(int i, Vector3 target, string text, bool objective)
        {
            _markerTarget[i] = target;
            _markerObjective[i] = objective;
            SetText(_markers[i], text);
            _markers[i].EnableInClassList("objective", objective);
        }

        static void Place(Label m, Vector3 target, Vector3 pos, float yaw, float pxPerDeg, bool objective)
        {
            Vector3 dir = target - pos;
            float bearing = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
            float d = Mathf.DeltaAngle(yaw, bearing);
            if (objective) d = Mathf.Clamp(d, -CompassFov * 0.5f + 8f, CompassFov * 0.5f - 8f);
            bool visible = Mathf.Abs(d) < CompassFov * 0.5f - 6f;
            m.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            if (visible) m.style.left = CompassWidth * 0.5f + d * pxPerDeg;
        }

        static Vector3 Flat(Vector3 v) => new Vector3(v.x, 0f, v.z);
        static string FormatDistance(float m) => m < 1000f ? $"{Mathf.RoundToInt(m / 10f) * 10} m" : $"{m / 1000f:0.0} km";
    }
}
