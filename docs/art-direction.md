# Art direction: Fire Canyon

Reference points: Valley of Fire (beehive formations, red sandstone along an old highway), The Wave
(swirling striped slickrock), cracked desert ground with layered outcrops, and a stylised game desert
with tall spires. Target: grounded, warm and readable. AAA in composition and cohesion, modest in
cost so a fanless MacBook Air holds 60 FPS on Medium.

## Principles

1. **The world is built around the rock.** Formations are placed first. The heightmap, ground
   textures, vegetation and paths are generated *around* them (aprons under each formation, desert
   pavement fans, grass belts, boulder talus). Nothing is sprinkled uniformly.
2. **Big shapes first.** Formations are 15–110 m and are combined into massifs (several overlapping
   pieces at 1.5–3× scale) that line the valley. Gateway formations pinch in close to the road to frame
   views. Small props only add detail at the base.
3. **One bedrock.** Terrain cliffs, slickrock and every rock mesh use the same world-space strata
   palette (`Assets/Art/Shaders/Desert.hlsl`), so a band of cream rock continues from a formation into
   the cliff behind it.
4. **Rocks sit *in* the ground, not on it.** Rocks sink 1–4 m below the surface and the rock shader
   blends to sand within about a metre of the terrain (read from the global heightmap). Sand also
   settles on ledges.
5. **Height-based blending.** Ground layers blend by their height maps: sand fills the cracks of mud
   plates and between pavement stones. Slopes over ~40° and masked areas turn to layered sandstone.
6. **Nothing visibly tiles.** Ground textures are hex-tiled (Mikkelsen 2022: every hexagon samples
   the texture with a random offset and rotation, blended by texel height). Wind ripples are drawn in
   world space, and colour varies at three scales (patches of tens of metres, iron-red and pale wash
   zones of hundreds of metres, and region-wide zones).
7. **Contrast.** Deep, cool shadows against warm sunlit rock: moderate ambient fill, ACES with
   +15 contrast and +5 saturation, and gentle split toning (cool shadows, warm highlights). Fog starts at 30% of the view distance
   so mid-distance rock stays crisp.
8. **Dirt tracks, not roads.** An old wagon track runs up the valley with side tracks to every
   landmark. Tracks are decal ribbons over the terrain (`DirtTrack.shader`): two compacted wheel ruts,
   a crown with loose sand (weeds on side tracks), ragged sandy edges, washboard stretches, and they
   fade out where dunes have drifted over them. Formations are pushed aside so tracks squeeze through
   gaps in the rock.
9. **Hazards read before you hit them.** Wet mud is dark and glossy with water in the ruts; quicksand
   is pale, smooth and slowly breathing, ringed by damp sand and marked by a warning sign. Both come
   from one hazard map (`desert_hazard.png`: R mud, G quicksand, B washboard, A water) that the
   shaders and the vehicle physics read.
10. **A living sky.** Procedural cumulus (Clouds.shader) drift over both regions, lit from the sun
    side with a silver lining near it and fading into the horizon haze; sparse over the canyon, fuller
    over the valley.
11. **Layers of distance.** Near rocks → valley → border cliffs → red mesas (1.4 km) → blue mountain
   ranges (2.6–3.4 km), with bluer haze the further you go.

## Palette (linear)

| Band | Colour | Share of beds |
|---|---|---|
| Deep red | 0.26, 0.04, 0.018 | 24% |
| Rust | 0.48, 0.10, 0.032 | 31% |
| Orange | 0.68, 0.24, 0.085 | 24% |
| Salmon | 0.76, 0.40, 0.20 | 12% |
| Cream | 0.82, 0.62, 0.40 | 6.5% |
| Pale | 0.88, 0.76, 0.62 | 2.5% |

Bed thickness is irregular (a monotonic warp of the band coordinate), with occasional thin iron or
bleached seams. In some zones the rock above ~65–95 m is bleached to cream and pale, like Valley of
Fire's White Domes.

