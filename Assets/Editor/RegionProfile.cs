using System;
using System.Collections.Generic;
using Offroad.World;
using UnityEngine;

namespace Offroad.EditorTools
{
    /// <summary>Scenery drawn with GPU instancing (see InstancedScatter).</summary>
    public struct InstancedSpec
    {
        public float distance;      // draw distance at Scenery Detail 1.0
        public bool shadows;
        public float align;         // 0 upright .. 1 fully aligned to the terrain normal
        public float lod;           // LOD1 distance (0 = no LOD1)
        public bool collider;       // also create a collider-only GameObject (mesh collider from LOD1)
        public float lod2;          // impostor distance (0 = none); uses <name>_LOD2 with its own materials
        public float trunkRadius, trunkHeight;   // runtime capsule collider (trees); 0 = none

        public InstancedSpec(float distance, bool shadows, float align, float lod = 0f, bool collider = false,
                             float lod2 = 0f, float trunkRadius = 0f, float trunkHeight = 0f)
        {
            this.distance = distance; this.shadows = shadows; this.align = align; this.lod = lod;
            this.collider = collider; this.lod2 = lod2; this.trunkRadius = trunkRadius; this.trunkHeight = trunkHeight;
        }
    }

    /// <summary>Scenery placed as GameObjects (prefabs with LODGroups and colliders).</summary>
    public struct PropKind
    {
        public float cullHeight;     // LOD screen height below which it disappears (scaled by Detail setting)
        public bool shadows;
        public int collider;         // 0 none, 1 mesh, 2 convex mesh, 3 trunk capsule
        public float alignToGround;  // 0 upright .. 1 fully aligned to terrain normal
    }

    /// <summary>Everything that differs between regions when the scene builder assembles a scene.</summary>
    public class RegionProfile
    {
        public string id, title, scenePath;
        public string propsModel, formationsModel;
        public string[] landmarkModels;
        public Func<Texture2D, Material> terrainMaterial;
        public Func<Material> trackMaterial;
        public Func<string, string> layerTexture;            // physics layer -> terrain texture (for TerrainLayers)
        public TerrainSurfaces.LayerSurface[] surfaces;       // null = TerrainSurfaces defaults (desert)
        public bool hazardGreenIsWater;
        public Dictionary<string, InstancedSpec> instanced;
        public Dictionary<string, PropKind> kinds;
        public bool water;

        // Light, sky and grade.
        public Vector3 sunEuler;
        public Color sunColor;
        public float sunIntensity;
        public Color ambientSky, ambientEquator, ambientGround, fogColor;
        public Color skyTint;
        public float atmosphereThickness, skyExposure;
        public Color farLit, farShadow, farHaze, midLit, midShadow, midHaze;
        public float farHazeAmount, farHazeHeight, midHazeAmount, midHazeHeight, farSnowLine;
        public float contrast, saturation, temperature;
        public float cloudCoverage;
    }

    public static class RegionProfiles
    {
        public static readonly RegionProfile Desert = new RegionProfile
        {
            id = "desert", title = "Desert", scenePath = "Assets/Scenes/Prototype.unity",
            propsModel = "Assets/Models/Props/DesertProps.fbx",
            formationsModel = "Assets/Models/Formations/Formations.fbx",
            landmarkModels = new[] { "Assets/Models/Landmarks/DesertLandmarks.fbx" },
            terrainMaterial = MaterialLibrary.DesertTerrain,
            trackMaterial = MaterialLibrary.DirtTrack,
            layerTexture = name => name switch { "Gravel" => "Pavement", "CrackedSoil" => "Mud", "RedRock" => "Sandstone", _ => "Sand" },
            instanced = new Dictionary<string, InstancedSpec>
            {
                ["Grass"] = new InstancedSpec(110f, false, 0.6f),
                ["Scrub"] = new InstancedSpec(220f, true, 0.3f),
                ["Rock"] = new InstancedSpec(180f, true, 0.8f),
                ["Yucca"] = new InstancedSpec(200f, true, 0.1f),
                ["Boulder"] = new InstancedSpec(330f, true, 0.6f, 70f, true),
            },
            kinds = new Dictionary<string, PropKind>
            {
                ["Boulder"] = new PropKind { cullHeight = 0.004f, shadows = true, collider = 1, alignToGround = 0.6f },
                ["Slab"] = new PropKind { cullHeight = 0.006f, shadows = true, collider = 1, alignToGround = 0.85f },
                ["Hoodoo"] = new PropKind { cullHeight = 0.0015f, shadows = true, collider = 1, alignToGround = 0f },
                ["Rock"] = new PropKind { cullHeight = 0.012f, shadows = false, collider = 2, alignToGround = 0.8f },
                ["DeadTree"] = new PropKind { cullHeight = 0.006f, shadows = true, collider = 3, alignToGround = 0.05f },
            },
            sunEuler = new Vector3(36f, 205f, 0f), sunColor = new Color(1f, 0.92f, 0.80f), sunIntensity = 2.45f,
            ambientSky = new Color(0.41f, 0.51f, 0.72f), ambientEquator = new Color(0.62f, 0.52f, 0.45f),
            ambientGround = new Color(0.39f, 0.25f, 0.17f), fogColor = new Color(0.72f, 0.77f, 0.84f),
            skyTint = new Color(0.40f, 0.50f, 0.70f), atmosphereThickness = 0.85f, skyExposure = 1.25f,
            farLit = new Color(0.56f, 0.61f, 0.74f), farShadow = new Color(0.38f, 0.45f, 0.60f), farHaze = new Color(0.74f, 0.79f, 0.87f),
            farHazeAmount = 0.5f, farHazeHeight = 420f, farSnowLine = 0f,
            midLit = new Color(0.80f, 0.47f, 0.33f), midShadow = new Color(0.52f, 0.32f, 0.27f), midHaze = new Color(0.74f, 0.77f, 0.84f),
            midHazeAmount = 0.42f, midHazeHeight = 180f,
            contrast = 15f, saturation = 5f, temperature = 2f,
            cloudCoverage = 0.34f,
        };

