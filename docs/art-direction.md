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
7. **Contrast.** Deep, cool shadows against warm sunlit rock: low ambient fill, ACES with +22
   contrast, and split toning (blue shadows, warm highlights). Fog starts at 30% of the view distance
   so mid-distance rock stays crisp.
8. **Layers of distance.** Near rocks → valley → border cliffs → red mesas (1.4 km) → blue mountain
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

## Third-party sources

Only used where they fit the palette and shapes exactly; everything else is made here.

| Asset | Source | Licence | Used for |
|---|---|---|---|
| Ground054 (sand scan) | [ambientCG](https://ambientcg.com/view?id=Ground054) | CC0 1.0 | Sand grain and surface relief, high-passed and re-coloured to our palette (`tools/art/sources/ambientcg/`) |
