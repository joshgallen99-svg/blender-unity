using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using RiverInfo = Offroad.EditorTools.PrototypeSceneBuilder.RiverInfo;
using LakeInfo = Offroad.EditorTools.PrototypeSceneBuilder.LakeInfo;
using FallsInfo = Offroad.EditorTools.PrototypeSceneBuilder.FallsInfo;

namespace Offroad.EditorTools
{
    /// <summary>
    /// Builds the river and lake surfaces from the terrain itself, instead of laying flat ribbons and
    /// ellipses over it (those hung over low banks and folded over themselves on tight bends).
    ///
    /// 1. On a 2 m grid, every point near the river takes the water level of the closest stretch of river
    ///    (or the lake's level inside the lake basin).
    /// 2. A point is wet only if the ground there is below that level.
    /// 3. Wet points are flood-filled outward from the channel, so water never appears in unconnected
    ///    hollows beside the river.
    /// 4. Only grid cells touching filled points get water, plus one dry ring for the shoreline; the
    ///    shader then fades the surface out exactly where it meets the ground, per pixel.
    /// The result is one continuous surface (no overlaps between the river and the lake), split into
    /// 64 m tiles for culling. Vertex data follows the Water shader's conventions.
    /// </summary>
    public static class WaterSurfaceBuilder
    {
        const float Cell = 2f;
        const float Tile = 64f;
        const float BankReach = 6f;      // how far past the river's half-width water may reach (over low banks)

        public static List<Mesh> Build(Terrain terrain, RiverInfo river, LakeInfo lake, FallsInfo falls)
        {
            float ty = terrain.transform.position.y;
            bool hasRiver = river != null && river.x != null && river.x.Length > 2;
            bool hasLake = lake != null && lake.rx > 0f;
            var meshes = new List<Mesh>();
            if (!hasRiver && !hasLake) return meshes;

            // --- Grid bounds around all water.
            float minX = float.MaxValue, minZ = float.MaxValue, maxX = float.MinValue, maxZ = float.MinValue;
            void Grow(float x, float z, float r)
            {
                minX = Mathf.Min(minX, x - r); maxX = Mathf.Max(maxX, x + r);
                minZ = Mathf.Min(minZ, z - r); maxZ = Mathf.Max(maxZ, z + r);
            }
            if (hasRiver)
                for (int i = 0; i < river.x.Length; i++) Grow(river.x[i], river.z[i], river.halfWidth[i] + BankReach + Cell);
            if (hasLake) Grow(lake.x, lake.z, Mathf.Max(lake.rx, lake.rz) * 1.3f + Cell);
            int nx = Mathf.CeilToInt((maxX - minX) / Cell) + 1, nz = Mathf.CeilToInt((maxZ - minZ) / Cell) + 1;
            int count = nx * nz;
            Vector3 Pos(int ix, int iz) => new Vector3(minX + ix * Cell, 0f, minZ + iz * Cell);

            var level = new float[count];
            var best = new float[count];
            var ground = new float[count];
            var uv = new Vector2[count];
            var dir = new Vector2[count];
            var col = new Color[count];
            var seed = new bool[count];
            for (int k = 0; k < count; k++) { level[k] = float.NaN; best[k] = float.MaxValue; }
            for (int iz = 0; iz < nz; iz++)
            for (int ix = 0; ix < nx; ix++)
                ground[iz * nx + ix] = terrain.SampleHeight(Pos(ix, iz)) + ty;

            Vector2 fallsXZ = falls != null && falls.top > 0f ? new Vector2(falls.x, falls.z) : new Vector2(1e6f, 1e6f);

            // --- 1a. River: nearest stretch of the centre line gives level, flow direction and texture coordinates.
            if (hasRiver)
            {
                int n = river.x.Length;
                var dist = new float[n];
                for (int i = 1; i < n; i++)
                    dist[i] = dist[i - 1] + Vector2.Distance(new Vector2(river.x[i], river.z[i]), new Vector2(river.x[i - 1], river.z[i - 1]));
                var turb = new float[n];
                for (int i = 0; i < n; i++)
                {
                    // Rapids where the river is narrow or drops fast.
                    int i2 = Mathf.Min(i + 4, n - 1), i0 = Mathf.Max(i - 4, 0);
                    float drop = (river.level[i0] - river.level[i2]) / Mathf.Max(dist[i2] - dist[i0], 1f);
                    turb[i] = Mathf.Clamp01((10f - river.halfWidth[i]) / 6f * 0.6f + drop * 25f);
                }
                bool churnAtHead = falls != null && falls.top > 0f;
                for (int s = 0; s < n - 1; s++)
                {
                    var a = new Vector2(river.x[s], river.z[s]);
                    var b = new Vector2(river.x[s + 1], river.z[s + 1]);
                    var ab = b - a;
                    float len2 = Mathf.Max(ab.sqrMagnitude, 1e-4f);
                    var fwd = ab.normalized;
                    var right = new Vector2(fwd.y, -fwd.x);
                    float reach = Mathf.Max(river.halfWidth[s], river.halfWidth[s + 1]) + BankReach;
                    int x0 = Mathf.Max(0, Mathf.FloorToInt((Mathf.Min(a.x, b.x) - reach - minX) / Cell));
                    int x1 = Mathf.Min(nx - 1, Mathf.CeilToInt((Mathf.Max(a.x, b.x) + reach - minX) / Cell));
                    int z0 = Mathf.Max(0, Mathf.FloorToInt((Mathf.Min(a.y, b.y) - reach - minZ) / Cell));
                    int z1 = Mathf.Min(nz - 1, Mathf.CeilToInt((Mathf.Max(a.y, b.y) + reach - minZ) / Cell));
                    for (int iz = z0; iz <= z1; iz++)
                    for (int ix = x0; ix <= x1; ix++)
                    {
                        var p = new Vector2(minX + ix * Cell, minZ + iz * Cell);
                        float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / len2);
                        var q = a + ab * t;
                        float d = Vector2.Distance(p, q);
                        float hw = Mathf.Lerp(river.halfWidth[s], river.halfWidth[s + 1], t);
                        int k = iz * nx + ix;
                        if (d > hw + BankReach || d >= best[k]) continue;
                        best[k] = d;
                        level[k] = Mathf.Lerp(river.level[s], river.level[s + 1], t);
                        float along = Mathf.Lerp(dist[s], dist[s + 1], t);
                        uv[k] = new Vector2(Vector2.Dot(p - q, right), along);
                        dir[k] = right;
                        float foam = churnAtHead ? Mathf.Clamp01(1f - along / 45f) : 0f;   // churned water below the falls
                        col[k] = new Color(Mathf.Lerp(turb[s], turb[s + 1], t), foam, 0f, 1f);
                        seed[k] = d < hw * 0.6f;
                    }
                }
            }

