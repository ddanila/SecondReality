Second Reality: RT1715 extraction
================================

The Robotron build is documented under "Robotron 1715M fly-through" below.
It replaces the city and goes directly to component/spec cards.
Robotron now defaults to the 32-bit protected-mode renderer. See "Protected-mode
renderer" below for the additional host compiler setup and benchmark commands.

Original extraction sequence: 3D city flyover -> original end-logo transition -> credit cards ->
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
No desktop screenshots or UI automation are required. The configuration sets
"quit warning = false" and chooses the config directory without prompting.
The runner isolates the emulator session; timeout or Ctrl-C kills and reaps
that child without entering its native confirmation-dialog handler.
DOSBox-X documents this switch at https://dosbox-x.com/wiki/Home .

The original illustrated-card cut runs for approximately 175 seconds.
The two-card example runs for approximately 76 seconds.

The capture command is DOSBox-X's built-in DX-CAPTURE /V /A /-D:
https://dosbox-x.com/wiki/DOSBox%E2%80%90X%E2%80%99s-Supported-Commands

Output and dependencies
-----------------------
build/dos is the self-contained DOS directory. Run RT1715.EXE there with a
386+ CPU, VGA, EMS, and a Sound Blaster Pro at port 220h, IRQ 7, DMA 1.
The supplied DOSBox-X configuration uses a 486, VGA, 32 MB RAM and an adaptive
CPU budget (cycles=max 95%). Setup is fixed, with no menu and no looping.

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
hashes, counts and the protected assets. With --project, U2E.028, .00M
and .0AA match the originals, preserving drone geometry, palette and scene
mapping. The separate --robotron mode replaces the scene mapping/palette.
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

Robotron 1715M fly-through
--------------------------
Use Python 3.11 or newer for the optional Robotron asset tools. From the repo root:

    python3 -m venv RT1715/build/host-python
    RT1715/build/host-python/bin/pip install -r RT1715/requirements-robotron.txt
    RT1715/build/host-python/bin/python RT1715/build.py --robotron
    python3 RT1715/run.py

--robotron defaults to ../3d-models/models/robotron-1715m. Supply another
canonical model directory after the option if needed. Its browser/model.json
and exported STL files must be present; each consumed mesh hash is checked.
The sibling 3d-models and dac repositories are read only. OpenSCAD, mesh
conversion, image rendering, assembly and compilation all run on the host.
Only playback runs in headless DOSBox-X.

This mode replaces the city geometry, scene-instance mapping, palette ramps
and animation stream, retaining the byte-exact drone mesh. robotron_lod.py
contains deliberate exterior panel/frame and dished-keycap LODs in the
canonical assembly coordinates. These replace destructive convex-hull
simplification of perforated thin shells. The curved CRT perimeter meets a
fitted surround and front housing lip. Drive fronts include loading slots,
horizontal door levers, grip ridges, moulding seams and red LED lenses.
Fine vents and internal electronics remain simplified in the realtime LOD;
credit photographs use the detailed canonical model exports.

Key legends come from browser/model.json (including shifted symbols and
arrow keys); blank source legends stay blank. legends.py rasterizes them
with Pillow's bundled font plus compact symbol bitmaps, merges pixel runs,
and converts them to polygons on the dished tops. Each marked key shares one
object with its ink; a small depth bias keeps the marks on the plastic.
Control keys use the blue-grey palette. Marks remain limited by 320-pixel VGA
resolution, especially in the distance.

The Robotron renderer is host-linked with Watcom's signed-char / cdecl ABI
and JWasm. renderer.py rebuilds the player, loader, transforms/projection,
data and DIS interface. painter.c now transforms each object once and feeds
depth.c: a per-pixel, 16-bit reciprocal-depth rasterizer using 128 KB of EMS.
Projected vertices and scanline gradients are cached. VGA planes are selected
once per triangle, and pixel addresses advance incrementally.
Faces no longer depend on centroid sorting for visibility. Near-plane and
screen clipping use consistent edge intersections; the original letterboxed
viewport and drone Gouraud shading are retained. Key legends use a one-unit
depth bias. Finite depth precision still requires care with coplanar surfaces.
The 386 arithmetic kernel uses a signed 64-bit product and hardware division
for bounded 32-bit results in projection, clipping and interpolation.

