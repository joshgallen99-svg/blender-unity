using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

/// <summary>Called by CI (GameCI buildMethod) to produce a WebGL build.</summary>
public static class BuildScript
{
    const string BootScenePath = "Assets/Scenes/Main.unity";

    public static void BuildWebGL()
    {
        EnsureScene();

        // Uncompressed output so any plain static file server can host it for playtesting.
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;

        var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        var outDir = System.Environment.GetEnvironmentVariable("BUILD_PATH") ?? "build/WebGL";

        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = outDir,
            target = BuildTarget.WebGL,
            options = BuildOptions.None,
        });

        if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            EditorApplication.Exit(1);
    }

    /// <summary>Creates an empty Main scene if the project has none, and registers it.</summary>
    static void EnsureScene()
    {
        if (EditorBuildSettings.scenes.Any(s => s.enabled && File.Exists(s.path))) return;

        if (!File.Exists(BootScenePath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(BootScenePath));
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            EditorSceneManager.SaveScene(scene, BootScenePath);
        }
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(BootScenePath, true) };
    }
}
