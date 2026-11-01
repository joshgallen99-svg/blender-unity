using UnityEngine;

namespace Game
{
    /// <summary>
    /// Placeholder scene content so the pipeline has something to build and screenshot.
    /// Spawns a camera, light, ground and a spinning cube if the scene has no camera.
    /// Remove once real scenes exist.
    /// </summary>
    public static class Bootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
            if (Object.FindAnyObjectByType<Camera>() != null) return;

            var cam = new GameObject("Main Camera").AddComponent<Camera>();
            cam.tag = "MainCamera";
            cam.transform.SetPositionAndRotation(new Vector3(0, 3, -6), Quaternion.Euler(20, 0, 0));
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.45f, 0.65f, 0.9f);

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";

            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = "Spinner";
            cube.transform.position = new Vector3(0, 1, 0);
            cube.AddComponent<Spinner>();
        }
    }

    public class Spinner : MonoBehaviour
    {
        public float degreesPerSecond = 90f;
        void Update() => transform.Rotate(0, degreesPerSecond * Time.deltaTime, 0);
    }
}
