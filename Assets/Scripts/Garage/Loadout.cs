using System;
using System.Collections.Generic;
using Offroad.World;
using UnityEngine;

namespace Offroad.Garage
{
    /// <summary>The player's garage: what they own, upgrade levels and what's fitted. Saved in PlayerPrefs.</summary>
    [Serializable]
    public class Loadout
    {
        [Serializable]
        public class Level
        {
            public string id;
            public int level;
        }

        public string body = "crawler";
        public string tire = "rock";
        public string spare = "dune";
        public int engineLevel;
        public int suspensionLevel;
        public int paint;
        public List<string> ownedBodies = new List<string> { "crawler", "ridgeback" };
        public List<string> ownedTires = new List<string> { "rock", "at", "dune" };
        public List<string> ownedAccessories = new List<string> { "RoofRack" };
        public List<string> fittedAccessories = new List<string> { "RoofRack" };
        public List<Level> tireLevels = new List<Level>();

        const string Key = "offroad.loadout.v1";
        static Loadout _current;

        public static Loadout Current => _current ??= Load();
        public static event Action<Loadout> Changed;

        public int TireLevel(string id)
        {
            var l = tireLevels.Find(x => x.id == id);
            return l?.level ?? 0;
        }

        public bool Owns(string id) => ownedBodies.Contains(id) || ownedTires.Contains(id) || ownedAccessories.Contains(id);
        public bool Fitted(string accessory) => fittedAccessories.Contains(accessory);

        // ------------------------------------------------------------------ actions (return false if unaffordable)

        public bool BuyOrEquipBody(Catalog.BodyDef b)
        {
            if (!ownedBodies.Contains(b.id))
            {
                if (!Progress.Spend(b.price)) return false;
                ownedBodies.Add(b.id);
            }
            body = b.id;
            Commit();
            return true;
        }

        public bool BuyOrEquipTire(Catalog.TireDef t)
        {
            if (!ownedTires.Contains(t.id))
            {
                if (!Progress.Spend(t.price)) return false;
                ownedTires.Add(t.id);
            }
            tire = t.id;
            Commit();
            return true;
        }

        public bool SetSpare(Catalog.TireDef t)
        {
            if (!ownedTires.Contains(t.id)) return false;
            spare = t.id;
            Commit();
            return true;
        }

        public bool UpgradeTire(Catalog.TireDef t)
        {
            int lvl = TireLevel(t.id);
            if (!ownedTires.Contains(t.id) || lvl >= t.upgradeCost.Length) return false;
            if (!Progress.Spend(t.upgradeCost[lvl])) return false;
            var entry = tireLevels.Find(x => x.id == t.id);
            if (entry == null) tireLevels.Add(new Level { id = t.id, level = 1 });
            else entry.level++;
            Commit();
            return true;
        }

        public bool Upgrade(Catalog.UpgradeTrack track)
        {
            int lvl = track == Catalog.Engine ? engineLevel : suspensionLevel;
            if (lvl >= track.MaxLevel || !Progress.Spend(track.cost[lvl])) return false;
            if (track == Catalog.Engine) engineLevel++;
            else suspensionLevel++;
            Commit();
            return true;
        }

        public bool ToggleAccessory(Catalog.AccessoryDef a)
        {
            if (!ownedAccessories.Contains(a.id))
            {
                if (!Progress.Spend(a.price)) return false;
                ownedAccessories.Add(a.id);
                fittedAccessories.Add(a.id);
            }
            else if (fittedAccessories.Contains(a.id)) fittedAccessories.Remove(a.id);
            else fittedAccessories.Add(a.id);
            Commit();
            return true;
        }

        public void SetPaint(int index)
        {
            paint = Mathf.Clamp(index, 0, Catalog.Paints.Length - 1);
            Commit();
        }

        public void Commit()
        {
            PlayerPrefs.SetString(Key, JsonUtility.ToJson(this));
            PlayerPrefs.Save();
            Changed?.Invoke(this);
        }

        static Loadout Load()
        {
            try
            {
                var json = PlayerPrefs.GetString(Key, "");
                if (!string.IsNullOrEmpty(json))
                {
                    var l = JsonUtility.FromJson<Loadout>(json) ?? new Loadout();
                    // Saves from before the crawler: hand it over, with its tyres, and drive it.
                    if (!l.ownedBodies.Contains("crawler"))
                    {
                        l.ownedBodies.Insert(0, "crawler");
                        if (!l.ownedTires.Contains("rock")) l.ownedTires.Insert(0, "rock");
                        l.body = "crawler";
                        l.tire = "rock";
                    }
                    return l;
                }
            }
            catch (Exception e) { Debug.LogWarning("Loadout reset: " + e.Message); }
            return new Loadout();
        }

        public static void ResetAll()
        {
            _current = new Loadout();
            _current.Commit();
        }
    }
}
