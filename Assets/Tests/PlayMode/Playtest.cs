using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using NUnit.Framework;
using Offroad.Game;
using Offroad.Vehicles;
using UnityEngine;
using UnityEngine.TestTools;

/// <summary>
/// Automated playtest (explicit: not run in CI). Loads each region, drives the player's vehicle into
/// every obstacle section with a simple line-following driver in low range, logs how it went, and saves
/// chase-camera screenshots to Playtest~/ at the repo root. Run:
///   Unity -batchmode -projectPath . -runTests -testPlatform PlayMode -testFilter Playtest -logFile -
/// Optional: OFFROAD_PLAYTEST_REGION=desert|forest|alpine, OFFROAD_PLAYTEST_LIMIT=n (sections per region).
/// </summary>
[Explicit, Category("Playtest")]
public class Playtest
{
    [Serializable] class Track { public string name; public float[] x, z; }
    [Serializable] class Challenge { public string track, kind; public int difficulty; public float x, z; }
    [Serializable] class Info { public Track[] tracks; public Challenge[] challenges; }

    static readonly (string id, string scene)[] Regions =
    {
        ("desert", "Assets/Scenes/Prototype.unity"), ("forest", "Assets/Scenes/Forest.unity"), ("alpine", "Assets/Scenes/Alpine.unity"),
    };

    static string OutDir => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Playtest~"));

    [UnityTest, Timeout(1800000)]
    public IEnumerator DriveObstacleSections()
    {
        Directory.CreateDirectory(OutDir);
        string only = Environment.GetEnvironmentVariable("OFFROAD_PLAYTEST_REGION");
        int limit = int.TryParse(Environment.GetEnvironmentVariable("OFFROAD_PLAYTEST_LIMIT"), out var l) ? l : 99;
        var report = new StringBuilder("region,track,kind,difficulty,progress_m,target_m,max_tip,min_grounded,flipped,stuck,seconds\n");
        foreach (var (id, scene) in Regions)
        {
            if (!string.IsNullOrEmpty(only) && only != id) continue;
            yield return UnityEditor.SceneManagement.EditorSceneManager.LoadSceneAsyncInPlayMode(scene,
                new UnityEngine.SceneManagement.LoadSceneParameters(UnityEngine.SceneManagement.LoadSceneMode.Single));
            yield return null;
            yield return null;
            var info = JsonUtility.FromJson<Info>(File.ReadAllText(Path.Combine(Application.dataPath, "Terrain", "Source~", id + "_info.json")));
            var flow = GameFlow.Instance;
            Assert.NotNull(flow, "GameFlow missing in " + scene);
            flow.ContinueExploring();
            var vehicle = flow.vehicle;
            var cam = Camera.main;
            yield return new WaitForSeconds(1f);
            Capture(cam, $"{id}_00_spawn");

            int n = 0;
            foreach (var c in info.challenges)
            {
                if (n++ >= limit) break;
                var track = Array.Find(info.tracks, t => t.name == c.track);
                if (track == null) continue;
                var pts = new List<Vector2>();
                for (int i = 0; i < track.x.Length; i++) pts.Add(new Vector2(track.x[i], track.z[i]));
                int k = Nearest(pts, new Vector2(c.x, c.z));
                int start = Mathf.Max(0, k - 3);                     // ~18 m before the section
                var p0 = pts[start];
                var dir = (pts[Mathf.Min(start + 1, pts.Count - 1)] - p0).normalized;
                vehicle.SetManual(true);
                vehicle.ShiftManual(-9);                              // 1st = low range
                vehicle.Teleport(Ground(new Vector3(p0.x, 0f, p0.y)), Quaternion.LookRotation(new Vector3(dir.x, 0f, dir.y)));
                yield return Settle();
                float target = 0f;
                for (int i = start; i < Mathf.Min(k + 9, pts.Count - 1); i++) target += Vector2.Distance(pts[i], pts[i + 1]);

                float t = 0f, maxTip = 0f, progress = 0f, lastProgress = 0f, lastMoveT = 0f;
                int minGrounded = 4;
                bool shot = false, flipped = false, stuck = false;
                Vector3 origin = vehicle.transform.position;
                while (t < 40f && progress < target)
                {
                    // Pure pursuit: steer at a point ~7 m ahead on the track.
                    var pos = new Vector2(vehicle.transform.position.x, vehicle.transform.position.z);
                    int near = Nearest(pts, pos);
                    var aim = pts[Mathf.Min(near + 1, pts.Count - 1)] + (pts[Mathf.Min(near + 2, pts.Count - 1)] - pts[Mathf.Min(near + 1, pts.Count - 1)]) * 0.2f;
                    Vector3 local = vehicle.transform.InverseTransformPoint(new Vector3(aim.x, vehicle.transform.position.y, aim.y));
                    float steer = Mathf.Clamp(Mathf.Atan2(local.x, Mathf.Max(local.z, 0.5f)) * 2f, -1f, 1f);
                    PlayerVehicleController.Scripted = new VehicleControls { throttle = 0.85f, steer = steer };
                    yield return new WaitForFixedUpdate();
                    t += Time.fixedDeltaTime;
                    progress = Mathf.Max(progress, ArcTo(pts, start, Nearest(pts, pos)));
                    if (progress > lastProgress + 0.5f) { lastProgress = progress; lastMoveT = t; }
                    maxTip = Mathf.Max(maxTip, vehicle.TipRisk);
                    minGrounded = Mathf.Min(minGrounded, vehicle.GroundedWheels);
                    if (!shot && progress > 18f) { shot = true; yield return null; Capture(cam, $"{id}_{n:00}_{c.track}_{c.kind}"); }
                    if (Vector3.Dot(vehicle.transform.up, Vector3.up) < 0.1f) { flipped = true; break; }
                    if (t - lastMoveT > 8f) { stuck = true; break; }
                }
                if (!shot) Capture(cam, $"{id}_{n:00}_{c.track}_{c.kind}_end");
                PlayerVehicleController.Scripted = null;
                report.AppendLine($"{id},{c.track},{c.kind},{c.difficulty},{progress:0.0},{target:0.0},{maxTip:0.00},{minGrounded},{flipped},{stuck},{t:0.0}");
                Debug.Log($"[Playtest] {id} {c.track} {c.kind} d{c.difficulty}: {progress:0}/{target:0} m in {t:0.0}s tip {maxTip:0.00} lifted {4 - minGrounded} {(flipped ? "FLIPPED" : stuck ? "STUCK" : "ok")}");
            }
        }
        PlayerVehicleController.Scripted = null;
        File.WriteAllText(Path.Combine(OutDir, "report.csv"), report.ToString());
        Debug.Log("[Playtest] report written to " + OutDir);
    }