            // --- 1b. Lake: its basin takes the lake level (it wins over the river mouth inside the basin).
            if (hasLake)
            {
                var inv = Quaternion.Euler(0f, lake.yaw, 0f);   // undo the lake's rotation
                for (int iz = 0; iz < nz; iz++)
                for (int ix = 0; ix < nx; ix++)
                {
                    int k = iz * nx + ix;
                    var p = Pos(ix, iz);
                    var local = inv * new Vector3(p.x - lake.x, 0f, p.z - lake.z);
                    float e = Mathf.Sqrt((local.x / lake.rx) * (local.x / lake.rx) + (local.z / lake.rz) * (local.z / lake.rz));
                    if (e > 1.3f) continue;
                    if (!float.IsNaN(level[k]) && e > 1.15f) continue;
                    level[k] = lake.level;
                    best[k] = 0f;
                    uv[k] = new Vector2(p.x, p.z);
                    dir[k] = new Vector2(1f, 0f);
                    // A churning foam ring where the falls hit the lake, spreading out and thinning.
                    float dFalls = Vector2.Distance(new Vector2(p.x, p.z), fallsXZ - new Vector2(0f, 4f));
                    float foam = Mathf.Clamp01(1.25f - dFalls / 24f);
                    float churn = Mathf.Clamp01(1f - dFalls / 30f);
                    col[k] = new Color(0.15f + 0.85f * churn, foam, 0f, 0.08f + 0.5f * churn);
                    seed[k] = e < 0.6f;
                }
            }

            // --- 2 + 3. Wet points, flood-filled from the channel and the lake centre.
            var filled = new bool[count];
            var queue = new Queue<int>();
            for (int k = 0; k < count; k++)
                if (seed[k] && !float.IsNaN(level[k]) && ground[k] < level[k]) { filled[k] = true; queue.Enqueue(k); }
            while (queue.Count > 0)
            {
                int k = queue.Dequeue();
                int ix = k % nx, iz = k / nx;
                for (int o = 0; o < 4; o++)
                {
                    int jx = ix + (o == 0 ? 1 : o == 1 ? -1 : 0), jz = iz + (o == 2 ? 1 : o == 3 ? -1 : 0);
                    if (jx < 0 || jz < 0 || jx >= nx || jz >= nz) continue;
                    int j = jz * nx + jx;
                    if (filled[j] || float.IsNaN(level[j]) || ground[j] >= level[j]) continue;
                    // A big step in level means a different stretch of river (e.g. the far side of a bend).
                    if (Mathf.Abs(level[j] - level[k]) > 1.5f) continue;
                    filled[j] = true;
                    queue.Enqueue(j);
                }
            }

