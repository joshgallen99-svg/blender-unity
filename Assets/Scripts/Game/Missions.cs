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
        };

        public static MissionDef Find(string id) => Array.Find(All, m => m.id == id);
    }
}
