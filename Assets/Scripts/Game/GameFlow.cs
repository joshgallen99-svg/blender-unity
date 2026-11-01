using Offroad.CameraRig;
using Offroad.Core;
using Offroad.Garage;
using Offroad.Settings;
using Offroad.UI;
using Offroad.Vehicles;
using UnityEngine;

namespace Offroad.Game
{
    public enum FlowState { Title, Missions, Garage, Driving, Paused, Results }

    /// <summary>Top-level game states: title, expedition select, garage, driving, pause, results.</summary>
    [DefaultExecutionOrder(-100)]
    public class GameFlow : MonoBehaviour
    {
        public OffroadVehicle vehicle;
        public ChaseCamera cam;
        public MissionRunner runner;
        public UIRoot ui;
        [Tooltip("Which region this scene is (see Regions).")]
        public string regionId = Regions.Desert;

        /// <summary>Mission to start as soon as the next region's scene has loaded.</summary>
        static string _pendingMission;

        public FlowState State { get; private set; } = FlowState.Title;
        public static GameFlow Instance { get; private set; }
        public VehicleAssembler Assembler { get; private set; }

        Vector3 _spawnPos;
        Quaternion _spawnRot;

        void Awake()
        {
            Instance = this;
            Assembler = vehicle ? vehicle.GetComponent<VehicleAssembler>() : null;
            _spawnPos = vehicle.transform.position;
            _spawnRot = vehicle.transform.rotation;
        }

        void Start()
        {
            GameSettings.Apply();
            ApplyLoadout();
            Loadout.Changed += OnLoadoutChanged;
            if (runner) runner.Completed += OnMissionCompleted;
            var pending = _pendingMission != null ? Missions.Find(_pendingMission) : null;
            _pendingMission = null;
            if (pending != null && pending.region == regionId) StartMission(pending);
            else GoTitle();
        }

        void OnDestroy()
        {
            Loadout.Changed -= OnLoadoutChanged;
            if (Instance == this) Instance = null;
        }

        void OnLoadoutChanged(Loadout l)
        {
            if (State == FlowState.Garage || State == FlowState.Title || State == FlowState.Missions) ApplyLoadout();
        }

        void ApplyLoadout()
        {
            if (!Assembler) return;
            Assembler.Apply(Loadout.Current);
            if (cam)
            {
                cam.distance = Assembler.CameraDistance;
                cam.distanceAtSpeed = Assembler.CameraDistance + 1.4f;
            }
        }

        // ------------------------------------------------------------------ transitions

        public void GoTitle()
        {
            State = FlowState.Title;
            Time.timeScale = 1f;
            runner?.Abandon();
            ResetVehicle();
            cam?.SetShowcase(true, 0.22f, 8.5f);
            ui?.ShowTitle();
            SetCursor(false);
        }

        public void GoMissions()
        {
            State = FlowState.Missions;
            cam?.SetShowcase(true, 0.12f, 8.5f);
            ui?.ShowMissions();
        }

        public void GoGarage()
        {
            State = FlowState.Garage;
            ResetVehicle();
            cam?.SetShowcase(true, 0.3f, 7.6f);
            ui?.ShowGarage();
        }

        public void StartMission(MissionDef m)
        {
            if (m.region != regionId)
            {
                // Another region: load its scene, then start the mission there.
                _pendingMission = m.id;
                Time.timeScale = 1f;
                ui?.ShowLoading(Regions.Title(m.region));
                UnityEngine.SceneManagement.SceneManager.LoadSceneAsync(Regions.Scene(m.region));
                return;
            }
            ApplyLoadout();
            ResetVehicle();
            State = FlowState.Driving;
            Time.timeScale = 1f;
            runner?.Begin(m);
            cam?.SetShowcase(false, 0f, 0f);
            cam?.SnapBehindTarget();
            ui?.ShowHud(m);
            SetCursor(true);
        }

        public void ContinueExploring()
        {
            State = FlowState.Driving;
            runner?.Begin(Missions.FreeRoam(regionId));
            ui?.ShowHud(runner?.Active);
            SetCursor(true);
        }

        public void Pause()
        {
            if (State != FlowState.Driving) return;
            State = FlowState.Paused;
            Time.timeScale = 0f;
            AudioListener.pause = true;
            ui?.ShowPause();
            SetCursor(false);
        }

        public void Resume()
        {
            if (State != FlowState.Paused) return;
            State = FlowState.Driving;
            Time.timeScale = 1f;
            AudioListener.pause = false;
            ui?.HidePause();
            SetCursor(true);
        }

        public void AbandonMission()
        {
            AudioListener.pause = false;
            GoTitle();
        }

        public void ResetVehicleUpright()
        {
            vehicle.ResetUpright();
            Resume();
        }

