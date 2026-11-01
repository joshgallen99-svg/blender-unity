using System;
using System.Collections.Generic;
using Offroad.Core;
using Offroad.Garage;
using Offroad.Vehicles;
using Offroad.World;
using UnityEngine;

namespace Offroad.Game
{
    [Serializable]
    public class MissionDef
    {
        public string id, title, brief, tip;
        public string[] targets;       // landmark ids, visited in order
        public bool returnToCamp;
        public int reward;
        public bool freeRoam;
        public string region = Regions.Desert;
        public string camp = "basecamp";   // landmark id of the region's camp
    }

    /// <summary>The regions you can drive, each its own scene.</summary>
    public static class Regions
    {
        public const string Desert = "desert";
        public const string Forest = "forest";

        public static string Title(string id) => id == Forest ? "Cedar Hollow" : "Fire Canyon";
        public static string Subtitle(string id) => id == Forest ? "Forest river valley" : "Desert canyon country";
        public static string Scene(string id) => id == Forest ? "Forest" : "Prototype";
        public static readonly string[] Order = { Desert, Forest };
    }

    public static class Missions
    {
        public static readonly MissionDef[] All =
        {
            new MissionDef
            {
                id = "shakedown", title = "Shakedown Run", reward = 200, returnToCamp = true,
                brief = "Take the rig through the Rock Garden south of camp, then bring it home in one piece.",
                tip = "Gripjaw M/T tyres claw up rock. Take it slow over the slabs.",
                targets = new[] { "rock_garden" },
            },
            new MissionDef
            {
                id = "needle", title = "Thread the Needle", reward = 250,
                brief = "Head north to the great sandstone arch and drive through the Needle's Eye.",
                tip = "Follow the old wagon track north through the valley, then turn east into mesa country.",
                targets = new[] { "needles_eye" },
            },
            new MissionDef
            {
                id = "water", title = "Water Run", reward = 300, returnToCamp = true,
                brief = "Check the old windmill pump at Prospector's Well and report back to camp.",
                tip = "The wash is packed dirt. All-terrain tyres are fine.",
                targets = new[] { "prospectors_well" },
            },
            new MissionDef
            {
                id = "salvage", title = "Salvage the Rustbucket", reward = 350, returnToCamp = true,
                brief = "An old pickup is half-buried in the eastern dunes. Find it and make it back.",
                tip = "Soft sand all the way. Dunerunner tyres float where others bog down. Keep your spare in mind.",
                targets = new[] { "rustbucket" },
            },
            new MissionDef
            {
                id = "chimneys", title = "Into the Chimneys", reward = 400,
                brief = "Pick a line through the hoodoo field in the south-west and reach Balanced Rock. Swing past the striped slickrock of The Wave on the way.",
                tip = "Sand on the way, rock at the end. A good moment for the spare-wheel swap.",
                targets = new[] { "chimneys" },
            },
            new MissionDef
            {
                id = "roam", title = "Free Roam", reward = 0, freeRoam = true,
                brief = "No objectives. Explore the canyon country and discover landmarks for scrap.",
                tip = "Every new landmark is worth 150 scrap.",
                targets = Array.Empty<string>(),
            },

            // ---- Cedar Hollow (forest river valley)
            new MissionDef
            {
                id = "falls", title = "Twin Falls", reward = 300, region = Regions.Forest, camp = "trailhead",
                brief = "Follow the old logging track up the valley, over the Old Bridge, to the falls at its head.",
                tip = "Two fords on the way. Under a metre of water is fine; take it slow and keep the revs up.",
                targets = new[] { "old_bridge", "twin_falls" },
            },
            new MissionDef
            {
                id = "lookout", title = "Fire Watch", reward = 350, returnToCamp = true, region = Regions.Forest, camp = "trailhead",
                brief = "Climb the switchbacks to the fire lookout on the eastern ridge, then get back to the trailhead.",
                tip = "Steep packed soil. Gripjaw M/T tyres climb best; watch the hairpins.",
                targets = new[] { "lookout" },
            },
            new MissionDef
            {
                id = "mudrun", title = "Mud Season", reward = 400, region = Regions.Forest, camp = "trailhead",
                brief = "The track to the Beaver Pond is a string of mud holes. Get there without needing a tow.",
                tip = "Mud tyres or bust: Dunerunners skate in the mud. Hit the holes with some momentum.",
                targets = new[] { "beaver_pond" },
            },
            new MissionDef
            {
                id = "logging", title = "The Old Logging Road", reward = 300, region = Regions.Forest, camp = "trailhead",
                brief = "Check on the abandoned logging camp in the south-west, then call in at the Ranger's Cabin.",
                tip = "Soft forest soil takes deep ruts: follow the wheel tracks where you can.",
                targets = new[] { "logging_camp", "ranger_cabin" },
            },
            new MissionDef
            {
                id = "roam_forest", title = "Free Roam", reward = 0, freeRoam = true, region = Regions.Forest, camp = "trailhead",
                brief = "No objectives. Explore Cedar Hollow: the river, the domes and the deep woods.",
                tip = "Every new landmark is worth 150 scrap.",
                targets = Array.Empty<string>(),
            },
        };

        public static MissionDef Find(string id) => Array.Find(All, m => m.id == id);
        public static MissionDef FreeRoam(string region) => Array.Find(All, m => m.freeRoam && m.region == region) ?? Find("roam");
    }
}
