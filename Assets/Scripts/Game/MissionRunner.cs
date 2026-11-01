using System;
using System.Collections.Generic;
using Offroad.Core;
using Offroad.Garage;
using Offroad.Vehicles;
using Offroad.World;
using UnityEngine;

namespace Offroad.Game
{
    /// <summary>Runs the active expedition: objectives, completion, rewards and the one-time spare swap.</summary>
    public class MissionRunner : MonoBehaviour
    {
        public OffroadVehicle vehicle;
        public float arriveRadius = 22f;

        public MissionDef Active { get; private set; }
        public int Step { get; private set; }
        public bool SpareUsed { get; private set; }
        public bool Swapping { get; private set; }
        public bool Running => Active != null && !Complete;
        public bool Complete { get; private set; }
        public float Elapsed { get; private set; }
        public float Distance { get; private set; }
        public int LastReward { get; private set; }

        public event Action<MissionDef> Started;
        public event Action<MissionDef> Completed;
        public event Action<string> ObjectiveChanged;
        public event Action<string> Notice;
        public event Action SpareSwapped;

        VehicleAssembler _assembler;
        Vector3 _lastPos;
        float _swapTimer;
        Transform _bodyVisual;
        Vector3 _bodyRest;

        void Awake() => _assembler = vehicle ? vehicle.GetComponent<VehicleAssembler>() : null;

        public void Begin(MissionDef m)
        {
            Active = m;
            Step = 0;
            Complete = false;
            SpareUsed = false;
            Elapsed = Distance = 0f;
            _lastPos = vehicle ? vehicle.transform.position : Vector3.zero;
            Started?.Invoke(m);
            ObjectiveChanged?.Invoke(ObjectiveText);
        }

        public void Abandon()
        {
            Active = null;
            Complete = false;
        }

        public string ObjectiveText
        {
            get
            {
                if (Active == null) return "";
                if (Active.freeRoam) return $"Explore: {Progress.DiscoveredCount}/{Landmark.All.Count} landmarks found";
                if (Complete) return "Expedition complete";
                if (Step < Active.targets.Length)
                {
                    var l = FindLandmark(Active.targets[Step]);
                    return l ? $"Reach {l.displayName}" : "Reach the objective";
                }
                var camp = FindLandmark(Active.camp);
                return camp ? $"Return to {camp.displayName}" : "Return to camp";
            }
        }

        /// <summary>World position of the current objective (for the compass), or null.</summary>
        public Vector3? Target
        {
            get
            {
                if (!Running || Active.freeRoam) return null;
                string id = Step < Active.targets.Length ? Active.targets[Step] : Active.camp;
                var l = FindLandmark(id);
                return l ? l.transform.position : (Vector3?)null;
            }
        }

        static Landmark FindLandmark(string id) => Landmark.All.Find(l => l.id == id);

        void Update()
        {
            UpdateSwap();
            if (!Running || !vehicle) return;
            Elapsed += Time.deltaTime;
            Vector3 p = vehicle.transform.position;
            float step = Vector3.Distance(p, _lastPos);
            if (step < 20f) Distance += step;
            _lastPos = p;

            GameInput.Poll();
            if (GameInput.SwapSparePressed) TrySwapSpare();

            if (Active.freeRoam) return;
            var target = Target;
            if (target == null) return;
            Vector3 d = target.Value - vehicle.transform.position;
            d.y = 0f;
            string id = Step < Active.targets.Length ? Active.targets[Step] : Active.camp;
            var lm = FindLandmark(id);
            float radius = lm ? Mathf.Max(arriveRadius, lm.discoverRadius * 0.6f) : arriveRadius;
            if (d.magnitude > radius) return;

            Step++;
            bool done = Step > Active.targets.Length || (Step == Active.targets.Length && !Active.returnToCamp);
            if (done)
            {
                Complete = true;
                // Full reward the first time, a smaller one for repeat runs.
                LastReward = Progress.IsMissionDone(Active.id) ? Mathf.RoundToInt(Active.reward * 0.4f) : Active.reward;
                Progress.Add(LastReward);
                Progress.MarkMissionDone(Active.id);
                Completed?.Invoke(Active);
            }
            else ObjectiveChanged?.Invoke(ObjectiveText);
        }

        // ------------------------------------------------------------------ spare wheel

        public bool CanSwapSpare(out string reason)
        {
            reason = null;
            if (!_assembler) { reason = "No spare fitted"; return false; }
            if (SpareUsed) { reason = "Spare already used this expedition"; return false; }
            if (_assembler.ActiveSpare == _assembler.ActiveTire) { reason = "Spare matches the fitted tyres"; return false; }
            if (Mathf.Abs(vehicle.ForwardSpeed) > 1.5f) { reason = "Stop to change wheels"; return false; }
            return true;
        }

        public void TrySwapSpare()
        {
            if (Swapping) return;
            if (!CanSwapSpare(out var reason)) { Notice?.Invoke(reason); return; }
            Swapping = true;
            _swapTimer = 0f;
            _bodyVisual = vehicle.transform.Find("Body");
            if (_bodyVisual) _bodyRest = _bodyVisual.localPosition;
            vehicle.controls = default;
        }

        const float SwapDuration = 2.4f;

        void UpdateSwap()
        {
            if (!Swapping) return;
            float prev = _swapTimer;
            _swapTimer += Time.deltaTime;
            float t = _swapTimer / SwapDuration;
            // Jack the body up, swap at the top, lower it again.
            float lift = Mathf.Sin(Mathf.Clamp01(t) * Mathf.PI) * 0.22f;
            if (_bodyVisual) _bodyVisual.localPosition = _bodyRest + Vector3.up * lift;
            if (prev < SwapDuration * 0.5f && _swapTimer >= SwapDuration * 0.5f)
            {
                _assembler.SwapToSpare();
                Notice?.Invoke($"Fitted {Catalog.Tire(_assembler.ActiveTire).name}");
            }
            if (t >= 1f)
            {
                if (_bodyVisual) _bodyVisual.localPosition = _bodyRest;
                Swapping = false;
                SpareUsed = true;
                SpareSwapped?.Invoke();
            }
        }

        public float SwapProgress => Swapping ? Mathf.Clamp01(_swapTimer / SwapDuration) : 0f;
    }
}