    static IEnumerator Settle()
    {
        PlayerVehicleController.Scripted = new VehicleControls { brake = 0f };
        for (int i = 0; i < 60; i++) yield return new WaitForFixedUpdate();
    }

    static Vector3 Ground(Vector3 p)
    {
        if (Physics.Raycast(p + Vector3.up * 300f, Vector3.down, out var hit, 600f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            p.y = hit.point.y + 0.3f;
        return p;
    }

    static int Nearest(List<Vector2> pts, Vector2 p)
    {
        int best = 0;
        float bd = float.MaxValue;
        for (int i = 0; i < pts.Count; i++)
        {
            float d = (pts[i] - p).sqrMagnitude;
            if (d < bd) { bd = d; best = i; }
        }
        return best;
    }

    static float ArcTo(List<Vector2> pts, int a, int b)
    {
        float s = 0f;
        for (int i = a; i < b; i++) s += Vector2.Distance(pts[i], pts[i + 1]);
        return s;
    }

    /// <summary>Render the camera (and only the camera: the UI is drawn by the engine on top) to a PNG.</summary>
    static void Capture(Camera cam, string name)
    {
        if (cam == null) return;
        var rt = RenderTexture.GetTemporary(1600, 900, 24, RenderTextureFormat.ARGB32);
        var prev = cam.targetTexture;
        cam.targetTexture = rt;
        cam.Render();
        cam.targetTexture = prev;
        var active = RenderTexture.active;
        RenderTexture.active = rt;
        var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex.Apply();
        RenderTexture.active = active;
        RenderTexture.ReleaseTemporary(rt);
        File.WriteAllBytes(Path.Combine(OutDir, name + ".png"), tex.EncodeToPNG());
        UnityEngine.Object.Destroy(tex);
    }
}
