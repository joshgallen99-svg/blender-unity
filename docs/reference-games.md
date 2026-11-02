# Reference games: Over the Hill and SnowRunner

Research for the redesign (November 2026). **Over the Hill** is the main target for how the game plays
and how it looks. **SnowRunner** is the target for rock and terrain detail. Facts are paraphrased from
reviews, interviews and technical write-ups (sources at the end). Anything marked *our read* is our own
interpretation, not a sourced fact. This is an original game: we take lessons, not content.

## At a glance

| | Over the Hill (Funselektor, Oct 2026) | SnowRunner (Saber Interactive, 2020) |
|---|---|---|
| Pitch | Cosy open-world off-road exploration; "almost an anti-racing game" | Heavy-duty off-road logistics sim; "off-roading is a battle" |
| Core verb | Pick a line, get stuck, recover with tools | Plan a route, haul cargo, recover with winch and drivetrain |
| Vehicles | 1960s–80s 4x4s, four categories, unlicensed but recognisable | Licensed trucks and scouts, deep upgrade trees |
| Drivetrain | Auto/manual gears, high/low range, no diff lock | AWD toggle, diff lock, low gears, tyre types |
| Recovery | Winch (quick and manual), land anchors, planks, jack, repair kit | Winch to trees/objects/other trucks |
| Structure | Handmade maps, camps/cabins, trail challenges, towing jobs, meteorites, wildlife photos | ~30 km² over 1–4 km² maps, contracts, watchtowers reveal the map |
| Engine | Unity 6, team of 12–14 | Saber's Swarm engine with MudRunner's terrain simulation (Havok physics) |
| Look | Stylised, clean, low-poly, rich colour | PBR, filmic tonemapping, deformable mud and snow |
| Min spec | GTX 1070 / i5-7400, 8 GB | Consoles at 30 fps with dynamic resolution |

## Over the Hill

### Why it is fun

- **Getting stuck is the game, not a failure.** A bogged vehicle isn't a restart. You change angle,
  drop to low range, place support, back off to firmer ground, or winch. Recovery takes visible,
  chosen actions and some effort, so mishaps become stories.
- **Freedom of line.** Routes aren't marked roads. You read the terrain and choose your own line up a
  slope, and every map is handmade, so each destination is memorable.
- **Gentler than SnowRunner on purpose.** The creative director made it after finding SnowRunner
  sometimes too hard. It aims for an arcade-sim middle ground: heavy, "toy-like" physics with a direct link
  between input and vehicle (one reviewer compares it to Trials).
- **Trails give purpose.** Reviewers agree the checkpoint trail challenges are the best part: narrow
  gorges, mountain passes, technical perimeter routes. The open wandering can feel aimless or repetitive
  without them.
- **Co-op convoys.** Up to four players. A lead calls hazards, others anchor at the top and winch the
  rest up, or push each other. Shared trouble makes the best moments.
- **Mood.** Campfires, a cassette player, shooting stars, day/night and weather. Storms and night feel
  isolating; sunny valleys are made for photo mode.

### Core mechanics

- **Winch.** Quick mode hooks the tree you're looking at, or the nearest winch point or player; hold the
  same button to reel in. A manual radial mode picks both attachment points. Range is upgradeable.
  Several vehicles can be chained into a "winch train". Reviewers sometimes found the pull strength
  inconsistent.
- **Tools** (limited slots, upgradeable to four): land anchors (single use; they stay in the world for
  other players), planks to bridge gaps and add traction, a jack to flip the vehicle upright, repair
  kit, a bell that clears bad weather, and a meteorite radar/compass.
- **Driving.** Auto or manual transmission and high/low range. Low range is also used on the flat to
  go slowly and safely. Suspension movement is readable and predictable. Water can flood the air
  intake, so snorkels matter.
- **Terrain.** Deformable sand, snow and mud: tracks persist, can be retraced, and affect physics.
  Weather changes grip; rivers wash the vehicle clean.
- **World structure.** Interconnected maps (Canada and Algeria at launch, linked by portals). Camps
  and cabins work as fast travel: rest, change time of day, reveal map sections, restock tools. There
  is no minimap; opening the map interrupts driving.
- **Things to do.** Vistas, cosmetic crates, towing broken-down vehicles back to camp, checkpoint trail
  challenges, night-glowing meteorites to dig out, and a wildlife photo journal.
