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
        readonly Label _speed, _gear, _surface, _fitText, _objTitle, _objText, _objDist, _scrap, _fps, _spareName, _spareState, _hint;
        readonly VisualElement _fitDot, _spareFill, _compass, _objective, _spare, _speedo, _surfaceChip, _scrapBox;
        readonly List<Label> _ticks = new List<Label>();
        readonly List<float> _tickAngles = new List<float>();
        readonly List<Label> _markers = new List<Label>();
        VehicleAssembler _asm;
        float _shownAt, _fpsTimer, _fpsSmoothed = 60f;
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
            _speed.text = Mathf.RoundToInt(kmh).ToString();
            _gauge.value = Mathf.Lerp(_gauge.value, kmh / 130f, 0.25f);
            _gauge.MarkDirtyRepaint();
            _gear.text = v.IsReversing ? "R" : kmh < 1f ? "N" : "D";

            // Surface under the wheels and how well the fitted tyres suit it.
            Vector4 layers = Vector4.zero;
            int grounded = 0;
            foreach (var w in v.wheels)
            {
                if (!w.grounded) continue;
                layers += w.surface.layers;
                grounded++;
            }
            if (grounded > 0)
            {
                int best = 0;
                for (int i = 1; i < 4; i++) if (layers[i] > layers[best]) best = i;
                _surface.text = new[] { "SAND", "GRAVEL", "PACKED DIRT", "ROCK" }[best];
                var tire = Catalog.Tire(_asm ? _asm.ActiveTire : "at");
                float fit = v.tire.GripOn(new SurfaceInfo { layers = layers });
                bool good = fit >= 1.05f, poor = fit < 0.88f;
                _fitText.text = $"{tire.name}: {(good ? "great grip" : poor ? "poor grip" : "ok")}";
                _fitDot.style.backgroundColor = good ? new Color(0.52f, 0.81f, 0.44f) : poor ? new Color(0.92f, 0.38f, 0.3f) : new Color(0.95f, 0.75f, 0.3f);
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
            UpdateMarkers(v.transform.position, yaw, pxPerDeg, runner);

            // Objective text and distance.
            if (runner && runner.Active != null)
            {
                _objText.text = runner.ObjectiveText;
                var target = runner.Target;
                _objDist.text = target.HasValue ? FormatDistance(Vector3.Distance(Flat(target.Value), Flat(v.transform.position))) : "";
            }
            _scrap.text = UIKit.Money(Progress.Scrap);

            // Spare wheel.
            if (_asm)
            {
                _spareName.text = Catalog.Tire(_asm.ActiveSpare).name.ToUpperInvariant();
                string state;
                if (runner && runner.Swapping) state = "Changing wheels...";
                else if (runner && runner.SpareUsed) state = "Used this expedition";
                else if (_asm.ActiveSpare == _asm.ActiveTire) state = "Same as fitted tyres";
                else state = Mathf.Abs(v.ForwardSpeed) > 1.5f ? "Stop, then press T to fit" : "Press T to fit";
                _spareState.text = state;
                _spareFill.style.width = Length.Percent((runner ? runner.SwapProgress : 0f) * 100f);
                _spare.style.opacity = runner && runner.SpareUsed && !runner.Swapping ? 0.45f : 1f;
            }

            // Hint fades after a while.
            if (Time.unscaledTime - _shownAt > 9f) _hint.RemoveFromClassList("shown");

            // FPS.
            float dt = Time.unscaledDeltaTime;
            if (dt > 0f) _fpsSmoothed = Mathf.Lerp(_fpsSmoothed, 1f / dt, 0.05f);
            _fpsTimer += dt;
            if (_fpsTimer > 0.25f)
            {
                _fpsTimer = 0f;
                _fps.text = GameSettings.Current.showFps ? $"{_fpsSmoothed:0} FPS  ·  {1000f / Mathf.Max(_fpsSmoothed, 1f):0.0} ms" : "";
            }
        }

        void UpdateMarkers(Vector3 pos, float yaw, float pxPerDeg, MissionRunner runner)
        {
            int used = 0;
            Vector3? objective = runner ? runner.Target : null;
            if (objective.HasValue) Place(_markers[used++], objective.Value, pos, yaw, pxPerDeg, "•  " + FormatDistance(Vector3.Distance(Flat(objective.Value), Flat(pos))), true);

            // Nearby landmarks: "?" until discovered.
            var nearby = new List<(float d, Landmark l)>();
            foreach (var l in Landmark.All)
            {
                if (l.reward <= 0) continue;
                float d = Vector3.Distance(Flat(l.transform.position), Flat(pos));
                if (d < 700f) nearby.Add((d, l));
            }
            nearby.Sort((a, b) => a.d.CompareTo(b.d));
            foreach (var (d, l) in nearby)
            {
                if (used >= _markers.Count) break;
                if (objective.HasValue && Vector3.Distance(Flat(l.transform.position), Flat(objective.Value)) < 5f) continue;
                Place(_markers[used++], l.transform.position, pos, yaw, pxPerDeg, l.Discovered ? l.displayName : "?", false);
            }
            for (int i = used; i < _markers.Count; i++) _markers[i].style.display = DisplayStyle.None;
        }

        static void Place(Label m, Vector3 target, Vector3 pos, float yaw, float pxPerDeg, string text, bool objective)
        {
            Vector3 dir = target - pos;
            float bearing = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
            float d = Mathf.DeltaAngle(yaw, bearing);
            if (objective) d = Mathf.Clamp(d, -CompassFov * 0.5f + 8f, CompassFov * 0.5f - 8f);
            bool visible = Mathf.Abs(d) < CompassFov * 0.5f - 6f;
            m.style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
            m.text = text;
            m.EnableInClassList("objective", objective);
            m.style.left = CompassWidth * 0.5f + d * pxPerDeg;
        }

        static Vector3 Flat(Vector3 v) => new Vector3(v.x, 0f, v.z);
        static string FormatDistance(float m) => m < 1000f ? $"{Mathf.RoundToInt(m / 10f) * 10} m" : $"{m / 1000f:0.0} km";
    }
}
