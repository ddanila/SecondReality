#!/usr/bin/env python3
"""Build the extracted DOS sequence using JWasm and Open Watcom's wlink.

Without --project, the original effects are reused from checked-in binaries.
With --project, host tools convert SCAD/images/text and rebuild DOS credits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def expand(path):
    """Flatten DOS includes, resolving their case on case-sensitive hosts too."""
    source = path.read_text(encoding="cp437")

    def include(match):
        child = path.parent
        for part in match[1].replace("\\", "/").split("/"):
            if part == "..":
                child = child.parent
            else:
                child = next(p for p in child.iterdir() if p.name.upper() == part.upper())
        return expand(child)

    return re.sub(r"^\s*include\s+([^\s;]+).*$", include, source, flags=re.M | re.I)


def masm_source(custom=False, robotron=False):
    """Translate the few TASM dialect differences without changing algorithms."""
    source = expand(ROOT / "MAIN/U2.ASM")
    source = re.sub(r"^\s*LOCALS\s*$", "", source, flags=re.M | re.I)
    source = source.replace("@@fjmp:\tdb", "@@fjmp LABEL BYTE\n\tdb")
    # Stray non-ASCII characters before STI in the released COPPER.ASM.
    source = source.replace("åå\tsti", "\tsti")
    source = source.replace("call\tcs:[si]", "call\tword ptr cs:[si]")
    # TASM allows global entry labels inside PROCs. Preserve those while
    # explicitly scoping @@ labels (JWasm otherwise hides the entry labels).
    lines = ["OPTION NOSCOPED", "RT1715=1"]
    if robotron:
        lines.append("RT_ROBOTRON=1")
    if custom:
        lines.append("RT_CUSTOM_CREDITS=1")
    scope = "global"
    for line in source.splitlines():
        proc = re.match(r"(\w+)\s+PROC\b", line, re.I)
        if proc:
            scope = proc[1]
        line = re.sub(r"@@(\w+)", lambda m: "local_" + scope + "_" + m[1], line)
        lines.append(line)
        if re.match(r"\w+\s+ENDP\b", line, re.I):
            scope = "global"
    return "\n".join(lines) + "\n"


def tool(value):
    found = shutil.which(value)
    # Reuse the native toolchain in a sibling msdos checkout when available.
    host = {("Darwin", "arm64"): "macos-arm64",
            ("Linux", "x86_64"): "linux-x64"}.get((platform.system(), platform.machine()))
    if not found and host and value in ("jwasm", "wlink", "wcc"):
        base = ROOT.parent / "msdos"
        candidate = (base / "jwasm" / host / value if value == "jwasm"
                     else base / "watcom/bin" / host / value)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            found = str(candidate)
    if not found:
        raise SystemExit(f"Tool not found: {value}. Select its path with the corresponding build option.")
    return str(Path(found).resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jwasm", default=os.environ.get("JWASM", "jwasm"))
    parser.add_argument("--wlink", default=os.environ.get("WLINK", "wlink"))
    parser.add_argument("--project", type=Path, help="OpenSCAD/image/ASCII asset manifest")
    parser.add_argument("--openscad", default=os.environ.get("OPENSCAD", "openscad"))
    parser.add_argument("--wcc", default=os.environ.get("WCC", "wcc"))
    parser.add_argument("--watcom-root", type=Path, default=os.environ.get("WATCOM"),
                        help="Watcom installation with h/ and lib286/dos/")
    parser.add_argument("--robotron", type=Path, nargs="?",
                        const=ROOT.parent/"3d-models/models/robotron-1715m",
                        help="Build Robotron fly-through from canonical model exports")
    args = parser.parse_args()
    if args.robotron and args.project:
        parser.error("Choose --robotron or --project")
    assembler, linker = tool(args.jwasm), tool(args.wlink)
    build = HERE / "build"
    dos = build / "dos"
    dos.mkdir(parents=True, exist_ok=True)
    (HERE / "capture").mkdir(exist_ok=True)
    if args.robotron:
        from robotron import prepare as prepare_robotron
        args.project = prepare_robotron(args.robotron, build, args.openscad)
    if args.project:
        from prepare import load_project
        load_project(args.project.resolve())
    (build / "RT1715.ASM").write_text(masm_source(bool(args.project), bool(args.robotron)), encoding="cp437")
    subprocess.run([assembler, "-q", "-Cp", "-omf", "-FoRT1715.OBJ", "RT1715.ASM"],
                   cwd=build, check=True)
    shutil.copyfile(ROOT / "MAIN/STMIK.300", build / "STMIK.OBJ")
    subprocess.run([linker, "format", "dos", "option", "quiet", "option",
                    "map=RT1715.MAP", "name", "dos/RT1715.EXE", "file",
                    "RT1715.OBJ", "file", "STMIK.OBJ"], cwd=build, check=True)

    # Use the runtime assets that accompany the released demo, rather than
    # potentially different intermediate files in VISU/C/SCENE.
    assets = ["STARTMUS.EXE", "U2E.EXE", "ENDLOGO.EXE", "CRED.EXE",
              "U2E.00M", "U2E.0AA", "U2E.0AB"]
    assets += [f"U2E.{n:03}" for n in range(1, 43)]
    manifest = []
    for name in assets:
        original = ROOT / "MAIN/DATA" / name
        shutil.copyfile(original, dos / name)
        manifest.append({"file": name, "source": str(original.relative_to(ROOT)),
                         "sha256": hashlib.sha256(original.read_bytes()).hexdigest()})

    # STARTMUS loads module 0 through a little-endian offset in REALITY.FC.
    # Both slots point to the same module: MUSIC1 is not needed by this cut.
    music = (ROOT / "MAIN/MUSIC0.S3M").read_bytes()
    (dos / "REALITY.FC").write_bytes(struct.pack("<II6xH", 16, 16, 0x1B1C) + music)
    manifest.append({"file": "REALITY.FC", "source": "MAIN/MUSIC0.S3M",
                     "module_sha256": hashlib.sha256(music).hexdigest(),
                     "module_offset": 16, "start_order": 18})
    # These are generated files owned by this build, not source assets.
    for old in [dos / "CRED.IDX", dos / "CRED.LOG", *dos.glob("CARD??.CRD")]:
        old.unlink(missing_ok=True)
    if args.project:
        from prepare import prepare
        compiler = tool(args.wcc)
        watcom = args.watcom_root or Path(compiler).parents[2]
        watcom = watcom.resolve()
        if not (watcom / "h/stdio.h").is_file() or not (watcom / "lib286/dos/clibl.lib").is_file():
            raise SystemExit("Set --watcom-root to an installation containing h/ and lib286/dos/")
        report = prepare(args.project, build, dos, args.openscad)
        subprocess.run([compiler, "-zq", "-bt=dos", "-ml", "-3", "-os", "-s",
                        f"-i={watcom / 'h'}", "-fo=CRED.OBJ", str(HERE / "credits.c")],
                       cwd=build, check=True)
        subprocess.run([linker, "format", "dos", "option", "quiet", "option", "stack=4096",
                        "option", "map=CRED.MAP", "name", "dos/CRED.EXE", "file", "CRED.OBJ",
                        "libpath", str(watcom / "lib286/dos"),
                        "libpath", str(watcom / "lib286")], cwd=build, check=True)
        if args.robotron:
            from robotron import install
            install(build, dos)
        for item in manifest:
            path = dos / item["file"]
            if "sha256" in item and hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                item["original_sha256"] = item.pop("sha256")
                item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                item["source"] = "RT1715/credits.c" if path.suffix == ".EXE" else str(args.project)
        for name in ["CRED.IDX", *[card["file"] for card in report["credits"]]]:
            manifest.append({"file":name,"source":str(args.project),
                             "sha256":hashlib.sha256((dos/name).read_bytes()).hexdigest()})
    (build / "assets.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {dos / 'RT1715.EXE'} ({'custom assets' if args.project else 'original assets'} + MUSIC0)")


if __name__ == "__main__":
    main()
