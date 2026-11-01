# blender-unity

A Unity game with assets made from Blender scripts. Heavy work (modelling, rendering, builds) runs in the cloud. A Mac only opens the project and plays it.

## Layout

| Path | What |
|---|---|
| `Assets/` | Unity project: scripts, scenes, models |
| `blender/` | Python scripts that generate models into `Assets/Models/` |
| `tools/playtest.js` | Serves a WebGL build in headless Chrome and takes screenshots |
| `.github/workflows/build.yml` | Runs tests and a WebGL build on every push |

Unity version: **6000.0.32f1** (Unity 6). Install that version through Unity Hub.

## One-time setup: Unity licence for GitHub builds

The build workflow skips itself until these secrets exist. Add them in the repo on GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

1. `UNITY_EMAIL`: your Unity account email.
2. `UNITY_PASSWORD`: your Unity account password.
3. `UNITY_LICENSE`: the full contents of your Unity licence file.
   - Sign in to Unity Hub on your Mac and activate a free **Personal** licence (Hub → Settings → Licenses → Add).
   - Open `/Library/Application Support/Unity/Unity_lic.ulf` in TextEdit and paste the whole file as the secret's value.

After that, every push builds a WebGL version, downloadable from the **Actions** tab as the `WebGL` artifact.

## Making models

```bash
pip install bpy
python blender/example_rock.py
```

## Playtesting a build

```bash
node tools/playtest.js path/to/WebGL-build playtest-output 20
```