        public void Quit()
        {
            Application.Quit();
        }

        void OnMissionCompleted(MissionDef m)
        {
            if (m.freeRoam) return;
            State = FlowState.Results;
            ui?.ShowResults(m);
            SetCursor(false);
        }

        int _tourIndex;
        bool _photo;

        /// <summary>F2: photo mode. Hides the HUD, parks the vehicle and lets you orbit the camera.</summary>
        void TogglePhoto()
        {
            _photo = !_photo;
            PlayerVehicleController.InputBlocked = _photo;
            if (cam)
            {
                cam.ManualOrbit = _photo;
                cam.SetShowcase(_photo, 0f, 11f);
                if (_photo) cam.BeginPhotoOrbit();
                else { cam.EndPhotoOrbit(); cam.SnapBehindTarget(); }
            }
            ui?.SetHudVisible(!_photo);
        }

        /// <summary>F9: jump to the next landmark (handy for screenshots and getting your bearings).</summary>
        void TourNextLandmark()
        {
            var list = World.Landmark.All;
            if (list.Count == 0 || !vehicle) return;
            var l = list[_tourIndex++ % list.Count];
            Vector3 c = l.transform.position;
            Vector3 from = (vehicle.transform.position - c);
            from.y = 0f;
            if (from.sqrMagnitude < 1f) from = Vector3.back;
            // Try spots around the landmark until one lands on open, fairly flat ground (not on a rock).
            Vector3 dir = from.normalized;
            float dist = Mathf.Max(28f, l.discoverRadius * 0.9f);
            Vector3 p = c + dir * dist + Vector3.up * 1.2f;
            for (int k = 0; k < 16; k++)
            {
                Vector3 q = c + Quaternion.Euler(0f, k * 23f, 0f) * dir * (dist + (k / 4) * 6f) + Vector3.up * 60f;
                if (!Physics.Raycast(q, Vector3.down, out var hit, 250f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    continue;
                bool ground = hit.collider is TerrainCollider && hit.normal.y > 0.85f;
                bool clear = !Physics.CheckBox(hit.point + Vector3.up * 1.4f, new Vector3(1.6f, 1.0f, 2.8f),
                    Quaternion.identity, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
                if (ground && clear) { p = hit.point + Vector3.up * 1.2f; break; }
                if (k == 0) p = hit.point + Vector3.up * 1.2f;
            }
            Vector3 look = c - p;
            look.y = 0f;
            vehicle.Teleport(p, Quaternion.LookRotation(look.normalized, Vector3.up));
            cam?.SnapBehindTarget();
        }

        void ResetVehicle()
        {
            if (vehicle) vehicle.Teleport(_spawnPos, _spawnRot);
        }

        static void SetCursor(bool locked)
        {
            if (Application.isEditor && !Application.isFocused) return;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }

        void Update()
        {
            GameInput.Poll();
            GameSettings.CheckResolution();
            if (GameInput.MenuPressed)
            {
                switch (State)
                {
                    case FlowState.Driving: Pause(); break;
                    case FlowState.Paused: Resume(); break;
                    case FlowState.Garage:
                    case FlowState.Missions: GoTitle(); break;
                }
            }
            if (State == FlowState.Missions && GameInput.NavVertical != 0) ui?.MoveMissionSelection(GameInput.NavVertical);
            if (GameInput.PhotoPressed && (State == FlowState.Driving || _photo)) TogglePhoto();
            if (_photo && cam)
            {
                // A/D orbit, W/S tilt, Q/E zoom (real time, works while the world is frozen).
                float dt = Time.unscaledDeltaTime;
                cam.NudgeOrbit(GameInput.Steer * 70f * dt, (GameInput.Throttle - GameInput.Brake) * 35f * dt, GameInput.Zoom * 8f * dt);
            }
            if (GameInput.ConfirmPressed)
            {
                if (State == FlowState.Title) GoMissions();
                else if (State == FlowState.Missions && ui && ui.SelectedMission != null) StartMission(ui.SelectedMission);
                else if (State == FlowState.Results) GoTitle();
            }
            if (GameInput.GaragePressed && (State == FlowState.Title || State == FlowState.Missions)) GoGarage();
            if (GameInput.FpsTogglePressed) GameSettings.Modify(s => s.showFps = !s.showFps);
            if (GameInput.TourPressed && State == FlowState.Driving) TourNextLandmark();
            PlayerVehicleController.InputBlocked = State != FlowState.Driving || (runner && runner.Swapping);
            if (cam) cam.InputEnabled = State == FlowState.Driving;
            if (State == FlowState.Driving && Cursor.lockState != CursorLockMode.Locked && GameInput.AnyPressed) SetCursor(true);
        }
    }
}