        public static readonly RegionProfile Forest = new RegionProfile
        {
            id = "forest", title = "Forest", scenePath = "Assets/Scenes/Forest.unity",
            propsModel = "Assets/Models/Props/ForestProps.fbx",
            formationsModel = "Assets/Models/Formations/GraniteFormations.fbx",
            landmarkModels = new[] { "Assets/Models/Landmarks/ForestLandmarks.fbx", "Assets/Models/Landmarks/DesertLandmarks.fbx" },
            terrainMaterial = MaterialLibrary.ForestTerrain,
            trackMaterial = MaterialLibrary.DirtTrackForest,
            layerTexture = name => name switch { "Meadow" => "Meadow", "Soil" => "ForestSoil", "Granite" => "Granite", _ => "ForestFloor" },
            surfaces = TerrainSurfaces.ForestLayers(),
            hazardGreenIsWater = true,
            water = true,
            instanced = new Dictionary<string, InstancedSpec>
            {
                ["Fir"] = new InstancedSpec(1000f, true, 0.05f, 55f, false, 190f, 0.32f, 9f),
                ["Snag"] = new InstancedSpec(500f, true, 0.05f, 0f, false, 0f, 0.28f, 8f),
                ["Aspen"] = new InstancedSpec(600f, true, 0.05f, 45f, false, 0f, 0.16f, 7f),
                ["Fern"] = new InstancedSpec(85f, false, 0.6f),
                ["Bush"] = new InstancedSpec(140f, true, 0.4f),
                ["MeadowGrass"] = new InstancedSpec(110f, false, 0.6f),
                ["Flowers"] = new InstancedSpec(100f, false, 0.6f),
                ["GBoulder"] = new InstancedSpec(380f, true, 0.6f, 70f, true),
            },
            kinds = new Dictionary<string, PropKind>
            {
                ["Log"] = new PropKind { cullHeight = 0.008f, shadows = true, collider = 2, alignToGround = 0.9f },
                ["Stump"] = new PropKind { cullHeight = 0.01f, shadows = true, collider = 2, alignToGround = 0.3f },
            },
            sunEuler = new Vector3(40f, 140f, 0f), sunColor = new Color(1f, 0.95f, 0.86f), sunIntensity = 2.25f,
            ambientSky = new Color(0.52f, 0.60f, 0.70f), ambientEquator = new Color(0.50f, 0.54f, 0.46f),
            ambientGround = new Color(0.30f, 0.31f, 0.23f), fogColor = new Color(0.66f, 0.74f, 0.80f),
            skyTint = new Color(0.42f, 0.52f, 0.66f), atmosphereThickness = 1.0f, skyExposure = 1.15f,
            farLit = new Color(0.66f, 0.72f, 0.82f), farShadow = new Color(0.34f, 0.42f, 0.55f), farHaze = new Color(0.70f, 0.77f, 0.85f),
            farHazeAmount = 0.55f, farHazeHeight = 420f, farSnowLine = 0.62f,
            midLit = new Color(0.20f, 0.28f, 0.22f), midShadow = new Color(0.11f, 0.16f, 0.14f), midHaze = new Color(0.60f, 0.68f, 0.75f),
            midHazeAmount = 0.5f, midHazeHeight = 220f,
            contrast = 14f, saturation = 4f, temperature = -3f,
            cloudCoverage = 0.5f,
        };

        public static readonly RegionProfile[] All = { Desert, Forest };
    }
}
