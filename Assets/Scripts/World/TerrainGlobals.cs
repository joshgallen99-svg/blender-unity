using UnityEngine;

namespace Offroad.World
{
    /// <summary>
    /// Publishes the terrain's heightmap and the sandstone strata settings as global shader values,
    /// so rocks can blend into the sand where they meet the ground and share the terrain's bands.
    /// </summary>
    [ExecuteAlways]
    public class TerrainGlobals : MonoBehaviour
    {
        public Terrain terrain;
        public Texture2D heightTexture;     // normalised 0..1 heights (RHalf), covering the terrain rect
        [Tooltip("Sandstone bands per metre of height.")]
        public float strataFrequency = 0.33f;
        [Tooltip("How strongly bands bend (cross-bedding).")]
        public float strataWarp = 1.6f;

        static readonly int HeightTex = Shader.PropertyToID("_OffroadTerrainHeight");
        static readonly int Rect = Shader.PropertyToID("_OffroadTerrainRect");
        static readonly int HeightParams = Shader.PropertyToID("_OffroadTerrainHeightParams");
        static readonly int StrataFreq = Shader.PropertyToID("_OffroadStrataFreq");
        static readonly int StrataWarp = Shader.PropertyToID("_OffroadStrataWarp");

        void OnEnable() => Publish();
        void OnValidate() => Publish();

        public void Publish()
        {
            if (!terrain) terrain = GetComponent<Terrain>();
            Shader.SetGlobalFloat(StrataFreq, strataFrequency);
            Shader.SetGlobalFloat(StrataWarp, strataWarp);
            if (!terrain || terrain.terrainData == null || !heightTexture)
            {
                Shader.SetGlobalVector(HeightParams, Vector4.zero);
                return;
            }
            var size = terrain.terrainData.size;
            var pos = terrain.transform.position;
            Shader.SetGlobalTexture(HeightTex, heightTexture);
            Shader.SetGlobalVector(Rect, new Vector4(pos.x, pos.z, size.x, size.z));
            Shader.SetGlobalVector(HeightParams, new Vector4(size.y, pos.y, 1f, 0f));
        }
    }
}
