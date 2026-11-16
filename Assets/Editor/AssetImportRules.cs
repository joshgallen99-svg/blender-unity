using UnityEditor;
using UnityEngine;

namespace Offroad.EditorTools
{
    /// <summary>Import settings for generated models and textures, so nothing needs hand-tuning.</summary>
    public class AssetImportRules : AssetPostprocessor
    {
        public override uint GetVersion() => 7;

        void OnPreprocessModel()
        {
            if (!assetPath.StartsWith("Assets/Models/")) return;
            var mi = (ModelImporter)assetImporter;
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.bakeAxisConversion = true;
            mi.importCameras = false;
            mi.importLights = false;
            mi.importAnimation = false;
            mi.animationType = ModelImporterAnimationType.None;
            mi.importBlendShapes = false;
            mi.meshCompression = ModelImporterMeshCompression.Off;
            mi.isReadable = true;
            mi.importNormals = ModelImporterNormals.Import;
            mi.addCollider = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
        }

        /// <summary>
        /// Rock shaders read baked occlusion / cavity / edge data from vertex colours (white = no effect).
        /// Meshes without colours get white, so every shader sees a defined value on every GPU.
        /// </summary>
        void OnPostprocessModel(GameObject root)
        {
            if (!assetPath.StartsWith("Assets/Models/")) return;
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mesh = mf.sharedMesh;
                if (mesh == null || mesh.colors32.Length == mesh.vertexCount) continue;
                var white = new Color32[mesh.vertexCount];
                for (int i = 0; i < white.Length; i++) white[i] = new Color32(255, 255, 255, 255);
                mesh.colors32 = white;
            }
        }

        void OnPreprocessTexture()
        {
            var ti = (TextureImporter)assetImporter;
            if (assetPath.StartsWith("Assets/Terrain/Masks/"))
            {
                ti.textureType = TextureImporterType.Default;
                ti.sRGBTexture = false;
                ti.mipmapEnabled = true;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.maxTextureSize = 1024;
                ti.textureCompression = TextureImporterCompression.Uncompressed;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.isReadable = assetPath.Contains("_hazard");   // vehicle physics samples it on the CPU
            }
            else if (assetPath.StartsWith("Assets/Terrain/Textures/"))
            {
                bool normal = assetPath.Contains("_normal");
                bool data = assetPath.Contains("Macro");
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !normal && !data;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.alphaIsTransparency = false;
                ti.mipmapEnabled = true;
                ti.anisoLevel = 4;
                ti.wrapMode = TextureWrapMode.Repeat;
                ti.maxTextureSize = 1024;
                ti.textureCompression = TextureImporterCompression.Compressed;
            }
            else if (assetPath.StartsWith("Assets/Art/Textures/Scans/"))
            {
                // Poly Haven scan maps: albedo (sRGB), OpenGL-convention normals.
                bool normal = assetPath.Contains("_nor");
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !normal && !assetPath.Contains("_arm");
                ti.mipmapEnabled = true;
                ti.anisoLevel = 2;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.maxTextureSize = 1024;
                ti.textureCompression = TextureImporterCompression.Compressed;
            }
            else if (assetPath.StartsWith("Assets/Art/Textures/Materials/"))
            {
                bool normal = assetPath.Contains("_normal");
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !normal;
                ti.mipmapEnabled = true;
                ti.anisoLevel = 4;
                ti.wrapMode = TextureWrapMode.Repeat;
                ti.maxTextureSize = 512;
            }
            else if (assetPath.StartsWith("Assets/Art/Textures/"))
            {
                ti.textureType = TextureImporterType.Default;
                ti.alphaIsTransparency = true;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.mipmapEnabled = true;
            }
        }
    }
}