Robotron meshes omit the obsolete eight precomputed sort lists, reserve slot
28 for the unchanged drone, and share transform scratch buffers. The animation
uses an 8 KB streaming buffer with a host-enforced 4 KB maximum encoded frame.
EMS keeps the depth buffer out of the conventional/upper memory used by models.
DOSBox-X uses a 486 dynamic core, an adaptive 95% CPU budget and 32 MB, headless only.
The adaptive CPU budget compensates for depth testing and finer close-up meshes;
close-ups are still more expensive than overview shots.

assets/robotron/flight.json contains independent camera eye/target and drone
position tracks in canonical millimetres. Time-aware cubic Hermite curves
keep movement continuous through waypoints. A camera waypoint with stop=true
has zero incoming/outgoing velocity, allowing a stationary shot without
spline overshoot. The 2031 samples at 35 Hz cover about 58 seconds: keyboard,
drive fronts, case corner, CRT, complete-machine reveal, then drone return.
The original +X drone nose follows its velocity; banking follows turn rate.
The drone crosses diagonally from lower-left to upper-right near the camera
on the swoosh, retaining forward clearance instead of aiming into the lens.

Synchronization uses MUSIC0 continuously, starting at order 18. music.py
reads its XOR-packed S3M patterns, including speed changes and pattern breaks.
The flyover starts at order 19. Its clock follows the actual DIS order/row,
interpolating with VGA retraces between rows. The swoosh is order 25 rows 6/8
(51.60/51.84 seconds after music start, 47.76/48.00 into the flight). The full
Robotron is fully visible by flight second 45.5, before the swoosh. The camera
holds still through second 49 and the drone continues straight out of view.
The overview occupies the original Future Crew logo interval. The final
frame survives loading CRED.EXE; CRED.SYN gates the first card at order 28,
row 0 (62.40 seconds after music start). Order/row numbers here are decimal.
FLIGHT.LOG and CRED.LOG record the runtime cue positions and are copied into
the capture directory. The loader normalizes each fread buffer so an animation
larger than 64 KB cannot wrap a far-pointer segment window.

The 21 cards restore the original illustrated-credit count and cadence:
102 entry retraces, 200 hold retraces, 59 exit retraces plus upload/loading.
Their nominal animation duration is about 108.5 seconds. Twenty-one distinct
views illustrate the technical pages, including crops of the CPU, RAM banks,
display memories, controllers and connectors. Captions, part selection, camera
angles and focus_chips/focus_parts/focus_component crop settings live
in assets/robotron/credits.json. Reference configuration details are labelled
as such, rather than asserted as verified properties of this specimen.
Images have black backgrounds and a thin white frame. Keyboard photographs
show only the populated narrow controller board; the display-board photograph
shows the component side. Generated SCAD wrappers and PNGs are in
build/robotron. Source provenance and licence notices remain in assets/robotron.

source_geometry.py freshly exports the fascia, drive fronts and case-base
front from the canonical model.scad. It preserves openings and recesses while
quantizing curves to 0.5 mm in X/Z and 0.1 mm in depth; hidden rear faces and
subpixel power-lens texture are simplified. The monitor has a physical 2 mm
horizontal housing joint. Cached source exports are invalidated by SCAD hashes.

build/robotron/report.json records source mesh and SCAD hashes, generated object slots,
instance count and flight settings. build/assets.json records installed DOS
file hashes. The host now propagates a failed Robotron flyover as an error;
run.py also preserves DOS stdout in capture/<timestamp>/demo.log.

Run all conversion/animation tests in the optional environment:

    RT1715/build/host-python/bin/python -m unittest discover -s RT1715 -v

Make a shareable, aspect-correct MP4 after a completed capture:

    python3 RT1715/preview.py RT1715/capture/<timestamp>

This requires ffmpeg and writes build/robotron-preview.mp4 by default. It
joins display-mode segments and uses the continuous captured WAV audio.