            // Vertex values: a filled point keeps its own; a shoreline point borrows from its wet neighbours,
            // so the surface stays level out to where the shader fades it against the bank.
            int Source(int k)
            {
                if (filled[k]) return k;
                int ix = k % nx, iz = k / nx, bestJ = -1;
                float bestLevel = float.MinValue;
                for (int dz = -1; dz <= 1; dz++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    int jx = ix + dx, jz = iz + dz;
                    if (jx < 0 || jz < 0 || jx >= nx || jz >= nz) continue;
                    int j = jz * nx + jx;
                    if (filled[j] && level[j] > bestLevel) { bestLevel = level[j]; bestJ = j; }
                }
                return bestJ;
            }

            // --- 4. Cells touching water, one mesh per tile.
            var tiles = new Dictionary<Vector2Int, TileMesh>();
            for (int iz = 0; iz < nz - 1; iz++)
            for (int ix = 0; ix < nx - 1; ix++)
            {
                int c00 = iz * nx + ix, c10 = c00 + 1, c01 = c00 + nx, c11 = c01 + 1;
                if (!(filled[c00] || filled[c10] || filled[c01] || filled[c11])) continue;
                var p = Pos(ix, iz);
                var key = new Vector2Int(Mathf.FloorToInt(p.x / Tile), Mathf.FloorToInt(p.z / Tile));
                if (!tiles.TryGetValue(key, out var tm)) tiles[key] = tm = new TileMesh();
                int V(int k)
                {
                    if (tm.map.TryGetValue(k, out int vi)) return vi;
                    int src = Source(k);
                    var wp = Pos(k % nx, k / nx);
                    wp.y = level[src] + ty;
                    var dv = dir[src];
                    // A borrowed shoreline point extrapolates the texture coordinates of the river (they are
                    // continuous in space); the lake uses world position anyway.
                    var tuv = src == k ? uv[k] : (float.IsNaN(level[k]) ? uv[src] + Offset(wp, Pos(src % nx, src / nx), dv) : uv[k]);
                    vi = tm.v.Count;
                    tm.v.Add(wp);
                    tm.t.Add(new Vector4(dv.x, 0f, dv.y, 1f));
                    tm.uv.Add(tuv);
                    tm.c.Add(col[src]);
                    tm.map[k] = vi;
                    return vi;
                }
                int a0 = V(c00), a1 = V(c10), b0 = V(c01), b1 = V(c11);
                tm.i.Add(a0); tm.i.Add(b0); tm.i.Add(b1);
                tm.i.Add(a0); tm.i.Add(b1); tm.i.Add(a1);
            }

            foreach (var kv in tiles)
            {
                var tm = kv.Value;
                var m = new Mesh { name = $"Water_{kv.Key.x}_{kv.Key.y}" };
                if (tm.v.Count > 65000) m.indexFormat = IndexFormat.UInt32;
                m.SetVertices(tm.v);
                var normals = new Vector3[tm.v.Count];
                for (int k = 0; k < normals.Length; k++) normals[k] = Vector3.up;
                m.SetNormals(normals);
                m.SetTangents(tm.t);
                m.SetUVs(0, tm.uv);
                m.SetColors(tm.c);
                m.SetTriangles(tm.i, 0);
                m.RecalculateBounds();
                meshes.Add(m);
            }
            return meshes;
        }

        static Vector2 Offset(Vector3 at, Vector3 from, Vector2 right)
        {
            var d = new Vector2(at.x - from.x, at.z - from.z);
            var fwd = new Vector2(-right.y, right.x);
            return new Vector2(Vector2.Dot(d, right), Vector2.Dot(d, fwd));
        }

        class TileMesh
        {
            public readonly Dictionary<int, int> map = new Dictionary<int, int>();
            public readonly List<Vector3> v = new List<Vector3>();
            public readonly List<Vector4> t = new List<Vector4>();
            public readonly List<Vector2> uv = new List<Vector2>();
            public readonly List<Color> c = new List<Color>();
            public readonly List<int> i = new List<int>();
        }
    }
}
