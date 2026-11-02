using Offroad.Core;
using UnityEngine;

namespace Offroad.Vehicles
{
    /// <summary>Feeds player input into an <see cref="OffroadVehicle"/>.</summary>
    [RequireComponent(typeof(OffroadVehicle))]
    [DefaultExecutionOrder(-80)]
    public class PlayerVehicleController : MonoBehaviour
    {
        OffroadVehicle _vehicle;
        Winch _winch;
        bool _winchWasDown, _winchJustHooked;
        float _winchDownAt;

        /// <summary>Set by game flow (menus, garage, wheel swap) to stop the player driving.</summary>
        public static bool InputBlocked;

        /// <summary>Scripted driving (automated playtests): replaces the player's pedals and steering while set.</summary>
        public static VehicleControls? Scripted;

        void Awake()
        {
            _vehicle = GetComponent<OffroadVehicle>();
            _winch = GetComponent<Winch>();
        }

        void Update()
        {
            GameInput.Poll();
            if (Time.timeScale <= 0f) return;
            if (InputBlocked)
            {
                if (_winch) _winch.SetReel(false);
                _vehicle.controls = new VehicleControls { handbrake = true };
                return;
            }
            if (Scripted.HasValue) { _vehicle.controls = Scripted.Value; return; }
            _vehicle.controls = new VehicleControls
            {
                throttle = GameInput.Throttle,
                brake = GameInput.Brake,
                steer = GameInput.Steer,
                handbrake = GameInput.Handbrake,
            };
            if (GameInput.ResetPressed && _vehicle.ResetUpright() && _winch) _winch.Release();
            UpdateWinch();
            if (GameInput.GearModePressed) _vehicle.SetManual(!_vehicle.manual);
            if (GameInput.Shift != 0) _vehicle.ShiftManual(GameInput.Shift);
        }
    
        /// <summary>Winch button: press to hook (and reel while held); a short tap while hooked releases.</summary>
        void UpdateWinch()
        {
            if (!_winch) return;
            bool down = GameInput.Winch;
            if (down && !_winchWasDown)
            {
                _winchDownAt = Time.unscaledTime;
                _winchJustHooked = !_winch.Attached && _winch.Attach();
            }
            else if (!down && _winchWasDown && _winch.Attached && !_winchJustHooked
                     && Time.unscaledTime - _winchDownAt < 0.25f)
                _winch.Release();
            _winch.SetReel(down && Time.unscaledTime - _winchDownAt > 0.2f);
            _winchWasDown = down;
        }
    }
}