Validation includes a complete headless playback, all 21 credit cards,
non-silent audio and runtime music-cue checks. The runner requires the overview
at order 24 before the order-25 swoosh, and credits at order 28 row 0.
Headless normal exit, termination, one-second timeout and Ctrl-C cancellation
were checked; none needs a quit confirmation. Run results and cue logs are
saved alongside each capture. The original illustrated cut's captured WAV
is 174.973 seconds (capture/20261014-110531-710934).

Latest validation: capture/20261014-170328-690943, 29 host tests passing,
21 cards complete, 174.944 seconds captured audio and 175.51 seconds wall time.
Overview 24:56 precedes swoosh 25:8; credits start at 28:0 and end at 43:29.
Reviewed captured keyboard/drive occlusion, monitor joint and wide-before-pass
sequence. All 21 rendered image hashes are distinct; current SCAD hashes match.

Keyboard rendering follow-up: the supporting shell/deck tops are divided into
20 mm panels so one large polygon cannot overwrite an entire bank of keys.
The globally sorted draw pass transforms only each flat-shaded face's vertices
and normal in a contiguous batch, avoiding repeated whole-object transforms.
Fully offscreen faces are rejected before sorting; the shell has an opening
under the deck, so hidden overlapping keyboard skins are not drawn. Gouraud objects retain
the full transform path. The loader uses DOS UMB-first allocation when available
and restores the previous DOS allocation strategy/link state before returning;
DOSBox-X's existing umb=true supplies the extra scene memory.
CPU and CRT-controller cards show their complete boards with the relevant IC
highlighted in amber. The floppy-controller view includes surrounding circuitry.
The current local model identifies the 32 RAM packages as M4164B-12; the cards
follow that corrected source label. These local source updates are consumed
read-only and recorded by content hashes, including uncommitted model updates.

Performance comparison against capture/20261014-170328-690943: RGB frame
hashes over the first 50 seconds show 1019 image changes versus 848 (+20%).
The first 20 seconds, containing the keyboard sweep, improve from 208 to 268
(+29%). These count visible frame updates, not VGA refreshes or a fixed FPS
guarantee. Detailed near views remain more expensive than the wide overview.

Keyboard/diagonal-pass validation: capture/20261014-172653-440061, all 31
host tests pass and all 21 cards complete. Captured audio is 174.930 seconds;
wall time is 176.99 seconds. Overview 24:56, swoosh 25:7, credits 28:0–43:29.
Headless playback exits normally with no confirmation. Reviewed keyboard
closeups/pullback, the diagonal pass and the revised board-context images.

Polish pass: each key mesh now starts with a six-face, eight-vertex coarse cap.
At camera depths beyond 240 mm, painter.c transforms only that envelope and
its six normals; nearer keys use the dished cap and full legends. Both levels
retain the same overall envelope and bounds. This avoids drawing unreadable distant
legends while preserving detailed keys in the foreground.

Eight technical cards have labels and leader lines rendered at the actual
160x100 DOS image resolution. Separate colour-mask renders identify the visible
source component positions using the identical camera and geometry; RAM groups
use corner brackets. Labels are configured by view.annotation in credits.json.
The black background and white picture border remain.

Case, drive-recess and blue-key palette ramps have brighter ambient shades,
retaining the dark seams and original drone/music palette entries. The diagonal
exit now accelerates along its existing line, with its timed position unchanged
at flight second 47.76. The overview still precedes the pass; credits retain the
original card count and retrace cadence.
The earlier painter implementation cached transforms for consecutive face
groups. The current depth renderer transforms each visible object only once.

Polish validation: capture/20261014-174534-351043, 33 host tests pass;
all 21 cards complete, audio 174.930 seconds, wall time 177.11 seconds.
Overview 24:55, swoosh 25:7, credits 28:0–43:29. Compared with the preceding
capture/20261014-172653-440061, the first 20 seconds contain 350 visible image
updates versus 268 (+31%); the first 50 contain 1215 versus 1019 (+19%).
These are RGB frame-change counts, not refresh-rate guarantees. All 96 key
meshes satisfy the native eight-vertex/six-normal coarse-layout contract.
The original drone mesh and protected palette ranges remain byte-identical.

