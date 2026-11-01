"""Compile the project's C# against Unity's reference assemblies, without Unity.

Catches compile errors in seconds instead of waiting for a cloud build.

Setup (once per machine):  git clone --depth 1 -b unity-refs <repo-url> ../unity-refs
Run:  python3 tools/compile-check/check.py [path-to-unity-refs]
Needs the .NET SDK (dotnet).
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REFS = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "..", "unity-refs"))

ENGINE = glob.glob(f"{REFS}/Editor/Managed/UnityEngine/UnityEngine*.dll")
EDITOR_MODULES = glob.glob(f"{REFS}/Editor/Managed/UnityEngine/UnityEditor*.dll")
NETSTD = glob.glob(f"{REFS}/Editor/NetStandard/ref/2.1.0/netstandard.dll")
COMPAT = glob.glob(f"{REFS}/Editor/NetStandard/compat/2.1.0/shims/netfx/*.dll")
SCRIPT_ASM = {os.path.basename(p)[:-4]: p for p in glob.glob(f"{REFS}/ScriptAssemblies/*.dll")}
NUNIT = (glob.glob(f"{REFS}/PackageCache/com.unity.ext.nunit*/net40/unity-custom/nunit.framework.dll") +
         glob.glob(f"{REFS}/PackageCache/com.unity.ext.nunit*/**/nunit.framework.dll", recursive=True))[:1]

RUNTIME_PKGS = ["Unity.RenderPipelines.Universal.Runtime", "Unity.RenderPipelines.Core.Runtime", "Unity.InputSystem",
                "Unity.Mathematics", "UnityEngine.UI"]
EDITOR_PKGS = RUNTIME_PKGS + ["Unity.RenderPipelines.Universal.Editor", "Unity.RenderPipelines.Core.Editor"]
TEST_PKGS = ["UnityEngine.TestRunner", "UnityEditor.TestRunner"]

BASE_DEFINES = ["UNITY_6000_0_OR_NEWER", "UNITY_2022_3_OR_NEWER", "UNITY_2021_3_OR_NEWER", "UNITY_2020_3_OR_NEWER",
                "UNITY_INCLUDE_TESTS", "ENABLE_PHYSICS", "ENABLE_UNITYWEBREQUEST"]

ASSEMBLIES = [
    # name, source globs, package refs, project refs, editor?
    ("Game", ["Assets/Scripts/**/*.cs"], RUNTIME_PKGS, [], False),
    ("Game.Editor", ["Assets/Editor/**/*.cs"], EDITOR_PKGS, ["Game"], True),
    ("EditModeTests", ["Assets/Tests/EditMode/**/*.cs"], EDITOR_PKGS + TEST_PKGS, ["Game", "Game.Editor"], True),
    ("PlayModeTests", ["Assets/Tests/PlayMode/**/*.cs"], RUNTIME_PKGS + TEST_PKGS, ["Game"], True),
]


def ref(path):
    return (f'<Reference Include="{os.path.basename(path)[:-4]}"><HintPath>{path}</HintPath>'
            f'<Private>false</Private></Reference>')


def csproj(name, sources, pkgs, deps, editor, defines, outdir):
    refs = list(ENGINE) + NETSTD + COMPAT
    if editor:
        refs += EDITOR_MODULES
    for p in pkgs:
        if p in SCRIPT_ASM:
            refs.append(SCRIPT_ASM[p])
        else:
            print(f"  (warning: {p}.dll not in refs)")
    if any(t in pkgs for t in TEST_PKGS):
        refs += NUNIT
    refs += [os.path.join(outdir, d, "bin", f"{d}.dll") for d in deps]
    files = sorted({f for g in sources for f in glob.glob(os.path.join(REPO, g), recursive=True)})
    d = ";".join(defines + (["UNITY_EDITOR"] if editor else []))
    return files, f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <DisableImplicitFrameworkReferences>true</DisableImplicitFrameworkReferences>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <AssemblyName>{name}</AssemblyName>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <DefineConstants>{d}</DefineConstants>
    <OutputPath>bin</OutputPath>
    <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
    <NoWarn>CS0649;CS0169;CS0414;CS1701;CS1702;MSB3277</NoWarn>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>
  </PropertyGroup>
  <ItemGroup>
    {"".join(f'<Compile Include="{f}" />' for f in files)}
  </ItemGroup>
  <ItemGroup>
    {"".join(ref(r) for r in refs)}
  </ItemGroup>
</Project>
"""


def build(variant, defines):
    out = tempfile.mkdtemp(prefix=f"cc-{variant}-")
    ok = True
    for name, sources, pkgs, deps, editor in ASSEMBLIES:
        files, text = csproj(name, sources, pkgs, deps, editor, defines, out)
        if not files:
            continue
        pdir = os.path.join(out, name)
        os.makedirs(pdir)
        with open(os.path.join(pdir, f"{name}.csproj"), "w") as f:
            f.write(text)
        r = subprocess.run(["dotnet", "build", "-nologo", "-v", "q", "-clp:NoSummary"], cwd=pdir,
                           capture_output=True, text=True)
        msgs = [l for l in (r.stdout + r.stderr).splitlines() if ": error " in l or ": warning CS" in l]
        seen = set()
        for m in msgs:
            m = m.replace(REPO + "/", "").split(" [")[0]
            if m not in seen:
                seen.add(m)
                print("  " + m)
        status = "OK" if r.returncode == 0 else "FAILED"
        print(f"[{variant}] {name}: {status} ({len(files)} files)")
        if r.returncode != 0:
            ok = False
            break
    shutil.rmtree(out, ignore_errors=True)
    return ok


if __name__ == "__main__":
    if not ENGINE:
        sys.exit(f"No Unity reference assemblies under {REFS}")
    base = BASE_DEFINES
    good = build("input-system", base + ["ENABLE_INPUT_SYSTEM"])
    good = build("legacy-input", base + ["ENABLE_LEGACY_INPUT_MANAGER"]) and good
    sys.exit(0 if good else 1)
