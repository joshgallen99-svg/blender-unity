# Offroad Expedition (working title)

An open-world off-road driving game built with **Blender** (models, generated from Python scripts) and **Unity 6 + URP**. It is designed to run well on a MacBook Air.

Heavy work runs in the cloud: models are generated with Blender's Python module, and GitHub Actions builds and tests the Unity project. Your Mac only runs the finished game.

## Playing the latest build

1. Open the repo's **Actions** tab on GitHub and click the latest green **Test and build** run.
2. Under **Artifacts**, download **Offroad-Expedition-mac** (native Mac app, best performance) or **WebGL** (browser version).
3. Mac app: double-click the `.tar.gz` to unpack it. The first time, right-click the app, choose **Open**, then **Open** again. The app isn't signed, so macOS asks once.

### Controls

| Action | Keyboard | Gamepad |
|---|---|---|
| Accelerate / brake & reverse | W / S (or arrows) | Right / left trigger |
| Steer | A / D | Left stick |
| Handbrake | Space | B |
| Reset vehicle | R | Y |
| Look around | Mouse | Right stick |
| Swap to the spare wheel (once per expedition, when stopped) | T | X |
| Pause, settings and graphics presets | Esc or P | Start |
| Menus: continue / open garage | Enter / G | A / Select |
| FPS counter | F1 | |
| Jump to the next landmark (sightseeing / screenshots) | F9 | |
| Photo mode: hide the HUD, orbit with A/D, tilt W/S, zoom Q/E | F2 | |
| Expedition list: move the selection | Up / Down (W / S) | D-pad |

## How it plays

- **Two regions**, each its own scene; pick an expedition anywhere and the game travels there:
  - **Fire Canyon** (desert): an old wagon track up a valley of sandstone formations, side tracks to the
    landmarks, The Wave, dunes, a playa. Hazards: quicksand in the wash near the spring, wet mud,
    washboard corrugations.
  - **Cedar Hollow** (forest river valley): firs, aspens, granite domes, a river with two fords and an
    old timber bridge, a waterfall and plunge lake, switchbacks to a fire lookout, mud holes and a
    beaver-pond bog. Deep water floods the engine.
- **Soft ground**: tyres press ruts into sand, soil and mud (they stay behind you), and settle into
  them; quicksand swallows a slow vehicle; R tows you back to firm ground.
- **Expeditions**: Fire Canyon has a rock-garden shakedown, the Needle's Eye arch, Prospector's Well, the
  Rustbucket salvage and the Chimneys; Cedar Hollow has Twin Falls, Fire Watch, Mud Season and the Old
  Logging Road; both have free roam.
- **Scrap**: earned by finishing expeditions and discovering landmarks; spent in the garage.
- **Garage**: two bodies (Ridgeback short-wheelbase wagon, Packhorse long-wheelbase pickup), three tyre types with surface trade-offs (Trailhound A/T all-rounder, Gripjaw M/T rock and mud crawler that bogs in sand, Dunerunner sand floater that slides on rock and in mud), tyre grades, engine and suspension stages, accessories and paint.
- **Spare wheel**: whatever tyre you mount on the back can be swapped on once per expedition. Choose it for the terrain you expect at the far end of the route.

Graphics presets: **Battery Saver** (30 FPS cap, runs cool), **Low**, **Medium** (default on Mac), **High**, and individual options. Each preset caps the internal render height (720/900/1080/1440 lines) and FSR upscales to the screen, so a Retina display doesn't cost 2.5x the GPU work.

## Project layout

| Path | What |
|---|---|
| `blender/vehicles/` | The fleet: two bodies, three tyre types, accessories |
| `blender/landmarks/` | Landmarks: arch, balanced rock, windmill outpost, wreck, camp, cairns; log cabin, fire lookout, timber bridge |
| `blender/props/` | Scenery: desert rocks, scrub, yuccas; forest firs (with impostors), aspens, logs, granite boulders, ferns |
| `blender/formations/` | Big landforms as signed distance fields: sandstone mounds/fins/spires/arch; granite domes/crags/falls |
| `blender/preview/` | Quick Cycles renders for reviewing models |
| `tools/terrain/` | Region generators (desert, forest): heightmap, tracks, rivers, hazards, masks, landmark sites, scenery |
| `tools/art/` | Ground textures (CC0 scans re-coloured + procedural), foliage sprites, material textures |
| `Assets/Art/Shaders/` | Terrain (hex-tiled, height-blended), rock, dirt-track decal, water, foliage, backdrop, tyre-trail shaders |
| `Assets/UI/` | UI Toolkit stylesheet and fonts (Barlow, SIL Open Font License) |
| `Assets/Scripts/` | Game code: vehicle physics, camera, settings, HUD, atmosphere |
| `Assets/Editor/` | Builds the scene, materials, prefabs and project settings from code |
| `Assets/Tests/` | Edit-mode asset checks and play-mode vehicle physics tests |
| `tools/playtest.js` | Loads a WebGL build in headless Chrome and takes screenshots |
| `tools/compile-check/` | Compiles the C# against Unity's libraries without Unity |

### How the scene is made

The Unity scenes aren't edited by hand. `Assets/Editor/PrototypeSceneBuilder.cs` builds every region (settings in `Assets/Editor/RegionProfile.cs`) from the generated data. In the Unity editor, use **Offroad → Rebuild Prototype Scene**. CI runs the same builder before every build. When the project is opened for the first time, the scene is generated automatically.

### Regenerating assets

```bash
pip install bpy numpy scipy pillow
tools/generate_all.sh
```

## Cloud builds (one-time setup)

The workflow needs three repository secrets (**Settings → Secrets and variables → Actions**): `UNITY_EMAIL`, `UNITY_PASSWORD`, and `UNITY_LICENSE` (the contents of `/Library/Application Support/Unity/Unity_lic.ulf` after activating a free Personal license in Unity Hub). Each push to `main` then:

1. runs all tests (asset checks + vehicle physics),
2. builds WebGL and publishes it to the `webgl-build` branch for automated playtesting,
3. builds the native Mac app (artifact `Offroad-Expedition-mac`).

Unity version: **6000.0.32f1**.