Ground: pinkish-orange sand, buff cracked mud with dark cracks, desert pavement in varnished red-brown
stones. Vegetation: straw and sage-green bunch grass, dusty sage shrubs, the occasional flowering
brittlebush. Sky: deep blue overhead, pale blue haze at the horizon.

## Budgets (per frame, Medium preset)

- Formations: LOD0 ~6–16k triangles each up close, LOD1 ~1.5–4k at distance.
- Instanced scenery: grass drawn to ~110 m, shrubs and rocks ~200 m (× Scenery Detail).
- Shadows: 70 m (Low/Medium), 160 m (High).
- Textures: 1024 px ground and rock sets; one 1024 region mask; one macro-variation texture.

## Where things come from

| What | Generator |
|---|---|
| Formations | `blender/formations/sandstone_formations.py` |
| Region layout, masks, scatter | `tools/terrain/generate_desert.py` |
| Ground and rock textures | `tools/art/generate_terrain_textures.py` (sand grain from a CC0 scan, see below) |
| Foliage sprites | `tools/art/generate_foliage_textures.py` |
| Composition preview (Blender) | `blender/preview/render_scene.py` |

## Cedar Hollow (forest river valley)

Reference points: Sierra Nevada and Cascades valleys: granite domes above fir forest, a clear river
over pale gravel bars, meadows with aspen groves, logging-era tracks with fords and timber bridges.

- **Composition.** The river is the spine: valley floor of meadows and gravel bars, firs climbing the
  slopes to granite crags and two domes, a cliff band and waterfall closing the valley in the north.
- **Trees** are the forest's "formations": firs (16-24 m, V-shaped needle sprays around a hidden trunk)
  drawn with GPU instancing at three detail levels: full cards close up, sparser cards mid-range, and
  rendered impostor cards (from Cycles side renders) to the horizon. Aspens add yellow-green near water.
- **Water** reads depth from the terrain heightmap: clear over the gravel at the edges, dark green-blue
  in the pools, foam in shallows, rapids and below the falls, sky reflected by Fresnel.
- **Soft ground everywhere**: forest soil and mud take deep ruts (tyre trails), fords cross the river at
  under a metre, mud holes sit in the low spots of the tracks.
- **Light**: cooler morning sun from the south-east, blue-grey haze, snow on the distant ranges.

| What | Generator |
|---|---|
| Region layout, river, tracks, hazards, scatter | `tools/terrain/generate_forest.py` |
| Ground textures, bark, foliage, water | `tools/art/generate_forest_textures.py` |
| Firs (+ impostors), aspens, logs, boulders, understorey | `blender/props/forest_props.py` |
| Granite domes, crags, tors, waterfall cliff | `blender/formations/granite_formations.py` |
| Cabin, lookout, bridge, log piles | `blender/landmarks/forest_landmarks.py` |

## Third-party sources

Only used where they fit the palette and shapes exactly; everything else is made here.

| Asset | Source | Licence | Used for |
|---|---|---|---|
| Ground054 (sand scan) | [ambientCG](https://ambientcg.com/view?id=Ground054) | CC0 1.0 | Sand grain and surface relief, high-passed and re-coloured to our palette (`tools/art/sources/ambientcg/`) |
| Ground037 (forest floor) | [ambientCG](https://ambientcg.com/view?id=Ground037) | CC0 1.0 | Forest floor and meadow |
| Ground048 (forest soil) | [ambientCG](https://ambientcg.com/view?id=Ground048) | CC0 1.0 | Track soil and wet mud |
| Rock030 (rock) | [ambientCG](https://ambientcg.com/view?id=Rock030) | CC0 1.0 | Granite, cooled |
| Gravel021 (gravel) | [ambientCG](https://ambientcg.com/view?id=Gravel021) | CC0 1.0 | River gravel, lightened, silt added |
| Bark001 (bark) | [ambientCG](https://ambientcg.com/view?id=Bark001) | CC0 1.0 | Fir bark, re-coloured |
