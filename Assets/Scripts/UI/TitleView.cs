using System;
using Offroad.Game;
using Offroad.Garage;
using Offroad.World;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>Title screen: animated logo, menu with sliding accent bars, progress chips.</summary>
    public class TitleView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly VisualElement _block, _menu, _footer;
        readonly Label _scrap, _found, _prompt;
        float _t;

        public TitleView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("screen");
            Root.pickingMode = PickingMode.Ignore;

            var shade = UIKit.Box("title-shade");
            shade.style.backgroundImage = UIKit.Gradient(new Color(0.03f, 0.03f, 0.035f, 0.88f), new Color(0, 0, 0, 0), true);
            shade.pickingMode = PickingMode.Ignore;
            Root.Add(shade);

            _block = UIKit.Box("title-block");
            _block.Add(UIKit.SubHeading("A canyon country expedition", "kicker", "slide-left"));
            _block.Add(UIKit.Heading("Offroad", "title-xl", "slide-left"));
            _block.Add(UIKit.SubHeading("Expedition", "title-sub", "slide-left"));
            Root.Add(_block);

            _menu = UIKit.Box("menu");
            AddItem("Expeditions", () => ui.flow.GoMissions());
            AddItem("Garage", () => ui.flow.GoGarage());
            AddItem("Settings", () => ui.ShowSettingsFromTitle());
            if (Application.platform != RuntimePlatform.WebGLPlayer) AddItem("Quit", () => ui.flow.Quit());
            Root.Add(_menu);

            _footer = UIKit.Box("title-footer");
            _scrap = Chip(_footer);
            _found = Chip(_footer);
            Root.Add(_footer);

            _prompt = UIKit.Label("Prototype build  ·  Esc to go back  ·  F1 shows FPS", "small");
            _prompt.style.position = Position.Absolute;
            _prompt.style.right = 60;
            _prompt.style.bottom = 64;
            Root.Add(_prompt);
        }

        static Label Chip(VisualElement parent)
        {
            var chip = UIKit.Box("chip");
            chip.Add(UIKit.Box("chip-dot"));
            var l = UIKit.Label("", "small");
            chip.Add(l);
            parent.Add(chip);
            return l;
        }

        void AddItem(string text, Action action)
        {
            var item = UIKit.Box("menu-item", "slide-left");
            item.Add(UIKit.Box("menu-bar"));
            item.Add(UIKit.Heading(text, "menu-label"));
            item.RegisterCallback<ClickEvent>(_ => action());
            _menu.Add(item);
        }

        public void Show()
        {
            _scrap.text = $"{UIKit.Money(Progress.Scrap)} scrap";
            _found.text = $"{Progress.DiscoveredCount}/{Mathf.Max(Landmark.All.Count - 1, 0)} landmarks found  ·  {Catalog.Body(Loadout.Current.body).name} on {Catalog.Tire(Loadout.Current.tire).name}";
            UIKit.Show(Root);
            UIKit.Stagger(_block, 110, 120);
            UIKit.Stagger(_menu, 70, 520);
            UIKit.Stagger(_footer, 80, 900);
            _t = 0f;
        }

        public void Tick()
        {
            if (Root.resolvedStyle.display == DisplayStyle.None) return;
            _t += Time.unscaledDeltaTime;
            _prompt.style.opacity = 0.55f + 0.25f * Mathf.Sin(_t * 1.6f);
        }
    }

    /// <summary>Expedition select: mission cards on the left, briefing and loadout on the right.</summary>
    public class MissionsView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly VisualElement _list, _brief;
        MissionDef _selected;
        public MissionDef Selected => _selected;

        public MissionsView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("screen");
            Root.pickingMode = PickingMode.Ignore;
            var shade = UIKit.Box("title-shade");
            shade.style.backgroundImage = UIKit.Gradient(new Color(0.03f, 0.03f, 0.035f, 0.9f), new Color(0, 0, 0, 0), true);
            shade.style.width = Length.Percent(70);
            shade.pickingMode = PickingMode.Ignore;
            Root.Add(shade);

            var left = UIKit.Box("missions");
            left.Add(UIKit.SubHeading("Choose your route", "kicker"));
            left.Add(UIKit.Heading("Expeditions", "h1"));
            _list = new ScrollView(ScrollViewMode.Vertical) { horizontalScrollerVisibility = ScrollerVisibility.Hidden };
            _list.style.flexGrow = 1;
            _list.style.marginTop = 14;
            left.Add(_list);
            Root.Add(left);

            _brief = UIKit.Box("brief", "panel", "slide-right");
            Root.Add(_brief);
        }

        public void Show()
        {
            _list.Clear();
            foreach (var m in Missions.All)
            {
                var card = UIKit.Box("mission-card", "slide-left");
                var col = UIKit.Box();
                col.style.flexGrow = 1;
                var top = UIKit.Box("row");
                top.Add(UIKit.Heading(m.title, "mission-title"));
                if (Progress.IsMissionDone(m.id))
                {
                    var done = UIKit.SubHeading("  Completed", "done-badge");
                    top.Add(done);
                }
                col.Add(top);
                var brief = UIKit.Label(m.brief, "small");
                brief.style.whiteSpace = WhiteSpace.Normal;
                col.Add(brief);
                card.Add(col);
                if (m.reward > 0) card.Add(UIKit.SubHeading($"{m.reward}", "mission-reward"));
                var mm = m;
                card.RegisterCallback<ClickEvent>(e =>
                {
                    Select(mm);
                    if (e.clickCount >= 2) _ui.flow.StartMission(mm);
                });
                card.userData = m;
                _list.Add(card);
            }
            UIKit.Show(Root);
            UIKit.Stagger(_list.contentContainer, 60, 100);
            Select(_selected ?? Array.Find(Missions.All, x => !Progress.IsMissionDone(x.id)) ?? Missions.All[0]);
        }

        void Select(MissionDef m)
        {
            _selected = m;
            foreach (var c in _list.contentContainer.Children())
                c.EnableInClassList("selected", c.userData == m);

            _brief.Clear();
            _brief.Add(UIKit.SubHeading(m.freeRoam ? "Free roam" : $"Reward  {m.reward} scrap", "kicker"));
            _brief.Add(UIKit.Heading(m.title, "h1"));
            _brief.Add(UIKit.Label(m.brief, "body"));
            _brief.Add(UIKit.Box("divider"));
            var tip = UIKit.Box("row");
            tip.Add(UIKit.SubHeading("Tip  ", "h3", "accent"));
            var tipText = UIKit.Label(m.tip, "body");
            tipText.style.flexShrink = 1;
            tip.Add(tipText);
            _brief.Add(tip);
            var l = Loadout.Current;
            _brief.Add(UIKit.Label($"Fitted: {Catalog.Tire(l.tire).name}   ·   Spare: {Catalog.Tire(l.spare).name}", "small"));
            _brief.Add(UIKit.Box("divider"));
            var buttons = UIKit.Box("row");
            buttons.Add(UIKit.Button("Back", () => _ui.flow.GoTitle(), "btn-ghost"));
            buttons.Add(UIKit.Button("Garage", () => _ui.flow.GoGarage(), "btn-ghost"));
            buttons.Add(UIKit.Box("spacer"));
            buttons.Add(UIKit.Button("Start expedition", () => _ui.flow.StartMission(m), "btn-primary"));
            _brief.Add(buttons);
            UIKit.Show(_brief);
            _brief.RemoveFromClassList("shown");
            _brief.schedule.Execute(() => _brief.AddToClassList("shown")).StartingIn(30);
        }
    }

    /// <summary>Mission complete card.</summary>
    public class ResultsView
    {
        public readonly VisualElement Root;
        readonly UIRoot _ui;
        readonly VisualElement _card;

        public ResultsView(UIRoot ui)
        {
            _ui = ui;
            Root = UIKit.Box("screen");
            var shade = UIKit.Box("pause-shade");
            Root.Add(shade);
            _card = UIKit.Box("result", "panel", "pop");
            Root.Add(_card);
        }

        public void Show(MissionDef m)
        {
            var r = _ui.runner;
            _card.Clear();
            _card.Add(UIKit.SubHeading("Expedition complete", "kicker"));
            _card.Add(UIKit.Heading(m.title, "h1"));
            _card.Add(UIKit.Heading($"+{r.LastReward} scrap", "h2", "accent"));
            var mins = Mathf.FloorToInt(r.Elapsed / 60f);
            var secs = Mathf.FloorToInt(r.Elapsed % 60f);
            _card.Add(UIKit.Label($"{mins}:{secs:00}  ·  {r.Distance / 1000f:0.0} km driven  ·  {(r.SpareUsed ? "spare used" : "spare unused")}", "body"));
            _card.Add(UIKit.Box("divider"));
            var row = UIKit.Box("row");
            row.Add(UIKit.Button("Keep exploring", () => _ui.flow.ContinueExploring(), "btn-ghost"));
            row.Add(UIKit.Button("Back to camp", () => _ui.flow.GoTitle(), "btn-primary"));
            _card.Add(row);
            UIKit.Show(Root);
            UIKit.Show(_card, 120);
        }
    }
}
