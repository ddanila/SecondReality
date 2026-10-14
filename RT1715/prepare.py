#!/usr/bin/env python3
"""Host-only OpenSCAD / image / ASCII conversion for the original DOS demo."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

import scene

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "MAIN/DATA"


def printable(lines):
    if not isinstance(lines, list) or not 1 <= len(lines) <= 4:
        raise ValueError("Each card needs 1..4 ASCII lines")
    for line in lines:
        if not isinstance(line, str) or len(line)>50 or any(not 32<=ord(c)<=126 for c in line):
            raise ValueError("Credit lines must be printable ASCII, at most 50 characters each")


def load_project(path):
    config = json.loads(path.read_text())
    if not isinstance(config,dict) or config.get("version") != 1 or set(config) - {"version", "models", "credits"}:
        raise ValueError("Expected project version 1 with models and credits")
    models, cards = config.get("models", []), config.get("credits", [])
    if not isinstance(models, list) or not isinstance(cards, list) or not 1 <= len(cards) <= 99:
        raise ValueError("Expected a models list and 1..99 credit cards")
    config["models"] = models
    slots = set()
    for model in models:
        if not isinstance(model,dict) or set(model) - {"slot", "scad", "color", "shades", "rotate_z"}:
            raise ValueError("Unknown model option")
        slot = model.get("slot")
        if type(slot) is not int or not 1 <= slot <= 42 or slot in slots:
            raise ValueError("Model slots must be unique integers in 1..42")
        if slot == scene.DRONE_SLOT:
            raise ValueError("Slot 28 (s01) is the protected drone")
        slots.add(slot)
        if not isinstance(model.get("scad"), str) or not model["scad"].lower().endswith(".scad"):
            raise ValueError("Model source must be an OpenSCAD .scad file")
        angle = model.get("rotate_z", 0)
        if not isinstance(angle, (int, float)) or not math.isfinite(angle):
            raise ValueError("rotate_z must be a finite number of degrees")
        color, shades = model.get("color",64), model.get("shades",32)
        if type(color) is not int or type(shades) is not int or shades not in (1,8,16,32) or not 0<=color<252 or color+shades>252:
            raise ValueError("Invalid palette ramp: use 1/8/16/32 shades within indices 0..251")
    for card in cards:
        if not isinstance(card,dict) or set(card) - {"image", "render_model", "lines", "hold_frames", "camera"}:
            raise ValueError("Unknown credit-card option")
        if ("image" in card) == ("render_model" in card):
            raise ValueError("Each card needs exactly one of image or render_model")
        if "render_model" in card and (not isinstance(card["render_model"],str) or
                                       not card["render_model"].lower().endswith(".scad")):
            raise ValueError("render_model must name an OpenSCAD .scad file")
        printable(card.get("lines"))
        hold = card.get("hold_frames", 200)
        if type(hold) is not int or not 1 <= hold <= 4200:
            raise ValueError("hold_frames must be an integer in 1..4200")
        if "camera" in card:
            camera = card["camera"]
            if "render_model" not in card or not isinstance(camera, list) or len(camera) not in (6,7) or any(
                    not isinstance(x,(int,float)) or not math.isfinite(x) for x in camera):
                raise ValueError("camera must have 6 or 7 finite OpenSCAD camera parameters")
    # Validate every input before invoking tools or changing runtime assets.
    for item in models + cards:
        for key in ("scad", "image", "render_model"):
            if key in item:
                if not isinstance(item[key], str) or not (path.parent / item[key]).is_file():
                    raise ValueError(f"Missing input {key}: {item[key]!r}")
    return config


def openscad(command, source, target, extra):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    subprocess.run([command, "--hardwarnings", "-o", str(target), *extra, str(source)],
                   env=env, check=True, timeout=180)


def make_card(image_path, lines, output, preview):
    printable(lines)
    with Image.open(image_path) as original:
        image = ImageOps.fit(original.convert("RGB"), (160,100), method=Image.Resampling.LANCZOS)
    indexed = image.quantize(colors=240, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.FLOYDSTEINBERG)
    colors = (indexed.getpalette() or [])[:720]
    colors += [0] * (720-len(colors))
    rgb = [v for i in range(16) for v in (i*17,)*3] + colors
    pixels = bytes(p+16 for p in indexed.tobytes())
    text = Image.new("L", (320,200))
    for n, line in enumerate(lines):
        # Pillow's bundled scalable font covers printable ASCII. Rasterize at
        # final resolution into 16 grayscale entries: no host font dependency.
        for size in range(28,5,-1):
            font = ImageFont.load_default(size=size)
            bbox = font.getbbox(line or " ")
            if bbox[2]-bbox[0] <= 312 and bbox[3]-bbox[1] <= 32:
                break
        bbox = font.getbbox(line or " ")
        glyph = Image.new("L", (max(1,bbox[2]-bbox[0]),max(1,bbox[3]-bbox[1])))
        ImageDraw.Draw(glyph).text((-bbox[0],-bbox[1]), line, font=font, fill=255)
        if glyph.width > 312:
            raise ValueError("Credit line does not fit the 320-pixel text panel")
        text.paste(glyph, ((320-glyph.width)//2, 16+n*42))
    caption = bytes(round(v*15/255) for v in text.tobytes())
    output.write_bytes(b"CRD1" + bytes(round(v*63/255) for v in rgb) + caption + pixels)
    # Readable host preview of the stable composition; animation stays in DOS.
    picture = Image.frombytes("P", (160,100), pixels)
    picture.putpalette(rgb)
    composition = Image.new("RGB",(640,480))
    composition.paste(picture.convert("RGB").resize((320,240),Image.Resampling.NEAREST),(160,0))
    composition.paste(text.convert("RGB").resize((640,240),Image.Resampling.NEAREST),(0,240))
    composition.save(preview)


def prepare(project, build, dos, command="openscad"):
    project = Path(project).resolve()
    config = load_project(project)
    output = build / "prepared"
    output.mkdir(parents=True,exist_ok=True)
    needs_scad = config["models"] or any("render_model" in c for c in config["credits"])
    if needs_scad and not shutil.which(command):
        raise ValueError("OpenSCAD CLI not found; set --openscad")
    report = {"project": str(project), "models": [], "credits": [], "protected": {}}
    (output / "scene-inventory.json").write_text(json.dumps(scene.inventory(ORIGINAL),indent=2)+"\n")
    total_faces, extra_memory = 0, 0
    for model in config["models"]:
        slot = model["slot"]
        source = project.parent / model["scad"]
        stl = output / f"slot{slot:03}.stl"
        openscad(command, source, stl, ["--export-format", "binstl"])
        original = scene.decode((ORIGINAL/f"U2E.{slot:03}").read_bytes())
        triangles = scene.fit_mesh(scene.read_stl(stl),original["bounds"],model.get("rotate_z",0))
        mesh = scene.encode(original["name"],triangles,model.get("color",64),model.get("shades",32))
        decoded = scene.decode(mesh)
        # Each vertex also needs transformed and projected runtime arrays.
        extra_memory += max(0,len(mesh)-(ORIGINAL/f"U2E.{slot:03}").stat().st_size)
        extra_memory += max(0,len(decoded["vertices"])-len(original["vertices"]))*32
        extra_memory += len(triangles)*16
        total_faces += len(triangles)
        if total_faces > 1000 or extra_memory > 64000:
            raise ValueError("Replacement set exceeds conservative DOS budget (1000 triangles / 64 KiB growth)")
        name = f"U2E.{slot:03}"
        (output / name).write_bytes(mesh)
        report["models"].append({"slot":slot,"name":original["name"],"source":str(source),
                                  "triangles":len(triangles),"bounds":decoded["bounds"],
                                  "sha256":hashlib.sha256(mesh).hexdigest()})
    index = [f"RT1715 {len(config['credits'])}"]
    for n, card in enumerate(config["credits"],1):
        if "render_model" in card:
            source = project.parent / card["render_model"]
            image_path = output / f"render{n:02}.png"
            options = ["--imgsize", "960,600", "--render"]
            if "camera" in card:
                options += ["--camera", ",".join(str(v) for v in card["camera"])]
            else:
                options += ["--viewall", "--autocenter"]
            openscad(command,source,image_path,options)
        else:
            image_path = project.parent / card["image"]
        name = f"CARD{n:02}.CRD"
        make_card(image_path,card["lines"],output/name,output/f"card{n:02}-preview.png")
        index.append(f"{name} {card.get('hold_frames',200)}")
        report["credits"].append({"file":name,"lines":card["lines"],
                                   "image":str(image_path),"hold_frames":card.get("hold_frames",200)})
    (output/"CRED.IDX").write_bytes(("\r\n".join(index)+"\r\n").encode("ascii"))
    # Only install a fully prepared set. The drone and all animation stay exact.
    names = [f"U2E.{m['slot']:03}" for m in config["models"]]
    names += [c["file"] for c in report["credits"]]+["CRED.IDX"]
    for name in names:
        shutil.copyfile(output/name,dos/name)
    for name in ("U2E.028","U2E.00M","U2E.0AA","U2E.0AB"):
        data = (dos/name).read_bytes()
        if data != (ORIGINAL/name).read_bytes():
            raise ValueError(f"Protected asset changed: {name}")
        report["protected"][name] = hashlib.sha256(data).hexdigest()
    (output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true",required=True)
    parser.parse_args()
    print(json.dumps(scene.inventory(ORIGINAL),indent=2))