Depth and presentation pass
---------------------------
The camera briefly holds keyboard and drive details, rounds the drive-to-CRT
turn, and pulls back gradually before the original timed overview and swoosh.
Near keycaps have chamfered corners and dishes; distant keys retain the coarse
six-face envelope. The CRT uses a finer 12 by 10 grid, drive latch curves retain
more source detail, and keyboard side boundaries match the deck subdivisions.

Annotated credit close-ups now include a full-board locator inset with an
amber rectangle showing the featured component group. Both images come from
the same source model and camera. Set view.locator=false to omit the inset.
The music, 21-card cadence, black backgrounds and white borders are preserved.

Build, play headlessly, validate music cues, and export review artifacts:

    RT1715/build/host-python/bin/python RT1715/build.py --robotron --review

A normal python3 RT1715/run.py also exports the review after successful Robotron
playback. Use --no-review during quick iterations. Export an existing capture:

    RT1715/build/host-python/bin/python RT1715/review.py RT1715/capture/<timestamp>

ffmpeg and Pillow are required for review export. Outputs include the complete
build/robotron-preview.mp4, a labelled build/robotron-review.mp4 excerpt reel,
and build/robotron-review.png contact sheet. Each capture retains its own reel,
contact sheet and review.json with shot timings and playback validation.
The sheet samples keyboard, drives, CRT, reveal, flyby and technical cards;
inspect the video as well, since a still cannot establish motion quality.

Depth/presentation validation: capture/20261014-182143-295674; 38 host tests
pass. All 21 cards completed headlessly, with normal exit and no confirmation.
Wall time 175.65 seconds; captured audio 175.358 seconds (startup capture length
varies). Overview 24:55, swoosh 25:6, credits 28:0–43:29. Source SCAD hashes and
built asset hashes match; the drone mesh and protected palette are unchanged.
Keyboard, drive fronts, CRT seams, reveal and diagonal flyby were inspected.
The final 29-second review reel and contact sheet were exported successfully.

Depth testing trades speed for correct per-pixel visibility: this capture has
184 visible image updates in its first 20 seconds versus 350 for the preceding
painter build. Camera holds and the adaptive CPU budget also affect this count;
it is not a fixed frame-rate guarantee. Music-position timing remains intact.

Assembly kernels
----------------
fast.asm contains five real-mode 386 routines, host-assembled with JWasm:
- rt_span386: depth-tested VGA plane spans with shading interpolation and a
  saturating decal bias. Interpolants and addresses remain in registers.
- rt_edges386: initializes scanline bounds and walks all three triangle edges
  inside one assembly call, including signed fixed-point slope calculation.
- rt_muldiv: signed IMUL/IDIV with a 64-bit intermediate product, a nonzero
  divisor and a result constrained to signed 32 bits by the renderer.
- rt_clear386: REP STOSD plus byte tails, used to clear EMS depth pages.
- rt_copy386: REP MOVSD plus byte tails, used for animation buffer compaction.
  It supports disjoint buffers or forward overlap (destination before source).

fast.h explicitly declares far stack-cdecl functions; long results return in
DX:AX. This avoids mixing Watcom's register convention with the original C ABI.
All far buffers must remain within their 64 KB segment windows. The original
library's memcpy/memmove already use REP MOVSW and its fills use REP STOSW;
small ordinary copies retain those routines. The generated U2E.MAP and FAST.LST
make the native symbols and emitted instructions inspectable.

C retains scene management, clipping and scanline setup. Fully onscreen faces
bypass clipping, and flat lighting is evaluated once per face. Host tests keep
an independent portable arithmetic/span path. Run the actual assembly tests:

    RT1715/build/host-python/bin/python RT1715/verify_native.py

This host-builds fast_test.c and runs it in an isolated headless DOSBox-X with
fixed 300000 cycles. It checks 2000 signed arithmetic vectors, 200 span cases
(including rejected pixels, shading slopes, decal saturation and EMS-page-edge
addresses), 400 triangle edge cases, and buffer alignment, odd tails, guard
bytes and forward overlap.
Results and a kernel benchmark are saved in build/native-tests/result.json.
The span benchmark processes 10.24 million pixels; timings are emulator-specific.
Bulk operations can fall below the DOS clock resolution; zero ticks do not
establish a throughput improvement. Full-demo captures remain the final check.

