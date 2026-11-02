# Handoff: continuing Offroad Expedition locally on the Mac

You are picking this project up on the owner's Mac (M2 MacBook Air, 16 GB). Until now it was built
entirely in a cloud session that could not run the game at real speed or download assets. Locally you
can do both, so test everything you change in the Unity editor and use real asset libraries.

## The project in one page

- **Game:** an original open-world off-road expedition game. Unity **6000.0.32f1**, URP, three regions,
  each its own scene: Fire Canyon (desert, `Assets/Scenes/Prototype.unity`), Cedar Hollow (forest,
  `Forest.unity`) and Highline Pass (alpine, `Alpine.unity`).
- **Everything is generated:** scenes are built by `Assets/Editor/PrototypeSceneBuilder.cs`
  (menu *Offroad > Rebuild Prototype Scene*, also run by CI) from:
  - terrain data made by `tools/terrain/generate_*.py` (heightmaps, splat/mask/hazard maps, tracks,
    landmark sites, scatter lists in `Assets/Terrain/Source~/`)
  - models made by headless Blender scripts in `blender/` (pip `bpy`), exported as FBX to `Assets/Models/`
    (convention: models face Blender -Y; `blender/lib/common.py` `export_fbx` rotates them for Unity)
  - textures from `tools/art/*.py` (CC0 ambientCG scans in `tools/art/sources/` plus procedural)
  - per-region settings in `Assets/Editor/RegionProfile.cs`; materials in `Assets/Editor/MaterialLibrary.cs`
  - `tools/generate_all.sh <python>` regenerates every asset. Python needs bpy, numpy, scipy, pillow,
    scikit-image (`python3 -m venv .venv && .venv/bin/pip install bpy numpy scipy pillow scikit-image`).
- **Shaders:** custom HLSL in `Assets/Art/Shaders/` (`Desert.hlsl` is the shared include: hex-tiling,
  triplanar, fog; `Trails.hlsl` for tyre ruts). WebGL allows only 16 samplers per shader, so keep that limit.
- **Vehicle:** `Assets/Scripts/Vehicles/` uses a custom raycast-wheel rigidbody vehicle
  (`OffroadVehicle.cs`: friction-circle tyres, surface types, sinking in sand/mud/snow, wading). The body,
  wheels and accessories come from `blender/vehicles/fleet.py` and are put together by
  `VehicleAssembler.cs`, with garage options in `Assets/Scripts/Garage/`.
- **Game flow and UI:** `Assets/Scripts/Game/` (missions, region travel, photo mode F2, landmark tour
  F9, tow/reset R). The UI is UI Toolkit, built in code (`Assets/Scripts/UI/`).
- **CI:** `.github/workflows/` (GameCI) runs edit- and play-mode tests, builds WebGL (published to
  the `webgl-build` branch) and an ad-hoc-signed Mac app (artifact `Offroad-Expedition-mac`).
  Unity credentials live only in GitHub secrets. Never ask for, print or store passwords or license
  data; local Unity activation is done by the owner in Unity Hub.

## Just fixed in the cloud, not yet verified on a Mac (check these first)

1. **UI tiny, upside-down in a corner, unclickable on the Mac.**
   `Assets/Scripts/Rendering/UIOverlayOwnership.cs` now has the engine draw the UI natively after
   URP. Confirm that the menus are full size and clickable, and that it still works at every graphics preset.
2. **See-through, inside-out rock formations** (all signed-distance rock models were wound inward).
   Fixed in `blender/formations/sandstone_formations.py` `mesh_from_sdf`, and all formation FBXs were
   regenerated. Confirm on the desert cliffs and mounds.
3. **Light rays** (`Assets/Scripts/Rendering/SunShaftsFeature.cs`) now composite with a read-write pass.
   Confirm the scene doesn't flicker or go black when you face the sun.

## What the owner wants next (their words, condensed; all of it matters)

The owner played the build and called it "decent, but really unplayable". In priority order:

1. **Driving physics that feel right.** Gravity and weight feel off. Wanted:
   - Faster top speed.
   - Drifts if you time it right.
   - Long-travel, accurate suspension with visible articulation.
   - Real tip-over risk on off-camber ground: no artificial anti-roll or auto-righting that removes the
     tension.
   - Easy to crawl over rocks.
   - A gearbox with an Auto/Manual toggle, gears selectable in manual, and gear 1 (low range) able to
     crawl up anything short of near-vertical.

   Approach: realistic mass (~1.8–2.2 t), centre of mass, gravity -9.81. Use an engine torque curve,
   gearbox ratios plus a transfer case low range, and a slip-based tyre model with proper load
   sensitivity. Add a handbrake for drifting. Tune in play mode on the Mac at real frame rates.
2. **The R (reset/tow) button can be spammed to launch the car high into the air.** Fix it: add a
   cooldown, place the car on the ground surface (raycast down, small clearance), zero all velocities,
   and refuse while the car is already upright and moving.
3. **Clipping through objects is easy.** Audit every solid object for a proper collider: rock formations
   (mesh colliders), instanced boulders (collider-only objects), trees (trunk capsules only exist near
   the vehicle), and landmarks. Use continuous collision detection on the vehicle rigidbody, and check
   the body collider covers the whole car.
4. **A much better vehicle model:** a proper Jeep-style rock crawler. Look at the reference images the
   owner shared: the Offroad Horizons Jeep, RC crawlers, and SnowRunner's Scout. Show:
   - Solid axles with visible links and coilovers.
   - Big aggressive tyres on beadlock wheels.
   - Rock sliders, roll cage or roof rack, and a winch bumper.

   Prefer a properly licensed high-quality model (check the licence and record it in
   `docs/art-direction.md`), or build a far more detailed one in Blender. Wheels and axles must line
   up with the physics.
5. **Intentional, technical level design, not "just road".** Obstacles should block and choke the
   tracks so you have to pick lines:
   - Rock gardens and boulder fields.
   - Ledges and steps.
   - Off-camber slabs.
   - V-notches.
   - Log crossings.
   - Steep climbs with good and bad lines.
   - Water crossings.

   Lots of rock crawling, placed deliberately (not randomly scattered; "right now all the objects look
   like they've just been thrown around"). Build hand-designed obstacle sections along every trail with
   clear difficulty, and make each region's trails a series of challenges between landmarks.
6. **Feedback:** surface-specific particles from the wheels (dust, gravel, mud spray, snow) and when
   sliding. Also camera, sound and HUD cues for tilt and wheel lift.
7. **Look:** the owner's dream target is SnowRunner. Their favourite reference is the old Scout
   perched on lichen-covered granite above an autumn valley: photo-scanned rocks with moss and lichen,
   rich ground cover, autumn colour, atmospheric distance. Use high-quality CC0 assets where they fit:
   - Poly Haven models and textures.
   - ambientCG.
   - Free Megascans/Fab content, if the owner adds it through their own account.
8. **General polish** everywhere: UI, menus, transitions.

## How to work

- Use real feedback. Run the game in the editor on the Mac and capture screenshots, e.g. a small
  editor script that renders the game camera to PNG. Iterate on what you see; don't guess.
- The owner prefers efficiency over lots of screenshots: do the work, look, iterate.
- Keep the generated-content pipeline (scripts are the source of truth), keep CI green, and commit
  in small steps with clear messages.
- Keep it running cool and smooth on an M2 Air: watch draw calls, shadow distance and instancing,
  and keep the graphics presets in `Assets/Scripts/Settings/GameSettings.cs`.
- Never commit secrets.
