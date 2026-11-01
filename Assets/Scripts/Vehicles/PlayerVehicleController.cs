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

        /// <summary>Set by game flow (menus, garage, wheel swap) to stop the player driving.</summary>
        public static bool InputBlocked;

        void Awake() => _vehicle = GetComponent<OffroadVehicle>();

        void Update()
        {
            GameInput.Poll();
            if (Time.timeScale <= 0f) return;
            if (InputBlocked)
            {
                _vehicle.controls = new VehicleControls { handbrake = true };
                return;
            }
            _vehicle.controls = new VehicleControls
            {
                throttle = GameInput.Throttle,
                brake = GameInput.Brake,
                steer = GameInput.Steer,
                handbrake = GameInput.Handbrake,
            };
            if (GameInput.ResetPressed) _vehicle.ResetUpright();
        }
    }
}