Assembly validation: capture/20261014-184149-318314, all 38 host tests and the
native kernel suite pass. The complete headless run exits normally after all
21 cards; wall time 175.89 seconds, captured audio 175.358 seconds. Overview
24:54, swoosh 25:6, credits 28:0–43:29. No confirmation dialogs. Source and
built asset hashes match; the original drone mesh and palette are preserved.

At fixed 300000 cycles, the native span benchmark measured 2197 ms for C and
549 ms for assembly (~4x); edge processing measured 604 vs 385 ms (~1.6x).
Against capture/20261014-182143-295674 under the same adaptive CPU setting,
visible RGB frame updates increased from 184 to 219 in the first 20 seconds
(+19%), and 941 to 1006 in the first 50 seconds (+7%). These full-scene counts
include holds and depend on host load; kernel speedups do not imply the same
whole-demo speedup. The final preview, review reel and contact sheet were
regenerated and the keyboard, drive fronts, CRT and diagonal pass inspected.

Span and lighting follow-up
--------------------------
Constant-color spans now use a dedicated assembly loop that skips Gouraud
interpolation. The C setup stores triangle-invariant span parameters once and
avoids EMS page lookups for empty spans. Gouraud lighting is cached by normal,
shading mode and transformed object; generation wrap clears the cache safely.

Two scanline batching designs were tested and discarded: buffering overhead
removed the expected gain. The retained renderer calls the span kernel directly.
At fixed 300000 cycles, native lighting measured 605 ms direct versus 274 ms
cached for repeated shared normals. Constant-color spans measured 440 ms versus
494 ms for interpolated spans. These are kernel timings, not whole-demo gains.
The suite additionally checks 6000 lighting cases, repeated cache hits, shading
mode changes and generation wrap; all 38 host tests also pass.

For comparable full-demo captures, pin the emulated CPU budget:

    python3 RT1715/run.py --cycles 300000
    python3 RT1715/compare_runs.py BASE_CAPTURE CANDIDATE_CAPTURE --output comparison.json

Playback records the actual DOSBox CPU setting, renderer hash and scene hash.
The comparison rejects mismatched CPU settings or available scene hashes and
counts visible RGB changes in the first 20 and 50 seconds. These include camera
holds and are not refresh rates. Older captures lacking scene hashes report a
null scene match; their assets must be checked separately.

Follow-up validation: capture/20261014-190652-233308 passes full headless playback
and all 21 credit cards, with no confirmation dialogs. Fixed 300000 cycles:
188 versus 181 visible updates in the first 20 seconds (+3.87%), and 949 versus
919 in the first 50 seconds (+3.26%), against capture/20261014-185327-420598.
This is a single-run comparison, not a statistical performance guarantee.
The compact batching experiment reached only 184/940 updates and was removed.
Wall time was 176.68 seconds; captured audio 174.930 seconds. Overview 24:54,
swoosh 25:6, flight end 26:57 and credits 28:0–43:29 satisfy the synchronization
checks. The review contact sheet was inspected and preview/reel regenerated.
All 22 source SCAD hashes match current files; built asset hashes, original
drone and protected palette remain valid. Scene assets were unchanged across
these runs; the baseline predates automatic scene-hash capture metadata.

Protected-mode renderer
-----------------------
The Robotron flyover now uses Open Watcom's native host wcc386 compiler and an
embedded DOS/32A extender. It is still a DOS executable. The resident DIS/STMIK
music player and the credits remain in their existing real-mode implementations.
Tested configuration: DOSBox-X dynamic core, 486 CPU, 32 MB RAM, headless SDL.

The 128 KB depth buffer is contiguous extended memory. Rendering performs no
EMS mappings or DPMI calls. Four planar RAM color buffers are uploaded with
REP MOVSD once per frame, requiring only four VGA plane selections. The direct
VGA alternative remains available for comparison. EMS remains enabled for the
original music subsystem; removing it from the renderer does not remove that
separate dependency.

Vertices are projected once into full-width coordinates, clipping flags and
reciprocal depth. Scanline row origins advance by addition; horizontal offsets
still follow each edge. Flat and Gouraud pixel kernels retain depth testing and
the saturating key-legend decal bias. Shared-normal lighting remains cached.
Original mesh records explicitly retain their 16-bit fields under the 32-bit
compiler. The full animation stream is loaded into RAM before playback.

