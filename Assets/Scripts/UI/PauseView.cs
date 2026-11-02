using System;
using Offroad.Settings;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>Pause menu with the graphics settings; also opened from the title screen.</summary>
    public class PauseView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly VisualElement _panel, _shade;
        bool _fromTitle;

        static readonly float[] ViewDistances = { 350f, 450f, 550f, 700f, 800f, 950f, 1100f, 1400f };
        static readonly float[] Details = { 0.4f, 0.5f, 0.7f, 1f, 1.3f, 1.6f, 2f };
        static readonly float[] Scales = { 0.5f, 0.6f, 0.7f, 0.8f, 0.9f, 1f };

        public PauseView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("screen");
            _shade = UIKit.Box("pause-shade", "anim");
            Root.Add(_shade);
            _panel = UIKit.Box("pause-panel", "slide-left");
            Root.Add(_panel);
            GameSettings.Changed += _ => { if (Root.resolvedStyle.display != DisplayStyle.None) Rebuild(false); };
        }

        public void Show(bool fromTitle)
        {
            _fromTitle = fromTitle;
            Rebuild(true);
            UIKit.Show(Root);
            UIKit.Show(_shade);
            UIKit.Show(_panel, 40);
        }

        public void Hide() => UIKit.Hide(Root);

        void Rebuild(bool animate)
        {
            _panel.Clear();
            _panel.Add(UIKit.SubHeading(_fromTitle ? "Options" : "Expedition paused", "kicker"));
            _panel.Add(UIKit.Heading(_fromTitle ? "Settings" : "Paused", "h1"));

            var actions = UIKit.Box("row");
            actions.style.flexWrap = Wrap.Wrap;
            actions.style.marginTop = 10;
            actions.style.marginBottom = 18;
            if (_fromTitle)
            {
                actions.Add(UIKit.Button("Back", () => { Hide(); }, "btn-primary"));
            }
            else
            {
                actions.Add(UIKit.Button("Resume", () => _ui.flow.Resume(), "btn-primary"));
                actions.Add(UIKit.Button("Reset vehicle", () => _ui.flow.ResetVehicleUpright()));
                actions.Add(UIKit.Button("Abandon", () => _ui.flow.AbandonMission(), "btn-ghost"));
            }
            _panel.Add(actions);

            var s = GameSettings.Current;
            _panel.Add(UIKit.SubHeading("Graphics preset", "h3"));
            var seg = UIKit.Box("segment");
            foreach (var p in new[] { QualityPreset.BatterySaver, QualityPreset.Low, QualityPreset.Medium, QualityPreset.High })
            {
                var b = UIKit.Button(GameSettings.Describe(p), () => GameSettings.ApplyPreset(p));
                b.EnableInClassList("on", s.preset == p);
                seg.Add(b);
            }
            _panel.Add(seg);
            if (s.preset == QualityPreset.Custom) _panel.Add(UIKit.Label("Custom settings", "small"));

            var rows = UIKit.Box();
            Row(rows, "Resolution scale", $"{Mathf.RoundToInt(s.renderScale * 100)}%", d => GameSettings.Modify(x => x.renderScale = Step(Scales, x.renderScale, d)));
            Row(rows, "Shadows", s.shadows.ToString(), d => GameSettings.Modify(x => x.shadows = Cycle(x.shadows, d)));
            Row(rows, "View distance", $"{Mathf.RoundToInt(s.viewDistance)} m", d => GameSettings.Modify(x => x.viewDistance = Step(ViewDistances, x.viewDistance, d)));
            Row(rows, "Scenery detail", $"{s.detail:0.0}x", d => GameSettings.Modify(x => x.detail = Step(Details, x.detail, d)));
            Row(rows, "Post effects", s.postEffects ? "On" : "Off", d => GameSettings.Modify(x => x.postEffects = !x.postEffects));
            Row(rows, "Anti-aliasing", s.antiAliasing.ToString(), d => GameSettings.Modify(x => x.antiAliasing = Cycle(x.antiAliasing, d)));
            Row(rows, "Frame cap", s.frameCap == FrameCap.Fps30 ? "30 FPS" : s.frameCap == FrameCap.Fps60 ? "60 FPS" : "Display", d => GameSettings.Modify(x => x.frameCap = Cycle(x.frameCap, d)));
            Row(rows, "FPS counter", s.showFps ? "On" : "Off", d => GameSettings.Modify(x => x.showFps = !x.showFps));
            _panel.Add(rows);
            if (animate) UIKit.Stagger(rows, 30, 150);

            _panel.Add(UIKit.Box("divider"));
            var help = UIKit.Label("Battery Saver caps at 30 FPS and lowers resolution to keep a fanless laptop cool. " +
                                   "Medium targets 60 FPS on an M-series MacBook Air.", "small");
            help.style.whiteSpace = WhiteSpace.Normal;
            _panel.Add(help);
            _panel.Add(UIKit.Label("Drive W/S · Steer A/D · Handbrake Space · Auto/Manual M · Gears Shift/Ctrl (manual 1st = low range) · Winch F (hold to reel) · Recover R · Spare T · Look mouse · F1 FPS", "small"));
        }

        static void Row(VisualElement parent, string name, string value, Action<int> change)
        {
            var row = UIKit.Box("setting-row");
            row.Add(UIKit.Label(name, "setting-name"));
            row.Add(UIKit.Button("<", () => change(-1), "btn-small", "btn-arrow"));
            row.Add(UIKit.SubHeading(value, "setting-value"));
            row.Add(UIKit.Button(">", () => change(1), "btn-small", "btn-arrow"));
            parent.Add(row);
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
    }
}
