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

## How it plays

- **Expeditions**: pick a route from base camp (rock garden shakedown, the Needle's Eye arch, Prospector's Well, the Rustbucket salvage, the Chimneys hoodoo field) or free roam.
- **Scrap**: earned by finishing expeditions and discovering landmarks; spent in the garage.
- **Garage**: two bodies (Ridgeback short-wheelbase wagon, Packhorse long-wheelbase pickup), three tyre types with surface trade-offs (Trailhound A/T all-rounder, Gripjaw M/T rock crawler that bogs in sand, Dunerunner sand floater that slides on rock), tyre grades, engine and suspension stages, accessories and paint.
- **Spare wheel**: whatever tyre you mount on the back can be swapped on once per expedition. Choose it for the terrain you expect at the far end of the route.

Graphics presets: **Battery Saver** (30 FPS cap, runs cool), **Low**, **Medium** (default on Mac), **High**, and individual options.

## Project layout

| Path | What |
|---|---|
| `blender/vehicles/` | The fleet: two bodies, three tyre types, accessories |
| `blender/landmarks/` | Landmarks: arch, balanced rock, windmill outpost, wreck, camp, cairns |
| `blender/props/` | Scenery: rocks, boulders, scrub, yuccas, dead trees |
| `blender/preview/` | Quick Cycles renders for reviewing models |
| `tools/terrain/` | Terrain generator: heightmap, paint layers, ground textures, landmark sites, clustered scenery |
| `tools/art/` | Procedural foliage sprites and wood/rust/steel/canvas textures |
| `Assets/Art/Shaders/` | Triplanar sandstone rock shader and wind-swaying foliage shader |
| `Assets/UI/` | UI Toolkit stylesheet and fonts (Barlow, SIL Open Font License) |
| `Assets/Scripts/` | Game code: vehicle physics, camera, settings, HUD, atmosphere |
| `Assets/Editor/` | Builds the scene, materials, prefabs and project settings from code |
| `Assets/Tests/` | Edit-mode asset checks and play-mode vehicle physics tests |
| `tools/playtest.js` | Loads a WebGL build in headless Chrome and takes screenshots |
| `tools/compile-check/` | Compiles the C# against Unity's libraries without Unity |

### How the scene is made

The Unity scene isn't edited by hand. `Assets/Editor/PrototypeSceneBuilder.cs` builds it from the generated data. In the Unity editor, use **Offroad → Rebuild Prototype Scene**. CI runs the same builder before every build. When the project is opened for the first time, the scene is generated automatically.

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