The original private EXE loader copied the parent's executable path into the
child PSP environment, which prevented a DOS extender from reopening its own
file. The Robotron flyover now uses DOS EXEC. A new DIS service 11 snapshots
tracker order/row and a monotonic retrace counter atomically. The protected
renderer queries it at frame boundaries through DPMI; no real-mode interrupt
callback points into protected code. The scheduler holds when rendering is
faster than the original 35 Hz animation and skips poses when it is slower.
Music continues uninterrupted, and the overview remains on screen for credits.

Host toolchain setup (no compiler runs inside DOS):

    python3 RT1715/setup_pm.py
    RT1715/build/host-python/bin/python RT1715/build.py --robotron

setup_pm.py extracts the official Open Watcom 2026-10-14 snapshot locally into
build/toolchain/watcom. Verified archive SHA-256:
f1dfab2b4ab082fc5a235fc651c1643e23250e490d620057697a9e9aaef02d44
The upstream Current-build URL changes; the script refuses another checksum.
Use --archive /path/to/ow-snapshot.tar.xz to supply the tested archive, or set
WATCOM32 to an existing native distribution containing wcc386, h/, lib386/ and
binw/dos32a.exe. No sibling checkout is modified. Toolchain hashes are written
to build/renderer32/toolchain.json. Upstream tools and DOS/32A licensing:
https://github.com/open-watcom/open-watcom-v2
https://github.com/open-watcom/open-watcom-v2/tree/master/contrib/extender/dos32a

Rebuild only the renderer and launcher against existing prepared assets:

    python3 RT1715/pm_renderer.py

A full Robotron build defaults to --renderer protected. --renderer real retains
the previous 16-bit renderer for regression comparisons. The original city and
example-project builds retain their existing renderer behavior.

Validation and comparison:

    python3 RT1715/verify_pm.py
    RT1715/build/host-python/bin/python -m unittest discover -s RT1715 -q
    python3 RT1715/run.py --cycles 300000 --color ram
    python3 RT1715/run.py --cycles 300000 --color direct --no-review
    python3 RT1715/compare_runs.py BASE_CAPTURE CANDIDATE_CAPTURE

--dos-dir selects an isolated complete runtime directory for archived baselines.
run.py normalizes DOSBox's child-process capture filenames into chronological
segments before exporting previews. Runtime metadata records the renderer mode,
color backend, source-scene and executable hashes, CPU setting, music cues and
frame/vertex/triangle/span/clipping counters. Counters are not refresh FPS.

The protected-mode native suite checks 2000 signed multiply/divides, 2000 wide
dot products, 800 spans, 128 matrix/normal cases, full-width projection, 258
uploads with guards and byte tails, and 160 complete clipped raster images
against the scalar host backend. The 38 host tests and the legacy native kernel
suite also pass. The native raster comparison covers flat/smooth interpolation,
decals, viewport clipping and unchanged pixels outside the letterbox.

Protected-mode validation (fixed 300000 cycles, unchanged scene assets):

  Renderer                  First 20s updates   First 50s updates
  Legacy, run 1                       188                 949
  Legacy, repeat                      188                 949
  Protected RAM, run 1                353                1355
  Protected RAM, repeat               353                1355
  Protected direct VGA                343                1345

The repeated RAM result is +87.77% / +42.78% versus legacy. Direct VGA is
slightly slower on this DOSBox-X configuration, so RAM is the default. These
are visible RGB frame-change counts, not monitor refresh FPS or a guarantee
of the same speedup on physical hardware. No simultaneous full-demo benchmarks
were run. The completed protected flight renders 1806 frames; counters confirm
zero renderer EMS mappings. Its data segment was observed above 1 MB.

Final capture: capture/20261014-193700-188192. All 21 credits complete with a
normal DOS exit and no confirmation dialog. Wall time 175.18 seconds, captured
audio 174.930 seconds. Overview 24:54, swoosh 25:6, flight end 26:57, credits
28:0–43:29. The first RAM and direct-VGA captures pass the same cue checks.
The final preview, review reel and contact sheet were regenerated. Keyboard,
drive fronts, monitor joint, full reveal, diagonal flyby and technical credit
images were inspected. Original drone, protected palette and MUSIC0 are intact.

