using System;
using Offroad.Garage;
using Offroad.World;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>
    /// Garage: tabs for body, tyres, spare, engine, suspension, kit and paint. Hovering a part previews
    /// its effect on the stat bars (green/red ghosts); changes are fitted to the vehicle live.
    /// </summary>
    public class GarageView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly VisualElement _left, _right, _tabs, _top;
        readonly ScrollView _cards;
        readonly Label _scrap;
        readonly StatBar _power, _weight, _speed, _sand, _gravel, _rock;
        string _tab = "Tyres";

        static readonly string[] Tabs = { "Body", "Tyres", "Spare", "Engine", "Suspension", "Kit", "Paint" };

        struct Stats { public float power, weight, speed; public Vector4 grip; }

        public GarageView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("screen");
            Root.pickingMode = PickingMode.Ignore;
            var shade = UIKit.Box("title-shade");
            shade.style.backgroundImage = UIKit.Gradient(new Color(0.03f, 0.03f, 0.035f, 0.9f), new Color(0, 0, 0, 0), true);
            shade.style.width = Length.Percent(55);
            shade.pickingMode = PickingMode.Ignore;
            Root.Add(shade);

            _top = UIKit.Box("garage-top", "drop");
            var titles = UIKit.Box();
            titles.Add(UIKit.SubHeading("Base camp workshop", "kicker"));
            titles.Add(UIKit.Heading("Garage", "h1"));
            _top.Add(titles);
            _top.Add(UIKit.Box("spacer"));
            var chip = UIKit.Box("chip");
            chip.Add(UIKit.Box("chip-dot"));
            _scrap = UIKit.Heading("0", "h2");
            chip.Add(_scrap);
            chip.Add(UIKit.Label("  scrap", "small"));
            _top.Add(chip);
            Root.Add(_top);

            _left = UIKit.Box("garage-left", "slide-left");
            _left.style.top = 140;
            _tabs = UIKit.Box("tabs");
            _left.Add(_tabs);
            _cards = new ScrollView(ScrollViewMode.Vertical) { horizontalScrollerVisibility = ScrollerVisibility.Hidden };
            _cards.AddToClassList("cards");
            _left.Add(_cards);
            Root.Add(_left);

            _right = UIKit.Box("garage-right", "panel", "slide-right");
            _right.Add(UIKit.SubHeading("Current build", "kicker"));
            _power = new StatBar("Power");
            _weight = new StatBar("Weight");
            _speed = new StatBar("Top speed");
            _sand = new StatBar("Sand grip");
            _gravel = new StatBar("Gravel grip");
            _rock = new StatBar("Rock grip");
            foreach (var b in new[] { _power, _weight, _speed, _sand, _gravel, _rock }) _right.Add(b);
            _right.Add(UIKit.Box("divider"));
            var buttons = UIKit.Box("row");
            buttons.Add(UIKit.Button("Back", () => _ui.flow.GoTitle(), "btn-ghost"));
            buttons.Add(UIKit.Box("spacer"));
            buttons.Add(UIKit.Button("Expeditions", () => _ui.flow.GoMissions(), "btn-primary"));
            _right.Add(buttons);
            Root.Add(_right);

            Loadout.Changed += _ => { if (Visible) Refresh(false); };
            Progress.ScrapChanged += _ => { if (Visible) _scrap.text = UIKit.Money(Progress.Scrap); };
        }

        bool Visible => Root.resolvedStyle.display != DisplayStyle.None;

        public void Show()
        {
            UIKit.Show(Root);
            UIKit.Show(_top, 50);
            UIKit.Show(_left, 120);
            UIKit.Show(_right, 220);
            Refresh(true);
        }

        void Refresh(bool animate)
        {
            _scrap.text = UIKit.Money(Progress.Scrap);
            _tabs.Clear();
            foreach (var t in Tabs)
            {
                var b = new Button(() => { _tab = t; Refresh(true); }) { text = t.ToUpperInvariant() };
                b.AddToClassList("tab");
                if (UIKit.HeadSemi) b.style.unityFontDefinition = new StyleFontDefinition(UIKit.HeadSemi);
                b.EnableInClassList("on", t == _tab);
                _tabs.Add(b);
            }
            _cards.Clear();
            var l = Loadout.Current;
            switch (_tab)
            {
                case "Body":
                    foreach (var b in Catalog.Bodies) _cards.Add(BodyCard(b, l));
                    break;
                case "Tyres":
                    foreach (var t in Catalog.Tires) _cards.Add(TireCard(t, l));
                    break;
                case "Spare":
                    _cards.Add(Note("The spare rides on the back. Once per expedition you can stop and swap it on " +
                                    "(T / gamepad X). Pick the tyre you might need where you're going."));
                    foreach (var t in Catalog.Tires) if (l.ownedTires.Contains(t.id)) _cards.Add(SpareCard(t, l));
                    break;
                case "Engine":
                    _cards.Add(UpgradeCard(Catalog.Engine, l.engineLevel, x => x.engineLevel++));
                    break;
                case "Suspension":
                    _cards.Add(UpgradeCard(Catalog.Suspension, l.suspensionLevel, x => x.suspensionLevel++));
                    break;
                case "Kit":
                    foreach (var a in Catalog.Accessories) _cards.Add(KitCard(a, l));
                    break;
                case "Paint":
                    _cards.Add(PaintCard(l));
                    break;
            }
            if (animate) UIKit.Stagger(_cards.contentContainer, 50, 60);
            UpdateStats(null);
        }

        // ------------------------------------------------------------------ cards

        VisualElement Card(string title, string tag, string blurb, bool fitted, Func<Loadout, Loadout> preview)
        {
            var card = UIKit.Box("card");
            card.EnableInClassList("fitted", fitted);
            var head = UIKit.Box("row");
            head.Add(UIKit.Heading(title, "card-title"));
            if (!string.IsNullOrEmpty(tag)) head.Add(UIKit.SubHeading(tag, "card-tag"));
            card.Add(head);
            if (!string.IsNullOrEmpty(blurb))
            {
                var b = UIKit.Label(blurb, "body");
                b.style.whiteSpace = WhiteSpace.Normal;
                card.Add(b);
            }
            if (preview != null)
            {
                card.RegisterCallback<PointerEnterEvent>(_ => UpdateStats(preview(Clone(Loadout.Current))));
                card.RegisterCallback<PointerLeaveEvent>(_ => UpdateStats(null));
            }
            return card;
        }

        VisualElement Actions(VisualElement card)
        {
            var row = UIKit.Box("row");
            row.style.marginTop = 10;
            card.Add(row);
            return row;
        }

        void Try(bool ok, string what)
        {
            if (!ok) _ui.Toasts?.Push("", $"Not enough scrap for {what}", "Discover landmarks and finish expeditions to earn more", 2600, small: true);
        }

        VisualElement BodyCard(Catalog.BodyDef b, Loadout l)
        {
            bool owned = l.ownedBodies.Contains(b.id), fitted = l.body == b.id;
            var card = Card(b.name, fitted ? "Fitted" : owned ? "Owned" : $"{b.price} scrap", b.blurb, fitted, x => { x.body = b.id; return x; });
            card.Add(UIKit.Label($"{b.mass:0} kg  ·  {b.steerAngle:0}° steering lock", "small"));
            var row = Actions(card);
            if (!fitted) row.Add(UIKit.Button(owned ? "Fit" : $"Buy  {b.price}", () => Try(l.BuyOrEquipBody(b), b.name), owned ? "btn-ghost" : "btn-primary"));
            return card;
        }

        VisualElement TireCard(Catalog.TireDef t, Loadout l)
        {
            bool owned = l.ownedTires.Contains(t.id), fitted = l.tire == t.id;
            int lvl = l.TireLevel(t.id);
            var card = Card(t.name, fitted ? "Fitted" : owned ? "Owned" : $"{t.price} scrap", t.blurb, fitted, x => { x.tire = t.id; return x; });
            float m = 1f + t.GripPerLevel * lvl;
            var grid = UIKit.Box();
            grid.style.marginTop = 8;
            var sand = new StatBar("Sand"); sand.Set(t.grip.x * m / 1.4f, $"{t.grip.x * m:0.00}x");
            var grav = new StatBar("Gravel"); grav.Set(t.grip.y * m / 1.4f, $"{t.grip.y * m:0.00}x");
            var soil = new StatBar("Dirt"); soil.Set(t.grip.z * m / 1.4f, $"{t.grip.z * m:0.00}x");
            var rock = new StatBar("Rock"); rock.Set(t.grip.w * m / 1.4f, $"{t.grip.w * m:0.00}x");
            foreach (var s in new[] { sand, grav, soil, rock }) grid.Add(s);
            card.Add(grid);
            var row = Actions(card);
            if (!fitted) row.Add(UIKit.Button(owned ? "Fit" : $"Buy  {t.price}", () => Try(l.BuyOrEquipTire(t), t.name), owned ? "btn-ghost" : "btn-primary"));
            if (owned)
            {
                row.Add(UIKit.Box("spacer"));
                row.Add(UIKit.SubHeading("Grade", "small"));
                row.Add(new Pips(lvl, t.upgradeCost.Length));
                if (lvl < t.upgradeCost.Length)
                    row.Add(UIKit.Button($"Upgrade  {t.upgradeCost[lvl]}", () => Try(l.UpgradeTire(t), "that upgrade"), "btn-small"));
            }
            return card;
        }

        VisualElement SpareCard(Catalog.TireDef t, Loadout l)
        {
            bool mounted = l.spare == t.id;
            var card = Card(t.name, mounted ? "On the back" : "", "", mounted, null);
            var row = Actions(card);
            if (!mounted) row.Add(UIKit.Button("Mount as spare", () => l.SetSpare(t), "btn-ghost"));
            return card;
        }

        VisualElement UpgradeCard(Catalog.UpgradeTrack track, int level, Action<Loadout> bump)
        {
            var card = Card(track.name, $"Stage {level}/{track.MaxLevel}", track.blurb, level > 0,
                level < track.MaxLevel ? (Func<Loadout, Loadout>)(x => { bump(x); return x; }) : null);
            var row = Actions(card);
            row.Add(new Pips(level, track.MaxLevel));
            row.Add(UIKit.Box("spacer"));
            if (level < track.MaxLevel)
                row.Add(UIKit.Button($"Upgrade  {track.cost[level]}", () => Try(Loadout.Current.Upgrade(track), "that upgrade"), "btn-primary"));
            else row.Add(UIKit.SubHeading("Maxed out", "small", "accent"));
            return card;
        }

        VisualElement KitCard(Catalog.AccessoryDef a, Loadout l)
        {
            bool owned = l.ownedAccessories.Contains(a.id), fitted = l.Fitted(a.id);
            var card = Card(a.name, fitted ? "Fitted" : owned ? "Owned" : $"{a.price} scrap", a.blurb, fitted, null);
            var row = Actions(card);
            row.Add(UIKit.Button(!owned ? $"Buy  {a.price}" : fitted ? "Remove" : "Fit", () => Try(l.ToggleAccessory(a), a.name),
                !owned ? "btn-primary" : "btn-ghost"));
            return card;
        }

        VisualElement PaintCard(Loadout l)
        {
            var card = Card("Paint", Catalog.Paints[l.paint].name, "Free respray at base camp.", true, null);
            var sw = UIKit.Box("swatches");
            for (int i = 0; i < Catalog.Paints.Length; i++)
            {
                var p = Catalog.Paints[i];
                var s = UIKit.Box("swatch");
                s.style.backgroundColor = p.color.gamma;
                s.EnableInClassList("on", i == l.paint);
                s.tooltip = p.name;
                int idx = i;
                s.RegisterCallback<ClickEvent>(_ => l.SetPaint(idx));
                sw.Add(s);
            }
            card.Add(sw);
            return card;
        }

        VisualElement Note(string text)
        {
            var n = UIKit.Label(text, "body");
            n.style.whiteSpace = WhiteSpace.Normal;
            n.style.marginBottom = 12;
            return n;
        }

        // ------------------------------------------------------------------ stats

        static Loadout Clone(Loadout l) => JsonUtility.FromJson<Loadout>(JsonUtility.ToJson(l));

        static Stats Compute(Loadout l)
        {
            var body = Catalog.Body(l.body);
            var tire = Catalog.Tire(l.tire);
            float mass = body.mass;
            foreach (var a in Catalog.Accessories) if (l.Fitted(a.id)) mass += a.mass;
            float m = 1f + tire.GripPerLevel * l.TireLevel(tire.id);
            return new Stats
            {
                power = 165f * (mass / 1800f) * (1f + 0.12f * l.engineLevel),
                weight = mass,
                speed = (34f + 1.2f * l.engineLevel) * 3.6f / tire.rolling,
                grip = tire.grip * m,
            };
        }

        void UpdateStats(Loadout preview)
        {
            var cur = Compute(Loadout.Current);
            var pre = preview != null ? Compute(preview) : cur;
            _power.Set(cur.power / 300f, $"{cur.power:0} kW", pre.power / 300f);
            _weight.Set(cur.weight / 2600f, $"{cur.weight:0} kg", pre.weight / 2600f);
            _speed.Set(cur.speed / 160f, $"{cur.speed:0} km/h", pre.speed / 160f);
            _sand.Set(cur.grip.x / 1.4f, $"{cur.grip.x:0.00}x", pre.grip.x / 1.4f);
            _gravel.Set(cur.grip.y / 1.4f, $"{cur.grip.y:0.00}x", pre.grip.y / 1.4f);
            _rock.Set(cur.grip.w / 1.4f, $"{cur.grip.w:0.00}x", pre.grip.w / 1.4f);
        }
    }
}
