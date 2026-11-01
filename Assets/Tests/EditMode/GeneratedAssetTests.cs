using System.IO;
using System.Linq;
using NUnit.Framework;
using Offroad.EditorTools;
using UnityEditor;
using UnityEngine;

/// <summary>Checks that the Blender/Python outputs import into Unity the way the game expects.</summary>
public class GeneratedAssetTests
{
    const string Vehicle = "Assets/Models/Vehicles/Fleet.fbx";
    const string Props = "Assets/Models/Props/DesertProps.fbx";

    static Mesh MeshOf(string model, string child, out Material[] mats)
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(model);
        Assert.IsNotNull(go, $"{model} should import");
        var t = go.transform.Find(child);
        Assert.IsNotNull(t, $"{model} should contain '{child}'");
        mats = t.GetComponent<MeshRenderer>().sharedMaterials;
        return t.GetComponent<MeshFilter>().sharedMesh;
    }

    [Test]
    public void VehicleFacesForwardAndIsUpright()
    {
        var body = MeshOf(Vehicle, "Body_Ridgeback", out var mats);
        var b = body.bounds;
        Assert.Greater(b.size.z, b.size.x * 1.8f, "vehicle length should run along Z");
        Assert.That(b.size.y, Is.InRange(2.0f, 3.2f), "height (incl. antenna) in metres");
        Assert.That(b.min.y, Is.InRange(0.25f, 0.6f), "underside sits above the ground plane");

        int lights = System.Array.FindIndex(mats, m => m && m.name == "Lights");
        Assert.GreaterOrEqual(lights, 0, "Body should have a 'Lights' material");
        var verts = body.vertices;
        var tris = body.GetTriangles(lights);
        float z = tris.Average(i => verts[i].z);
        Assert.Greater(z, 0.5f, "lights centre should be toward +Z overall (front headlights dominate)");
        var head = tris.Select(i => verts[i]).Where(v => v.y < 1.3f).ToArray();
        Assert.Greater(head.Length, 0);
        Assert.Greater(head.Average(v => v.z), 1.9f, "headlights must be at the front (+Z)");
    }

    [Test]
    public void WheelMarkersMatchRigDefaults()
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(Vehicle);
        string[] names = { "Ridgeback_WheelFL", "Ridgeback_WheelFR", "Ridgeback_WheelRL", "Ridgeback_WheelRR" };
        for (int i = 0; i < 4; i++)
        {
            var t = go.transform.Find(names[i]);
            Assert.IsNotNull(t, names[i]);
            Assert.Less((t.localPosition - Offroad.Vehicles.VehicleRig.DefaultWheelPositions[i]).magnitude, 0.05f,
                $"{names[i]} at {t.localPosition}");
        }
    }

    [Test]
    public void WheelShowFaceIsOnLeft()
    {
        var wheel = MeshOf(Vehicle, "Wheel_AT", out var mats);
        int cap = System.Array.FindIndex(mats, m => m && m.name == "Steel");
        Assert.GreaterOrEqual(cap, 0);
        var verts = wheel.vertices;
        float x = wheel.GetTriangles(cap).Average(i => verts[i].x);
        Assert.Less(x, 0f, "hub cap / bolts should face -X (vehicle left) so the rig can mirror right wheels");
    }

    [Test]
    public void FleetHasEveryPartTheGarageSells()
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(Vehicle);
        foreach (var b in Offroad.Garage.Catalog.Bodies)
        {
            Assert.IsNotNull(go.transform.Find($"Body_{b.mesh}"), b.mesh);
            Assert.IsNotNull(go.transform.Find($"{b.mesh}_Spare"), b.mesh + " spare mount");
            foreach (var a in Offroad.Garage.Catalog.Accessories)
                Assert.IsNotNull(go.transform.Find($"{a.id}_{b.mesh}"), $"{a.id} for {b.mesh}");
        }
        foreach (var t in Offroad.Garage.Catalog.Tires) Assert.IsNotNull(go.transform.Find(t.mesh), t.mesh);
        // Packhorse wheelbase is 3 m.
        Assert.AreEqual(1.5f, go.transform.Find("Packhorse_WheelFL").localPosition.z, 0.02f);
    }

    [Test]
    public void TyreTradeOffsPointTheRightWay()
    {
        var sand = new Vector4(1, 0, 0, 0);
        var rock = new Vector4(0, 0, 0, 1);
        var at = Offroad.Garage.Catalog.Tire("at");
        var mt = Offroad.Garage.Catalog.Tire("mt");
        var dune = Offroad.Garage.Catalog.Tire("dune");
        Assert.Greater(Offroad.Garage.Catalog.Suitability(dune, sand), Offroad.Garage.Catalog.Suitability(at, sand));
        Assert.Greater(Offroad.Garage.Catalog.Suitability(at, sand), Offroad.Garage.Catalog.Suitability(mt, sand));
        Assert.Greater(Offroad.Garage.Catalog.Suitability(mt, rock), Offroad.Garage.Catalog.Suitability(at, rock));
        Assert.Greater(Offroad.Garage.Catalog.Suitability(at, rock), Offroad.Garage.Catalog.Suitability(dune, rock));
    }

    [Test]
    public void AllPropVariantsExist()
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(Props);
        Assert.IsNotNull(go);
        foreach (var n in new[] { "Boulder_0", "Boulder_5", "Slab_2", "Hoodoo_2", "Grass_1", "Rock_0", "Rock_4", "Scrub_0", "Scrub_2", "Yucca_0", "Yucca_1", "DeadTree_0", "DeadTree_1" })
        {
            var t = go.transform.Find(n);
            Assert.IsNotNull(t, n);
            Assert.GreaterOrEqual(t.GetComponent<MeshFilter>().sharedMesh.bounds.min.y, -0.25f, $"{n} pivot should be at its base");
        }
    }

    [Test]
    public void LandmarksExistAndWindmillRotorSitsOnTheTower()
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Landmarks/DesertLandmarks.fbx");
        Assert.IsNotNull(go);
        foreach (var n in new[] { "NeedlesEye", "BalancedRock", "Windmill", "Windmill_Rotor", "WaterTank", "Shack", "Wreck",
                                  "Tent", "FireRing", "Crates", "Cairn", "Signpost" })
            Assert.IsNotNull(go.transform.Find(n), n);
        var rotor = go.transform.Find("Windmill_Rotor").localPosition;
        Assert.That(rotor.y, Is.InRange(8.5f, 10.5f), "rotor hub height");
        Assert.Greater(rotor.z, 0.2f, "rotor is on the front (+Z) of the tower");
    }

    [Test]
    public void LandmarkPiecesReferenceRealModels()
    {
        var info = JsonUtility.FromJson<PrototypeSceneBuilder.RegionInfo>(File.ReadAllText("Assets/Terrain/Source~/desert_info.json"));
        var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Landmarks/DesertLandmarks.fbx");
        Assert.GreaterOrEqual(info.landmarks.Length, 5);
        foreach (var l in info.landmarks)
            foreach (var p in l.pieces)
                Assert.IsNotNull(go.transform.Find(p.model), $"{l.name}: {p.model}");
    }

    [Test]
    public void TerrainSourceDataIsConsistent()
    {
        var info = JsonUtility.FromJson<PrototypeSceneBuilder.RegionInfo>(File.ReadAllText("Assets/Terrain/Source~/desert_info.json"));
        Assert.AreEqual(info.resolution * info.resolution * 2, new FileInfo("Assets/Terrain/Source~/desert_height.r16").Length);
        Assert.AreEqual(4, info.layers.Length);
        foreach (var l in info.layers)
        {
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{l}_albedo.png"), l);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Terrain/Textures/{l}_normal.png"), l);
        }
        var scatter = JsonUtility.FromJson<PrototypeSceneBuilder.ScatterFile>(File.ReadAllText("Assets/Terrain/Source~/desert_scatter.json"));
        Assert.Greater(scatter.props.Length, 1000);
        Assert.That(info.spawn.x, Is.InRange(50f, info.size - 50f));
    }
}