Detailed measurements and toolchain hashes are recorded in
benchmarks/protected-mode.json. Scene geometry was held fixed throughout these
renderer comparisons. The sibling 3d-models checkout received concurrent edits
to the interior/PCB sources during validation; those in-progress edits were not
imported into this renderer upgrade. A later full --robotron build will prepare
assets from the then-current source models.

Uncapped renderer benchmark and subsequent kernels
-------------------------------------------------
Measure actual rendering cost independently of music/retrace pacing:

    python3 RT1715/benchmark.py --label candidate
    python3 RT1715/benchmark.py --label repeat --reference PATH/result.json

Each run copies the current U2E runtime into build/pose-benchmarks, decodes six
fixed camera poses, then times 120 renders per pose, including VGA uploads.
Asset loading, animation decoding, warm-up and color hashing are untimed.
Counters include the warm-up (121 renders); timings include only 120 renders.
The DOS clock advances in roughly 55 ms steps, so small differences should not
be treated as precise. References must use identical scene assets and CPU
settings; the tool rejects any changed pose image checksum. Run performance
measurements sequentially. No music player is needed for this benchmark.

Implemented in measured order: benchmark, whole-triangle assembly traversal,
conservative object bounds rejection, fused assembly transform/projection.
The triangle kernel keeps edge walks, row setup, VGA planes and pixels in one
assembly call. Bounds include all original vertices and use wide intermediate
arithmetic plus a pixel margin. Near-plane clipping remains in the raster path.
The fused loop retains camera-space coordinates for clipping/backface tests,
full-width projection, signed matrix truncation and 64-bit dot products.
Normal rotation now happens only after an object passes projection rejection.
The original scalar stages remain available to native verification.

Fixed 300000 cycles, milliseconds per render (same six image hashes):

  Pose          Baseline   Triangles    +Bounds     +Fused
   420            41.650      29.300     28.842     27.467
   980            27.008      19.683     19.683     18.308
  1840            18.308      14.650     14.192     13.733
  2660            10.075       7.325      6.408      6.408
  3200            18.767      16.933     17.392     16.475
  3750            18.308      16.475     16.933     16.017

Final reduction: 12–36% per pose versus the starting protected renderer.
Bounds help close passes most; their small overhead remains in the overview.
These are emulator measurements, not promised physical-hardware speedups.
Detailed stage hashes, counters and measurements: benchmarks/renderer-kernels.json.
Native verification additionally compares 40000 randomized fused vertices with
the separate transform/project pipeline and checks 2000 conservative bounds.
Prepared model assets are unchanged by this optimization.

Full playback validation: capture/20261014-204840-907867, fixed 300000 cycles.
1902 rendered flight frames; visible RGB updates rise from 353 to 448 in the
first 20 seconds (+26.91%) and 1355 to 1452 in the first 50 seconds (+7.16%).
All 21 credit cards complete, with normal DOS exit and no confirmation dialog.
Overview 24:54, swoosh 25:6, flight end 26:57, credits 28:0–43:29 are unchanged.
Original drone, protected palette entries and complete MUSIC0 payload match.
The preview/review artifacts were regenerated and visually checked. Both native
kernel suites and all 38 host tests pass.

Viewport traffic and triangle setup follow-up
--------------------------------------------
The flyover clears and uploads only rows 25..174 after page initialization.
That cuts routine depth clearing, color clearing and VGA upload bytes by 25%.
RAM borders and all four VGA pages are initialized explicitly; changing the
viewport invalidates their cached borders. Direct VGA retains the same rules.
Objects rejected by bounds now leave the pipeline before distance calculation
and sorting. Gradient divisions and row origins run inside the triangle
assembly call, with exact signed rounding and 64-bit scaled numerators.

Two additional experiments were implemented and measured: spatial keyboard
batches and depth storage in VGA-plane order. Keyboard grouping showed no
clear gain at the timer's resolution, so the additional grouping code was not
retained. Planar depth passed the raster checks but was not retained: its
mixed timing changes did not establish an overall improvement in DOSBox-X.
These experiments do not establish performance on a physical CPU/cache.

