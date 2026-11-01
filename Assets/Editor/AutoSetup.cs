using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace Offroad.EditorTools
{
    /// <summary>First time the project is opened in the editor, generate and open the prototype scene.</summary>
    [InitializeOnLoad]
    static class AutoSetup
    {
        static AutoSetup()
        {
            if (UnityEngine.Application.isBatchMode || File.Exists(PrototypeSceneBuilder.ScenePath)) return;
            EditorApplication.delayCall += () =>
            {
                if (File.Exists(PrototypeSceneBuilder.ScenePath)) return;
                PrototypeSceneBuilder.Build();
                EditorSceneManager.OpenScene(PrototypeSceneBuilder.ScenePath);
            };
        }
    }
}
