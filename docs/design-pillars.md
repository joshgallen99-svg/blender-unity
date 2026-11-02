# Design pillars

The owner's targets, in order: **Over the Hill** (Funselektor, 2026) for how it plays and the cosy,
performant look, and **SnowRunner** for the rock and terrain detail (the Scout on lichen-covered granite
above an autumn valley). This is an original game; we borrow ideas and feel, never content.

## How it plays

1. **Technical rock scrambling is the game.** Boulder fields, ledges, off-camber slabs, V-notches, logs and
   steep climbs, placed by hand along every track with a readable good line and a harder bad line
   (`tools/terrain/obstacles.py`). Not "just road".
2. **The vehicle is the tool kit.** Auto/manual gearbox with a low-range crawl gear, then diff lock and a
   winch. Over the Hill reviewers single out the winch, used on trees and rocks, as the standout tool,
   because it makes recovery part of the puzzle rather than a reset. A portable anchor covers open
   ground.
3. **Real tension, honest physics.** Weight, momentum and tip-over risk are real: no auto-righting and no
   hidden anti-roll. The HUD, camera and sound warn you; the R recovery is a limited last resort
   (cooldown, refused while driving).
4. **Trials give purpose.** Reviews found open wandering a little aimless and the trial challenges the
   best part. Each region's tracks are a chain of graded trials between landmarks; discovering them
   reveals the map and earns upgrade currency.
5. **Arcade-sim middle ground.** Easy to pick up, deep to master.

## How it looks

- Stylised-real: chunky readable shapes with soft light, strong atmosphere and colour grading (Over the
  Hill), dressed with a few CC0 photo-scanned rock materials, moss and lichen, and autumn colour
  (SnowRunner). See `docs/art-direction.md` for asset licences.
- Performance first on an M2 MacBook Air: GPU instancing, short shadow distance, few post effects,
  graphics presets in `Assets/Scripts/Settings/GameSettings.cs`.

## Sources

- [Over the Hill review (TechRadar)](https://www.techradar.com/gaming/over-the-hill-review)
- [Over the Hill review (RacingGames.gg)](https://racinggames.gg/article/over-the-hill-review-the-ultimate-cozy-exploration-racing-game)
- [Over the Hill demo preview](https://racinggames.gg/article/over-the-hill-demo-preview-the-art-of-rally-devs-just-reopened-the-great-outdoors)
- [SnowRunner tips (PlayStation Blog)](https://blog.playstation.com/?p=223636)
- [SnowRunner review (Jalopnik)](https://jalopnik.com/snowrunner-is-a-nuanced-off-road-driving-game-to-get-lo-1843110799)
