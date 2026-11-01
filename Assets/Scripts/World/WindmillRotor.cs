using UnityEngine;

namespace Offroad.World
{
    /// <summary>Spins a windmill rotor about its forward axis, with gusty speed changes.</summary>
    public class WindmillRotor : MonoBehaviour
    {
        public float baseSpeed = 70f;    // degrees per second
        public float gust = 0.45f;
        float _seed;

        void Start() => _seed = UnityEngine.Random.value * 100f;

        void Update()
        {
            float t = Time.time * 0.15f + _seed;
            float speed = baseSpeed * (1f + gust * (Mathf.PerlinNoise(t, 0.3f) - 0.5f) * 2f);
            transform.Rotate(0f, 0f, speed * Time.deltaTime, Space.Self);
        }
    }
}
