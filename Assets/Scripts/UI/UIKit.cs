using System;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>Small helpers for building the UI in code (fonts, labels, buttons, animated show/hide).</summary>
    public static class UIKit
    {
        public static Font Body, BodyBold, Head, HeadSemi;

        public static Label Label(string text, params string[] classes)
        {
            var l = new Label(text);
            foreach (var c in classes) l.AddToClassList(c);
            if (Body) l.style.unityFontDefinition = new StyleFontDefinition(Body);
            return l;
        }

        /// <summary>Condensed, uppercase display text.</summary>
        public static Label Heading(string text, params string[] classes)
        {
            var l = Label(text.ToUpperInvariant(), classes);
            if (Head) l.style.unityFontDefinition = new StyleFontDefinition(Head);
            return l;
        }

        public static Label SubHeading(string text, params string[] classes)
        {
            var l = Label(text.ToUpperInvariant(), classes);
            if (HeadSemi) l.style.unityFontDefinition = new StyleFontDefinition(HeadSemi);
            return l;
        }

        public static Button Button(string text, Action onClick, params string[] classes)
        {
            var b = new Button(onClick) { text = text.ToUpperInvariant() };
            b.AddToClassList("btn");
            foreach (var c in classes) b.AddToClassList(c);
            if (HeadSemi) b.style.unityFontDefinition = new StyleFontDefinition(HeadSemi);
            return b;
        }

        public static VisualElement Box(params string[] classes)
        {
            var v = new VisualElement();
            foreach (var c in classes) v.AddToClassList(c);
            return v;
        }

        /// <summary>Fade/slide an element in. Uses the .anim / .shown USS transitions.</summary>
        public static void Show(VisualElement e, long delayMs = 0)
        {
            e.style.display = DisplayStyle.Flex;
            e.pickingMode = PickingMode.Position;
            e.AddToClassList("anim");
            e.schedule.Execute(() => e.AddToClassList("shown")).StartingIn(16 + delayMs);
        }

        public static void Hide(VisualElement e, long durationMs = 320)
        {
            e.RemoveFromClassList("shown");
            e.schedule.Execute(() =>
            {
                if (!e.ClassListContains("shown")) e.style.display = DisplayStyle.None;
            }).StartingIn(durationMs);
        }

        public static void HideNow(VisualElement e)
        {
            e.RemoveFromClassList("shown");
            e.style.display = DisplayStyle.None;
        }

        /// <summary>Stagger the entrance of children (each child needs the .anim class).</summary>
        public static void Stagger(VisualElement parent, long stepMs = 55, long startMs = 0)
        {
            int i = 0;
            foreach (var c in parent.Children())
            {
                c.AddToClassList("anim");
                c.RemoveFromClassList("shown");
                var child = c;
                child.schedule.Execute(() => child.AddToClassList("shown")).StartingIn(startMs + stepMs * i++ + 16);
            }
        }

        /// <summary>Horizontal or vertical alpha gradient texture (USS has no gradients).</summary>
        public static Texture2D Gradient(Color from, Color to, bool horizontal, int size = 256)
        {
            var t = new Texture2D(horizontal ? size : 2, horizontal ? 2 : size, TextureFormat.RGBA32, false)
            {
                wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.HideAndDontSave,
            };
            for (int i = 0; i < size; i++)
            {
                float k = i / (size - 1f);
                var c = Color.Lerp(from, to, k * k * (3 - 2 * k));
                for (int j = 0; j < 2; j++)
                {
                    if (horizontal) t.SetPixel(i, j, c);
                    else t.SetPixel(j, i, c);
                }
            }
            t.Apply();
            return t;
        }

        public static string Money(int amount) => $"{amount:N0}";
    }

    /// <summary>Semicircular speedometer drawn with the vector API.</summary>
    public class SpeedGauge : VisualElement
    {
        public float value;      // 0..1
        public float redline = 0.85f;
        public Color track = new Color(1, 1, 1, 0.12f);
        public Color fill = new Color(0.95f, 0.55f, 0.16f);

        public SpeedGauge()
        {
            generateVisualContent += Draw;
        }

        void Draw(MeshGenerationContext ctx)
        {
            var p = ctx.painter2D;
            var r = contentRect;
            var c = new Vector2(r.width * 0.5f, r.height * 0.56f);
            float radius = Mathf.Min(r.width * 0.44f, r.height * 0.5f);
            const float a0 = 150f, a1 = 390f;

            p.lineWidth = 10f;
            p.lineCap = LineCap.Round;
            p.strokeColor = track;
            p.BeginPath();
            p.Arc(c, radius, Angle.Degrees(a0), Angle.Degrees(a1));
            p.Stroke();

            float v = Mathf.Clamp01(value);
            if (v > 0.002f)
            {
                p.strokeColor = fill;
                p.BeginPath();
                p.Arc(c, radius, Angle.Degrees(a0), Angle.Degrees(a0 + (a1 - a0) * v));
                p.Stroke();
            }

            p.lineWidth = 2f;
            p.lineCap = LineCap.Butt;
            for (int i = 0; i <= 12; i++)
            {
                float a = Mathf.Deg2Rad * (a0 + (a1 - a0) * i / 12f);
                var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                bool major = i % 3 == 0;
                p.strokeColor = i / 12f >= redline ? new Color(0.95f, 0.35f, 0.25f, 0.9f) : new Color(1, 1, 1, major ? 0.6f : 0.3f);
                p.BeginPath();
                p.MoveTo(c + dir * (radius - 20f));
                p.LineTo(c + dir * (radius - (major ? 32f : 26f)));
                p.Stroke();
            }
        }
    }

    /// <summary>Horizontal stat bar with an animated fill (width transition in USS).</summary>
    public class StatBar : VisualElement
    {
        readonly VisualElement _fill, _ghost;
        readonly Label _label, _value;

        public StatBar(string label)
        {
            AddToClassList("stat");
            _label = UIKit.Label(label, "stat-label");
            var track = UIKit.Box("stat-track");
            _ghost = UIKit.Box("stat-ghost");
            _fill = UIKit.Box("stat-fill");
            track.Add(_ghost);
            track.Add(_fill);
            _value = UIKit.Label("", "stat-value");
            Add(_label);
            Add(track);
            Add(_value);
        }

        /// <summary>value and preview in 0..1; preview shows what a change would do.</summary>
        public void Set(float value, string text, float? preview = null)
        {
            _fill.style.width = Length.Percent(Mathf.Clamp01(value) * 100f);
            float g = preview ?? value;
            _ghost.style.width = Length.Percent(Mathf.Clamp01(g) * 100f);
            _ghost.EnableInClassList("better", g > value + 0.005f);
            _ghost.EnableInClassList("worse", g < value - 0.005f);
            _value.text = text;
        }
    }

    /// <summary>Row of level pips (upgrade stages).</summary>
    public class Pips : VisualElement
    {
        public Pips(int level, int max)
        {
            AddToClassList("pips");
            for (int i = 0; i < max; i++)
            {
                var p = UIKit.Box("pip");
                p.EnableInClassList("on", i < level);
                Add(p);
            }
        }
    }
}
