Second Reality: RT1715 extraction
================================

Sequence: 3D city flyover -> original end-logo transition -> credit cards ->
music fade and return to DOS. The long ENDSCRL text scroller and all earlier
effects are omitted. All compilation, conversion, and OpenSCAD rendering
run on the HOST. DOSBox-X only executes the finished DOS programs.

Try the editable OpenSCAD/image/ASCII workflow from the repository root:

    python3 -m pip install -r RT1715/requirements.txt
    python3 RT1715/build.py --project RT1715/assets/example.json
    python3 RT1715/run.py

The example replaces two buildings with simple SCAD placeholders, keeps the
drone, renders two credit photos from those same SCAD sources, and builds a
new DOS credits player. It runs for approximately 76 seconds. Inspect host
previews and the conversion report in RT1715/build/prepared/ before running.

No final artwork is needed yet. Copy assets/example.json to your own JSON
file and replace its model paths, card images and text when ready. Paths in
the manifest are relative to the manifest's directory.

Build the original extracted visuals (without customization):

    python3 RT1715/build.py

The baseline needs Python 3, JWasm (OMF output), and Open Watcom wlink.
Customization also needs OpenSCAD CLI, Pillow >=10.1, and Open Watcom wcc
with its DOS headers and libraries. The build searches PATH and the native
toolchain in a sibling msdos checkout. To select tools:

    python3 RT1715/build.py --jwasm /path/to/jwasm --wlink /path/to/wlink

JWASM, WLINK, WCC, OPENSCAD and WATCOM environment variables are accepted.
Additional options: --wcc, --openscad, --watcom-root (installation containing
h/ and lib286/dos/). No compiler, modeler or converter runs in the guest.

Asset manifest (version 1)
--------------------------
Model entries accept:

    {"slot": 2, "scad": "models/tower.scad",
     "color": 64, "shades": 32, "rotate_z": 0}

  slot       Existing U2E mesh number, 1..42. Each may occur only once.
             Slot 28 ("s01", the drone) is protected and cannot be replaced.
  scad       Source OpenSCAD file. include/use dependencies work normally.
  color      First palette index in the existing city palette (default 64).
  shades     Ramp length: 1, 8, 16 or 32 (default 32). Entries 252..255 are
             reserved. Useful existing ramps include 64/32 blue, 128/32 red,
             160/32 orange and 192/32 cyan; inspect the DOS capture.
  rotate_z   Rotation in degrees before fitting (default 0).

SCAD is Z-up. The converter exports binary STL, deduplicates vertices,
generates face normals and eight painter-order lists, and writes native
U2E geometry. It uniformly scales the model to fit the original object's
geometry bounds, centers it in X/Y and puts its bottom on the original Z
floor. This preserves proportions; narrow/short objects leave empty space.
The original object name/slot, camera path and instance transforms stay.
All instances that use a replaced mesh share its replacement.

Find mesh IDs/names/bounds with:

    python3 RT1715/prepare.py --inventory

A custom build also writes build/prepared/scene-inventory.json.

Keep models simple: at most 500 triangles and 491 geometry vertices per
mesh. The whole replacement set is limited to 1000 triangles and a
conservative estimated 64 KiB of additional mesh memory. Use low $fn on
cylinders/spheres and simplify bevels. These checks are not a frame-rate
guarantee; review the full flyover in DOSBox-X after changing geometry.

STL carries geometry, not OpenSCAD materials. Each replacement currently
uses one original palette ramp, with flat shading. It has no textures or
transparency. The original renderer uses painter ordering, not a z-buffer:
interpenetrating/complicated concave geometry may show ordering artifacts.
The eight sort lists use the original converter's farthest-vertex depth
ordering. Changing buildings does not recalculate the flight route.

Credit entries accept either an existing rendered image:

    {"image": "photos/tower.png",
     "lines": ["Model by Alice", "Code by Bob"], "hold_frames": 200}

or a render generated automatically on the host:

    {"render_model": "models/tower.scad",
     "lines": ["RT1715", "OpenSCAD city"], "hold_frames": 200}

  image/render_model  Choose exactly one. Images may be PNG, JPEG or other
                      Pillow-supported formats. Rendered models use the
                      OpenSCAD CLI in offscreen mode, at 960x600.
  lines               1..4 strings; printable ASCII (codes 32..126), up to
                      50 characters per line. Lowercase and punctuation
                      work. Newlines/tabs/control characters are rejected;
                      use separate list entries for separate lines.
  hold_frames         Stable display duration in VGA refresh frames,
                      excluding transitions; 1..4200, default 200 (~3 s).
  camera              Optional list of 6 or 7 OpenSCAD camera parameters,
                      only with render_model. By default viewall/autocenter
                      frame the whole model. These are credit-render camera
                      settings; they do not alter the flyover camera.

The credit image is center-cropped/resized to 160x100 and quantized to 240
colors. Each card has its own palette. The other 16 palette entries are
reserved for grayscale captions. Pillow's bundled scalable font renders
ASCII on the host with no external font dependency; long lines shrink to
fit. Short lines look better. Previews show the final aspect-correct layout.
The DOS player retains the original split-screen/slide transition formulas.

There may be 1..99 cards. Their order is the manifest order. Shortening the
card list shortens the demo: music remains continuous and fades at the end.
Use run.py --timeout 900 (or longer) for a long credit sequence.

