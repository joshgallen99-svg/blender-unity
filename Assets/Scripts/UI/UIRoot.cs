using Offroad.Game;
using Offroad.Vehicles;
using Offroad.World;
using UnityEngine;
using UnityEngine.UIElements;

namespace Offroad.UI
{
    /// <summary>Owns the UI Toolkit document and switches between screens.</summary>
    [RequireComponent(typeof(UIDocument))]
    public class UIRoot : MonoBehaviour
    {
        public StyleSheet style;
        public Font body, bodyBold, head, headSemi;
        public GameFlow flow;
        public MissionRunner runner;
        public OffroadVehicle vehicle;

        VisualElement _root;
        TitleView _title;
        MissionsView _missions;
        GarageView _garage;
        HudView _hud;
        PauseView _pause;
        ResultsView _results;
        Toasts _toasts;

        public Toasts Toasts => _toasts;
        public MissionDef SelectedMission => _missions?.Selected;

        void OnEnable()
        {
            EnsureBuilt();
            Progress.Discovered += OnDiscovered;
            if (runner)
            {
                runner.Notice += OnNotice;
                runner.ObjectiveChanged += OnObjective;
            }
        }

        void OnDisable()
        {
            Progress.Discovered -= OnDiscovered;
            if (runner)
            {
                runner.Notice -= OnNotice;
                runner.ObjectiveChanged -= OnObjective;
            }
        }

        bool EnsureBuilt()
        {
            if (_root != null) return true;
            var doc = GetComponent<UIDocument>();
            if (doc == null || doc.rootVisualElement == null) return false;
            UIKit.Body = body;
            UIKit.BodyBold = bodyBold;
            UIKit.Head = head;
            UIKit.HeadSemi = headSemi;

            _root = new VisualElement { name = "ui" };
            _root.AddToClassList("ui-root");
            _root.style.position = Position.Absolute;
            _root.style.left = _root.style.top = _root.style.right = _root.style.bottom = 0;
            _root.pickingMode = PickingMode.Ignore;
            if (style) _root.styleSheets.Add(style);
            if (body) _root.style.unityFontDefinition = new StyleFontDefinition(body);
            doc.rootVisualElement.Add(_root);

            _hud = new HudView(this);
            _title = new TitleView(this);
            _missions = new MissionsView(this);
            _garage = new GarageView(this);
            _results = new ResultsView(this);
            _pause = new PauseView(this);
            _toasts = new Toasts();
            foreach (var v in new VisualElement[] { _hud.Root, _title.Root, _missions.Root, _garage.Root, _results.Root, _pause.Root })
            {
                _root.Add(v);
                UIKit.HideNow(v);
            }
            _root.Add(_toasts.Root);
            return true;
        }

        void HideScreens(VisualElement keep)
        {
            foreach (var v in new[] { _hud.Root, _title.Root, _missions.Root, _garage.Root, _results.Root, _pause.Root })
                if (v != keep && v.resolvedStyle.display != DisplayStyle.None) UIKit.Hide(v);
        }

        public void ShowTitle()
        {
            if (!EnsureBuilt()) return;
            HideScreens(_title.Root);
            _title.Show();
        }

        public void ShowMissions()
        {
            if (!EnsureBuilt()) return;
            HideScreens(_missions.Root);
            _missions.Show();
        }

        public void ShowGarage()
        {
            if (!EnsureBuilt()) return;
            HideScreens(_garage.Root);
            _garage.Show();
        }

        public void ShowHud(MissionDef m)
        {
            if (!EnsureBuilt()) return;
            HideScreens(_hud.Root);
            _hud.Show(m);
        }

        public void ShowPause()
        {
            if (!EnsureBuilt()) return;
            _pause.Show(fromTitle: false);
        }

        public void ShowSettingsFromTitle()
        {
            if (!EnsureBuilt()) return;
            _pause.Show(fromTitle: true);
        }

        public void HidePause() => _pause?.Hide();

        public void MoveMissionSelection(int delta) => _missions?.Move(delta);

        /// <summary>Photo mode hides the HUD and toasts.</summary>
        public void SetHudVisible(bool visible)
        {
            if (!EnsureBuilt()) return;
            _hud.Root.style.visibility = visible ? Visibility.Visible : Visibility.Hidden;
            _toasts.Root.style.visibility = visible ? Visibility.Visible : Visibility.Hidden;
        }

        /// <summary>Full-screen "travelling to ..." card while the next region's scene loads.</summary>
        public void ShowLoading(string regionTitle)
        {
            if (!EnsureBuilt()) return;
            HideScreens(null);
            var card = UIKit.Box("loading");
            card.Add(UIKit.SubHeading("Travelling to", "kicker"));
            card.Add(UIKit.Heading(regionTitle, "h1"));
            _root.Add(card);
            UIKit.Show(card);
        }

        public void ShowResults(MissionDef m)
        {
            if (!EnsureBuilt()) return;
            HideScreens(_results.Root);
            _results.Show(m);
        }

        void OnDiscovered(Landmark l)
        {
            if (l.reward <= 0) return;
            _toasts?.Push("Landmark discovered", l.displayName, $"+{l.reward} scrap");
        }

        void OnNotice(string text) => _toasts?.Push("", text, "", 2200, small: true);

        void OnObjective(string text)
        {
            if (flow && flow.State == FlowState.Driving && runner && runner.Step > 0)
                _toasts?.Push("New objective", text, "", 3200);
        }

        void Update()
        {
            if (_root == null) EnsureBuilt();
            _hud?.Tick();
            _title?.Tick();
        }
    }

    /// <summary>Stack of animated notifications at the top of the screen.</summary>
    public class Toasts
    {
        public readonly VisualElement Root;

        public Toasts()
        {
            Root = UIKit.Box("toasts");
            Root.pickingMode = PickingMode.Ignore;
        }

        public void Push(string kicker, string title, string sub, long durationMs = 3800, bool small = false)
        {
            var t = UIKit.Box("toast", "drop");
            t.pickingMode = PickingMode.Ignore;
            if (!string.IsNullOrEmpty(kicker)) t.Add(UIKit.SubHeading(kicker, "toast-kicker"));
            var title_ = small ? UIKit.Label(title, "toast-sub") : UIKit.Heading(title, "toast-title");
            t.Add(title_);
            if (!string.IsNullOrEmpty(sub)) t.Add(UIKit.Label(sub, "toast-sub", "accent"));
            Root.Add(t);
            UIKit.Show(t);
            t.schedule.Execute(() =>
            {
                UIKit.Hide(t);
                t.schedule.Execute(() => t.RemoveFromHierarchy()).StartingIn(400);
            }).StartingIn(durationMs);
            while (Root.childCount > 3) Root.RemoveAt(0);
        }
    }
}
