using UnityEngine;

namespace Offroad.World
{
    /// <summary>Watches the player's vehicle and discovers landmarks it gets close to.</summary>
    public class DiscoveryTracker : MonoBehaviour
    {
        public Transform player;
        float _timer;

        void Update()
        {
            if (!player) return;
            _timer -= Time.deltaTime;
            if (_timer > 0f) return;
            _timer = 0.25f;
            Vector3 p = player.position;
            foreach (var l in Landmark.All)
            {
                if (l.Discovered) continue;
                Vector3 d = l.transform.position - p;
                d.y = 0f;
                if (d.sqrMagnitude <= l.discoverRadius * l.discoverRadius) Progress.Discover(l);
            }
        }
    }
}