For repeatable comparisons, benchmark.py now accepts --samples and --dos-dir:

    python3 RT1715/benchmark.py --label repeat --samples 5
    python3 RT1715/benchmark.py --label old --samples 5 --dos-dir ARCHIVED_RUNTIME

Each sample launches the same isolated runtime; timings/counters are summed
and raw per-sample tick measurements are preserved. Reference comparisons
normalize for sample count. Five samples give 600 timed renders per pose,
plus five untimed warm-ups. Repetition checks repeatability, but the roughly
55 ms clock quantization still limits small per-pose speed claims.

The native suite now exercises all four VGA pages, repeated clears, changing
viewports, RAM/direct rendering and eight complete direct-VGA raster images.
It compares both the C and assembly triangle paths on 160 complete images,
including full-range reciprocal depth. The original scene image checksums
remain unchanged. Stage measurements: benchmarks/renderer-followup.json.

Five-sample comparison at fixed 300000 cycles (milliseconds per render):

  Pose          Starting renderer     Retained final
   420                     27.463             27.467
   980                     18.308             18.308
  1840                     13.732             13.272
  2660                      6.408              5.952
  3200                     16.477             16.020
  3750                     16.018             16.018

Three views improve by about 3–7%; the other three are effectively unchanged.
Total measured time over these equally repeated poses decreases about 1.4%.
This is a modest follow-up gain, separate from the earlier renderer upgrade.
Both baseline and final runs use identical assets and produce the same six
image checksums, triangle counts and span counts. The planar-depth experiment
was about 0.5% slower in aggregate than the retained version; neither that
small difference nor timer-quantized ties justify keeping the layout change.

Completed playback: capture/20261014-213333-188258, fixed 300000 cycles.
All 21 cards and music cues pass, with normal exit and no confirmation dialog.
Overview 24:54, swoosh 25:6, flight end 26:57, credits 28:0–43:29 are unchanged.
1904 flight frames render; visible updates are 451/1454 in the first 20/50s,
versus 448/1452 before this follow-up. Both native suites and all 38 host tests
pass. The regenerated contact sheet and flyby strip were visually reviewed.
Original drone, protected palette entries and MUSIC0 payload are byte-exact.

Presentation pass: motion, materials, credits and asset editing
--------------------------------------------------------------
The presentation now has one validated entry point:
assets/robotron/presentation.json. See assets/robotron/EDITING.txt for model,
photo, SCAD-render, ASCII-text, material and motion replacement instructions.

Camera holds let key legends, drive mouths and the monitor seam register.
The drone retains its exact tangent-facing nose and musical flyby anchors;
continuous-acceleration motion and smoothed, restrained banking refine its turns.
Robotron palette ramps distinguish paint, metal and recesses. Curved CRT glass
uses smooth normals, a glow floor and a broad view-dependent sheen. Its geometry
and shared bezel boundary remain unchanged, and drone palette slots are protected.

The 21 technical cards now introduce the workstation, then explain individual
components with shorter, hierarchical captions and specific annotated views.
Focused cards carry board/part locators. The controller keyboard PCB remains the
narrow assembly. Reference configuration facts remain labelled as references.
The latest source snapshot and per-input hashes are kept locally for provenance.

The final overview fades into black before the first card. Card entrances now
follow authored tracker beats, with eased movement and palette fades. Live cue
scheduling preserves the 28:0 start and original 43:29 end instead of accumulating
fixed-frame holds. Generic editable projects without CRED.CUE retain their old
transition behavior. Playback validates all scheduled card entries automatically.

Validated with 43 host tests, both native renderer suites and full headless
DOSBox-X playback at fixed 300000 cycles (capture/20261014-220008-548049).
All 21 entrances land on their scheduled tracker rows with zero measured cue
error; overview 24:54, swoosh 25:6 and credits 28:0-43:29 remain intact.
Playback exits normally without confirmation. Original drone data, protected
palette slots and music payload remain byte-exact. The final review contact
sheet was visually inspected. Results: benchmarks/presentation.json.