Generated CARDxx.CRD files contain a CRD1 header, 768 bytes of 6-bit VGA
palette, a 320x200 caption panel (indices 0..15), and a 160x100 picture
(indices 16..255). CRED.IDX selects cards and hold durations. These files
are build outputs; edit the manifest/source assets instead.

Run and test headlessly:

    python3 RT1715/run.py

This uses DOSBox-X with SDL dummy video AND audio drivers, so no window or
host audio is produced. The emulated sound card still runs and its output
is recorded. AVI, WAV, emulator log, and result.json go into a timestamped
RT1715/capture directory. A run has a 300-second timeout. The runner checks
the DOS exit status and sustained non-silent audio. Review AVI captures to
check visuals. DOSBox-X splits video files when the display mode changes.
No desktop screenshots or UI automation are required.

The original illustrated-card cut runs for approximately 175 seconds.
The two-card example runs for approximately 76 seconds.

The capture command is DOSBox-X's built-in DX-CAPTURE /V /A /-D:
https://dosbox-x.com/wiki/DOSBox%E2%80%90X%E2%80%99s-Supported-Commands

Output and dependencies
-----------------------
build/dos is the self-contained DOS directory. Run RT1715.EXE there with a
386+ CPU, VGA, EMS, and a Sound Blaster Pro at port 220h, IRQ 7, DMA 1.
The supplied DOSBox-X configuration uses a 486, VGA, 16 MB RAM and 60,000
fixed CPU cycles. Setup is fixed, with no menu and no looping.

MAIN/U2.ASM has an optional RT1715 build path. The original full-demo path
remains available when RT1715 is not defined. SETUP.INC supplies the sound
configuration; SEQUENCE.INC selects and orders the three effect programs.
The build translates a few TASM syntax differences into generated
build/RT1715.ASM, assembles it, and links it with the existing STMIK object.

The demo host is rebuilt from source. With --project, credits.c is also
compiled on the host to CRED.EXE, and the selected city meshes are regenerated
by scene.py. The city renderer, end-logo effect and STMIK music player reuse
the original executables/object; none is binary-patched. Without --project,
the original CRED.EXE is used too. Original sources and artwork remain here:

  City:       VISU/C/U2E.C; renderer in VISU/*.ASM and VISU/VISU.C
  City data:  MAIN/DATA/U2E.001 through .042 (geometry), .00M (materials
              and palette), .0AA (animation list), .0AB (animation stream)
  Authoring:  VISU/C/SCENE/U2E.* and 3DS/ (may differ from runtime assets)
  End logo:   END/END.C, END/ASM.ASM, END/PIC.LBM and END/PIC.UH
  Credits:    CREDITS/MAIN.C, CREDITS/TWEAK.ASM, CREDITS/PICS/*.LBM,
              CREDITS/FONA.INC and CREDITS/INCLUDE.ASM / INCLUD2.ASM
  Host/DIS:   MAIN/U2.ASM, MAIN/U2A.ASM, MAIN/COPPER.ASM, DIS/DISINT.ASM
  Music:      MAIN/MUSIC0.S3M; MAIN/STARTMUS.C; MAIN/STMIK.300

The new credit player is RT1715/credits.c. Its VGA implementation and
transitions follow the original CREDITS sources. It loads prepared card data
at runtime, so images/text can change without editing the C source. It logs
each card and successful completion to CRED.LOG. The headless runner checks
that log for custom builds as well as checking DOS exit and recorded audio.
build/assets.json and build/prepared/report.json record source paths,
hashes, counts and the protected assets. U2E.028, .00M and .0AA always
match the originals, preserving drone geometry, palette and scene mapping.
U2E.0AB also stays exact with the default visibility mode (original).

Format and validation tests:

    python3 -m unittest discover -s RT1715 -v

The original renderer's legacy makefiles still require adaptation if we
later change its rendering code. Geometry conversion and new credits do
not require rebuilding that renderer.

Music starts at order 18 (decimal, zero-based) of MUSIC0.S3M. The city
waits for the following order before starting its animation. Music runs
continuously through the logo and credits. REALITY.FC is rebuilt as a
16-byte offset header plus MUSIC0 only; MUSIC1 is not part of this cut.

The repository's root README.md and UNLICENSE contain the public-domain
release terms. Original art, code, and music are by Future Crew.

City visibility preparation
---------------------------
The project may set "visibility": "original" (default) or "static". The
example explicitly selects static. The host rewrites U2E.0AB; the DOS city
executable stays unchanged. Camera records, moving-object records (including
the drone), frame count and FOV values are preserved.

Static mode initializes 51 city object instances at their recovered fixed
poses on the first frame and keeps them enabled throughout. The renderer
still clips and draws them normally. This removes their original baked
visibility restrictions, including when replacement geometry reveals more
of the surroundings. It increases rendering work, so inspect captures for
performance and painter-order artifacts when changing models.

This is not yet unrestricted camera-path editing. Six moving instances
(2, 28, 35, 51, 52, 57; instance IDs, not mesh slots) retain their original
visibility. The exporter omitted motion while objects were hidden; those
missing poses cannot be recovered exactly from U2E.0AB. A new path revealing
those intervals needs source animation or explicitly authored replacement
tracks. Static classification is inferred from constant visible poses; it
cannot prove an object never moved while hidden. This mode is intended for
the supplied city data, not arbitrary animation streams.

animation.py decodes and rewrites the stream on the host. The preparation
report lists the affected instances. Tests compare all retained camera and
moving-object records and all originally visible static poses frame by
frame. A future host visibility bake can reduce work again after geometry,
complete motion tracks and the new camera path are settled.