- **Progression.** The currency is pebbles, earned from all of the above and spent at a merchant van.
  Upgrades are linear: engine, suspension height, tyres, winch range, snorkel. Cosmetics are free.
  Reviewers found vehicle differences hard to feel, so many stuck with one upgraded vehicle.

### How it looks and how it's made

- **Engine and team.** Unity 6, chosen because the team knows it best. Few custom tools; most effort
  goes into integrating third-party lighting, level-design, terrain, optimisation and multiplayer
  tools. 12–14 people, self-funded. Skipping pre-production caused them problems later.
- **Style.** The minimalist style carried over from *art of rally*: low-poly shapes, rich colour, clean
  rather than photoreal, not fully flat-shaded. Valleys get waterfalls and snowy peaks; the desert
  reads as more subdued with fewer surprises.
- *Our read of the reference images:* (1) large, simple forms with few, readable shapes per object;
  (2) almost no texture noise, so colour comes from vertex or flat albedo plus soft ambient occlusion;
  (3) a strong, warm key light with cool sky fill and heavy aerial perspective (distance fades to a pale,
  tinted haze); (4) tight, saturated palettes per biome (autumn gold larches against dark firs; red
  sandstone with teal water); (5) foliage as chunky cards and cones; (6) gentle bloom and colour
  grading doing most of the mood work.
- **Performance.** Minimum spec is a GTX 1070; previews reported frame drops on a mid-range laptop.
  An M2 Air is weaker than that, so our budget has to be leaner than theirs.

## SnowRunner

### Why it is fun

- **The terrain is the antagonist.** Mud, snow, ice and rivers of different depths, mixed and changed
  often, so you keep adapting.
- **Planning, then executing.** You scout, pick a truck, fit tyres, plan a route, and set out on a long
  haul. When it goes well it's soothing; inching free on the winch is very satisfying.
- **Specialised builds with trade-offs.** High suspension, snorkel, big wheels and engine for bogs; but
  roof loads and oversized tyres make a truck top-heavy on rocks.
- **Exploration pays.** Watchtowers reveal the map; upgrades and hidden vehicles are found in the
  world. Many players say exploring is their favourite part.
- The downside is that it's slow, punishing early, and easy to tip over or fall into trap spots.

### Core mechanics

- **AWD and diff lock** add traction at a cost (fuel; diff lock makes turning harder). Low gears let you
  crawl. Throttle-first driving just digs holes.
- **Tyres** matter more than anything else; chains for ice.
- **Winch** needs an anchor such as a tree or object; it's how you rescue yourself and others.
- **Contracts** from companies, done in any order; Driver Rank unlocks tyres.
- **Maps** are 1–4 km² each, about 30 km² in total, connected by gateways.

### How it looks and how it's made

- **Engine.** Saber's Swarm engine (also used for World War Z) with MudRunner's terrain simulation
  ported in; Havok physics.
- **Rendering** (developer notes): full PBR materials, filmic HDR tonemapping and modern bloom,
  shadow maps for everything near the camera, TAA plus contrast-adaptive sharpening, a new weather
  system with clouds, light shafts, rain and snow, redone vegetation with improved LODs and
  "advanced billboards" for trees, far-plane objects to sell map size, texture streaming up to 4K, and
  dynamic resolution on consoles.
- **Terrain.** Maps up to 2×2 km with higher terrain mesh resolution; 4 texture layers per area (up
  from 2) plus a snow layer that blends four extra normal maps.
- **Mud, from the MudRunner technical write-up:**
  - The world is split into 16 m blocks; only visible blocks are drawn and only blocks near the truck
    are simulated.
  - Each block has a 25×25 texture (elevation, material blend, softness tint, mud mask) and, only where
    there is mud, a 128×128 mud texture (mud height relative to the terrain, slide offset, blend).
  - Wheels and chassis are drawn as "primitives" (from position, size, velocity, penetration) into a
    render target that updates the mud heights. It's tuned by eye rather than physically based.
  - Tracks render in two passes (heights with their own depth so newer tracks cover older ones, then a
    parallax pass). Mud spray is CPU particles on a worker thread; mud clumps are rigid bodies; water
    flow is baked from editor-drawn rivers.

## What this means for our game

Status of each lesson in this project (✔ have, ◐ partly, ✘ missing), most valuable first:

| Lesson | Status | Next step |
|---|---|---|
| Stuck is a puzzle, recovery is visible and chosen | ◐ winch with auto anchor + portable anchor; R recovery | Make R a **jack** with a short animation and cost; add **planks**; anchors stay placed |
| Quick winch on what you look at, plus manual | ◐ quick mode picks the best anchor ahead | Aim by camera direction; anchor marker/preview; upgradeable range |
| Low range, auto/manual | ✔ | Add a **diff lock** toggle (more grip, wider turns), shown on the HUD |
| Handmade trails with good and bad lines | ✔ 43 graded sections (`tools/terrain/obstacles.py`) | Turn them into **named trail challenges** with checkpoints, start/finish markers and rewards |
| Things to find | ◐ landmarks, discovery, missions | Towing jobs, vistas, collectables, wildlife photo journal (we already have photo mode, F2) |
| Camps as fast travel that reveal the map | ◐ camps per region | Unlock camps by reaching them; reveal map sections; no minimap |
| Deformable ground affects physics | ◐ visual tyre trails (`GroundTrails`), sinking in mud/snow | Rut heightfield near the vehicle (Spintires-style blocks) that the wheels then follow |
| Weather and night change grip | ✘ | Rain lowers grip and darkens ground; night needs headlights |
| Specialised builds and trade-offs | ◐ tyres, bodies, accessories | Snorkel matters for fording depth (already modelled); roof load raises the centre of mass |
| Readable suspension | ✔ solid axles, links and coilovers move | Tune damping by feel |
| Clean, warm, stylised-real look | ◐ ACES, sun shafts, fog, impostors | Per-biome palettes, stronger aerial perspective, chunky foliage, ambient occlusion |
| Performance on an M2 Air | ◐ presets, instancing | Keep draw calls and shadow distance low; profile each region |

## Sources

Over the Hill
- [80.lv: Creating a co-op driving adventure game (developer interview)](https://80.lv/articles/over-the-hill-creating-a-co-op-driving-adventure-game)
- [Steam store page](https://store.steampowered.com/app/2929250/over_the_hill/)
- [GamerGuru: when the road runs out, it hands you a winch](https://gamerguru.net/editorial/over-the-hill-slow-routes-winch-co-op)
- [The Wand Report review](https://report.wand.com/reviews/over-the-hill-review)
- [Traxion review](https://traxion.gg/over-the-hill-review-cosy-and-captivating-off-roading/)
- [GamesRadar review](https://www.gamesradar.com/games/open-world/over-the-hill-review/)
- [TechRadar review](https://www.techradar.com/gaming/over-the-hill-review)
- [RacingGames.gg preview](https://racinggames.gg/article/over-the-hill-preview-funselektors-gorgeous-co-op-off-roader-channels-pure-a-short-hike-energy)
- [Kotaku announcement coverage](https://kotaku.com/art-rally-over-hill-trailer-minimalist-steam-coop-1851746273)
- [PCGamingWiki](https://www.pcgamingwiki.com/wiki/Over_the_Hill)
- [Over the Hill wiki: gameplay](https://overthehillgame.wiki/game-info/gameplay)
- [Art of Rally (Wikipedia)](https://en.wikipedia.org/wiki/Art_of_Rally)

SnowRunner
- [GamingBolt developer interview](https://gamingbolt.com/snowrunner-interview-physics-progression-customization-and-more)
- [Engine and visuals changes (MudRunner Mods, from developer notes)](https://www.mudrunnermods.com/engine-visuals-snowrunner/)
- [Game Developer: Mud and water of Spintires: MudRunner](https://www.gamedeveloper.com/programming/mud-and-water-of-spintires-mudrunner)
- [Saber support FAQ](https://support.saber.games/hc/en/snowrunner/articles/snow-runner-faq-1)
- [SnowRunner (Wikipedia)](https://en.wikipedia.org/wiki/SnowRunner)
- [Gaming Trend review](https://gamingtrend.com/a-muddy-good-time-snowrunner-review/)
- [Well Played review](https://www.well-played.com.au/snowrunner-review/)
- [Game Pitt review](https://www.gamepitt.co.uk/?p=23933)
- [DSOGaming PC performance analysis](https://www.dsogaming.com/pc-performance-analyses/snowrunner-pc-performance-analysis/)
