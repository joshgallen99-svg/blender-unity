"""Hand-designed obstacle sections laid along a track: the technical driving between landmarks.

Each region generator builds a `Course` per track, lists the sections it wants (by distance along the
track), applies their terrain shaping to the heightmap before it is written, and appends their props to
the scatter list afterwards. Sections are placed on purpose, with a readable "good line" and a harder
"bad line", rather than scattered:

  rock_garden   a field of rocks across the track; small rocks along a weaving line, big ones off it
  ledges        a staircase of rocky steps up the track
  off_camber    the track tilts sideways across a slab; boulders on the low side pinch the line uphill
  v_notch       the track drops into a V-shaped gully lined with boulders; wheels ride the walls
  climb         a steep rocky hump: one side graded smooth (good line), the other stepped and strewn (bad line)
  logs          fallen logs across the track at angles (forest)

`difficulty` (1-3) scales heights, angles and rock sizes. Kinds are per region, e.g.
dict(rock="Rock", rock_variants=5, rock_size=1.0, boulder="Boulder", boulder_variants=6, boulder_size=2.5).
"""
import math

import numpy as np
from scipy.spatial import cKDTree


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Course:
    def __init__(self, name, path, xs, zs, cell, rng, kinds, avoid=None):
        self.name = name
        self.path = np.asarray(path, float)
        seg = np.hypot(*np.diff(self.path, axis=0).T)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])   # arc length at each path point
        self.length = float(self.s[-1])
        self.xs, self.zs, self.cell = xs, zs, cell
        self.rng = rng
        self.kinds = kinds
        self.sections = []
        self.avoid = avoid          # avoid(x, z) -> True where no section may sit (water, bridges, landmarks)

    # ------------------------------------------------------------------ geometry
    def frame(self, s):
        """Position, forward and right (unit, x/z) at arc length s."""
        k = int(np.clip(np.searchsorted(self.s, s), 1, len(self.path) - 2))
        p = self.path[k]
        t = self.path[k + 1] - self.path[k - 1]
        t = t / (np.hypot(*t) or 1.0)
        right = np.array([t[1], -t[0]])
        return p, t, right

    def local(self, s0, s1, margin):
        """Grid window around the section with each cell's arc length and signed lateral offset."""
        k0, k1 = np.searchsorted(self.s, [s0 - margin, s1 + margin])
        pts = self.path[max(k0, 0):min(k1 + 1, len(self.path))]
        lo = pts.min(axis=0) - margin
        hi = pts.max(axis=0) + margin
        c0, c1 = int(max(lo[0] / self.cell, 0)), int(min(hi[0] / self.cell + 1, self.xs.shape[1]))
        r0, r1 = int(max(lo[1] / self.cell, 0)), int(min(hi[1] / self.cell + 1, self.xs.shape[0]))
        X, Z = self.xs[r0:r1, c0:c1], self.zs[r0:r1, c0:c1]
        tree = cKDTree(pts)
        d, i = tree.query(np.stack([X.ravel(), Z.ravel()], -1))
        i = i + max(k0, 0)
        i = np.clip(i, 1, len(self.path) - 2)
        tang = self.path[i + 1] - self.path[i - 1]
        tang /= np.maximum(np.hypot(tang[:, 0], tang[:, 1]), 1e-6)[:, None]
        off = np.stack([X.ravel(), Z.ravel()], -1) - self.path[i]
        lateral = off[:, 0] * tang[:, 1] - off[:, 1] * tang[:, 0]        # + to the right
        along = self.s[i] + off[:, 0] * tang[:, 0] + off[:, 1] * tang[:, 1]
        shape = X.shape
        return (slice(r0, r1), slice(c0, c1)), along.reshape(shape), lateral.reshape(shape)

    def at(self, s, lateral):
        p, _, r = self.frame(s)
        return p + r * lateral

    # ------------------------------------------------------------------ sections
    def add(self, kind, at, difficulty=2, **kw):
        """Queue a section starting `at` metres along the track (negative = from the end)."""
        s0 = float(np.clip(at if at >= 0 else self.length + at, 10, self.length - 40))
        span = kw.get("length", 40.0)
        # Slide forward (then back) in 8 m steps until the whole span is clear of anything to avoid,
        # and of the sections already placed.
        for shift in [0, 8, 16, 24, 32, 40, -8, -16, -24, -32, -40]:
            a = s0 + shift
            if a < 10 or a + span > self.length - 5:
                continue
            if any(abs(a - o["s0"]) < span + 10 for o in self.sections):
                continue
            if self.avoid and any(self.avoid(*self.at(x, 0)) for x in np.arange(a - 6, a + span + 6, 3.0)):
                continue
            self.sections.append(dict(kind=kind, s0=a, difficulty=difficulty, **kw))
            break
        return self

    def shape(self, h):
        """Apply every section's terrain shaping to the heightmap (in place)."""
        for sec in self.sections:
            getattr(self, "_shape_" + sec["kind"], lambda h_, s_: None)(h, sec)

    def props(self):
        """Props for every section, in the region's scatter format."""
        out = []
        for sec in self.sections:
            out += getattr(self, "_props_" + sec["kind"], lambda s_: [])(sec)
        return out

    def records(self):
        """Section summaries for the info file (HUD / map markers)."""
        recs = []
        for sec in self.sections:
            p, _, _ = self.frame(sec["s0"])
            recs.append({"track": self.name, "kind": sec["kind"], "difficulty": sec["difficulty"],
                         "x": round(float(p[0]), 1), "z": round(float(p[1]), 1)})
        return recs

    def _prop(self, kind, variants, pos, yaw, scale, sink):
        return {"kind": kind, "variant": int(self.rng.integers(variants)), "x": round(float(pos[0]), 2),
                "z": round(float(pos[1]), 2), "yaw": round(float(yaw), 1), "scale": round(float(scale), 3),
                "sink": round(float(sink), 3)}

    def _rock(self, pos, size, sink=0.35):
        k = self.kinds
        if size > 1.6 * k["rock_size"] and k.get("boulder"):
            return self._prop(k["boulder"], k["boulder_variants"], pos, self.rng.uniform(0, 360),
                              size / k["boulder_size"], sink)
        return self._prop(k["rock"], k["rock_variants"], pos, self.rng.uniform(0, 360), size / k["rock_size"], sink)

    # rock garden -----------------------------------------------------------------------------------
    def _props_rock_garden(self, sec):
        L = sec.get("length", 22.0 + 6 * sec["difficulty"])
        half = sec.get("width", 3.4)
        out = []
        phase = self.rng.uniform(0, math.tau)
        s = sec["s0"]
        while s < sec["s0"] + L:
            line = 1.4 * math.sin(phase + (s - sec["s0"]) / L * math.tau * 1.3)
            for lat in np.arange(-half - 1.0, half + 1.01, 1.15):
                lat = lat + self.rng.uniform(-0.35, 0.35)
                off = abs(lat - line)
                if off < 0.8 and self.rng.random() < 0.6:
                    continue                                    # the line itself stays mostly clear
                big = _smoothstep(0.6, 3.2, off)
                size = (0.45 + 0.35 * sec["difficulty"]) * (0.55 + 0.9 * big) * self.rng.uniform(0.75, 1.15)
                if self.rng.random() < 0.72:
                    out.append(self._rock(self.at(s, lat), size, sink=0.3 + 0.1 * self.rng.random()))
            s += self.rng.uniform(1.4, 2.1)
        # Gate boulders mark the entry and exit.
        for ss in (sec["s0"] - 2, sec["s0"] + L + 2):
            for side in (-1, 1):
                out.append(self._rock(self.at(ss, side * (half + 2.2)), 2.4 + 0.4 * sec["difficulty"], sink=0.6))
        return out

    # ledges ----------------------------------------------------------------------------------------
    def _ledge_params(self, sec):
        steps = sec.get("steps", 2 + sec["difficulty"])
        rise = sec.get("rise", 0.3 + 0.12 * sec["difficulty"])
        gap = sec.get("gap", 6.0)
        return steps, rise, gap

    def _shape_ledges(self, h, sec):
        steps, rise, gap = self._ledge_params(sec)
        L = steps * gap
        win, along, lat = self.local(sec["s0"], sec["s0"] + L + 30, 16)
        u = along - sec["s0"]
        stair = np.zeros_like(u)
        for k in range(steps):
            stair += rise * _smoothstep(k * gap - 0.6, k * gap + 0.6, u)   # sharp-ish step faces
        # After the top step the track eases back down to its graded line over 30 m.
        stair *= 1 - _smoothstep(L + 2, L + 30, u)
        w = 1 - _smoothstep(4.5, 11.0, np.abs(lat))
        h[win] += stair * w

    def _props_ledges(self, sec):
        steps, rise, gap = self._ledge_params(sec)
        out = []
        for k in range(steps):
            for lat in np.arange(-3.6, 3.61, 0.9):
                if self.rng.random() < 0.25:
                    continue
                size = (0.55 + 0.3 * rise / 0.3) * self.rng.uniform(0.8, 1.2)
                out.append(self._rock(self.at(sec["s0"] + k * gap + 0.4, lat + self.rng.uniform(-0.2, 0.2)), size,
                                      sink=0.5))
        return out

    # off camber ------------------------------------------------------------------------------------
    def _shape_off_camber(self, h, sec):
        L = sec.get("length", 28.0)
        ang = math.radians(sec.get("angle", 12 + 5 * sec["difficulty"]))
        side = sec.get("side", 1 if self.rng.random() < 0.5 else -1)
        sec["side"] = side
        win, along, lat = self.local(sec["s0"], sec["s0"] + L, 18)
        u = along - sec["s0"]
        ramp = _smoothstep(-2, 6, u) * (1 - _smoothstep(L - 6, L + 2, u))
        tilt = side * np.clip(lat, -7, 7) * math.tan(ang)
        w = 1 - _smoothstep(7.0, 14.0, np.abs(lat))
        h[win] += tilt * ramp * w

    def _props_off_camber(self, sec):
        L = sec.get("length", 28.0)
        side = sec.get("side", 1)
        out = []
        # Boulders on the low side push the line up the slab, toward the tipping point.
        for s in np.linspace(sec["s0"] + 6, sec["s0"] + L - 6, 3 + sec["difficulty"]):
            out.append(self._rock(self.at(s, -side * self.rng.uniform(2.6, 3.6)),
                                  self.rng.uniform(1.5, 2.3) + 0.3 * sec["difficulty"], sink=0.5))
        return out

    # V notch ---------------------------------------------------------------------------------------
    def _shape_v_notch(self, h, sec):
        L = sec.get("length", 16.0)
        depth = sec.get("depth", 0.7 + 0.35 * sec["difficulty"])
        win, along, lat = self.local(sec["s0"], sec["s0"] + L, 12)
        u = along - sec["s0"]
        along_w = _smoothstep(-3, 3, u) * (1 - _smoothstep(L - 3, L + 3, u))
        v = depth * np.clip(1 - np.abs(lat) / 3.6, 0, 1)
        h[win] -= v * along_w

    def _props_v_notch(self, sec):
        L = sec.get("length", 16.0)
        out = []
        for s in np.arange(sec["s0"], sec["s0"] + L, 3.2):
            for side in (-1, 1):
                out.append(self._rock(self.at(s + self.rng.uniform(-0.6, 0.6), side * self.rng.uniform(3.6, 4.4)),
                                      self.rng.uniform(1.6, 2.4) + 0.3 * sec["difficulty"], sink=0.4))
        return out

    # climb -----------------------------------------------------------------------------------------
    def _shape_climb(self, h, sec):
        L = sec.get("length", 26.0)
        height = sec.get("height", 2.0 + 1.0 * sec["difficulty"])
        side = sec.get("side", 1 if self.rng.random() < 0.5 else -1)
        sec["side"] = side
        win, along, lat = self.local(sec["s0"], sec["s0"] + L, 16)
        u = (along - sec["s0"]) / L
        hump = np.where(u < 0.5, _smoothstep(0.0, 0.5, u), 1 - _smoothstep(0.5, 1.0, u)) * height
        # Bad line: terraced into steps on one half of the track.
        bad = _smoothstep(0.3, 1.6, side * lat)
        terraced = np.floor(hump / 0.55) * 0.55
        prof = hump * (1 - bad) + terraced * bad
        w = 1 - _smoothstep(5.0, 13.0, np.abs(lat))
        h[win] += prof * w

    def _props_climb(self, sec):
        L = sec.get("length", 26.0)
        side = sec.get("side", 1)
        out = []
        for s in np.arange(sec["s0"] + 2, sec["s0"] + L - 2, 1.6):
            for lat in np.arange(0.9, 3.8, 1.0):
                if self.rng.random() < 0.55:
                    out.append(self._rock(self.at(s, side * (lat + self.rng.uniform(-0.3, 0.3))),
                                          (0.5 + 0.25 * sec["difficulty"]) * self.rng.uniform(0.8, 1.4), sink=0.35))
        return out

    # logs ------------------------------------------------------------------------------------------
    def _props_logs(self, sec):
        k = self.kinds
        if not k.get("log"):
            return []
        out = []
        n = sec.get("count", 1 + sec["difficulty"])
        for j in range(n):
            s = sec["s0"] + j * 5.5
            _, fwd, _ = self.frame(s)
            yaw = math.degrees(math.atan2(fwd[0], fwd[1])) + 90 + self.rng.uniform(-25, 25)
            dia = (0.3 + 0.1 * sec["difficulty"]) * self.rng.uniform(0.9, 1.15)
            out.append(self._prop(k["log"], k["log_variants"], self.at(s, self.rng.uniform(-0.8, 0.8)), yaw,
                                  dia / k["log_diameter"], 0.15))
        return out
