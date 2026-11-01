using System.Linq;
using Offroad.EditorTools;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>Build entry points for CI (GameCI buildMethod) and the Offroad menu.</summary>
public static class BuildScript
{
    public static void BuildWebGL()
    {
        PrepareProject();
        // Uncompressed output so any plain static file server can host it for playtesting.
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.dataCaching = false;
        Build(BuildTarget.WebGL, System.Environment.GetEnvironmentVariable("BUILD_PATH") ?? "build/WebGL/WebGL");
    }

    public static void BuildMac()
    {
        PrepareProject();
        Build(BuildTarget.StandaloneOSX, System.Environment.GetEnvironmentVariable("BUILD_PATH") ?? "build/StandaloneOSX/Offroad.app");
    }

    static void PrepareProject()
    {
        PrototypeSceneBuilder.Build();
    }

    static void Build(BuildTarget target, string path)
    {
        var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = path,
            target = target,
            options = BuildOptions.None,
        });
        Debug.Log($"[Offroad] Build {target}: {report.summary.result}, {report.summary.totalSize / (1024 * 1024)} MB, " +
                  $"{report.summary.totalTime.TotalMinutes:0.0} min");
        if (report.summary.result != BuildResult.Succeeded)
            EditorApplication.Exit(1);
    }
}
