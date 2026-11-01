using System;
using System.Collections.Generic;
using UnityEngine;

namespace Offroad.World
{
    /// <summary>A named place the player can discover (arch, well, camp...).</summary>
    public class Landmark : MonoBehaviour
    {
        public string id;
        public string displayName;
        public float discoverRadius = 40f;
        public int reward = 150;

        public static readonly List<Landmark> All = new List<Landmark>();

        public bool Discovered => Progress.IsDiscovered(id);

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        void OnDrawGizmos()
        {
            Gizmos.color = new Color(1f, 0.5f, 0.1f, 0.6f);
            Gizmos.DrawWireSphere(transform.position, discoverRadius);
        }
    }

    /// <summary>Saved exploration progress and currency ("scrap"), shared by the HUD and the garage.</summary>
    public static class Progress
    {
        const string Key = "offroad.progress.v1";

        [Serializable]
        class Data
        {
            public List<string> discovered = new List<string>();
            public int scrap = 300;
        }

        static Data _data;
        static Data D => _data ??= Load();

        public static event Action<Landmark> Discovered;
        public static event Action<int> ScrapChanged;

        public static int Scrap => D.scrap;
        public static int DiscoveredCount => D.discovered.Count;

        public static bool IsDiscovered(string id) => D.discovered.Contains(id);

        public static void Discover(Landmark l)
        {
            if (string.IsNullOrEmpty(l.id) || D.discovered.Contains(l.id)) return;
            D.discovered.Add(l.id);
            D.scrap += l.reward;
            Save();
            Discovered?.Invoke(l);
            ScrapChanged?.Invoke(D.scrap);
        }

        public static bool Spend(int amount)
        {
            if (amount > D.scrap) return false;
            D.scrap -= amount;
            Save();
            ScrapChanged?.Invoke(D.scrap);
            return true;
        }

        public static void Add(int amount)
        {
            D.scrap += amount;
            Save();
            ScrapChanged?.Invoke(D.scrap);
        }

        public static void ResetAll()
        {
            _data = new Data();
            Save();
            ScrapChanged?.Invoke(D.scrap);
        }

        static Data Load()
        {
            try
            {
                var json = PlayerPrefs.GetString(Key, "");
                if (!string.IsNullOrEmpty(json)) return JsonUtility.FromJson<Data>(json) ?? new Data();
            }
            catch (Exception e) { Debug.LogWarning("Progress reset: " + e.Message); }
            return new Data();
        }

        static void Save()
        {
            PlayerPrefs.SetString(Key, JsonUtility.ToJson(D));
            PlayerPrefs.Save();
        }
    }
}
