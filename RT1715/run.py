#!/usr/bin/env python3
"""Run and capture the DOS extraction headlessly in DOSBox-X."""
import argparse
import hashlib
from datetime import datetime
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time
import wave

HERE = Path(__file__).resolve().parent


def verify_sync(flight_log, credit_log):
    """Check actual tracker positions, including the >64 KB flight regression."""
    def position(log, label):
        match = re.search(r"^"+label+r"[^\n]*order=(\d+) row=(\d+)", log, re.M)
        if not match:
            raise ValueError(f"Missing {label} music cue")
        return tuple(map(int, match.groups()))
    cues = {"swoosh": position(flight_log, "SWOOSH"),
            "overview": position(flight_log, "OVERVIEW"),
            "flight_end": position(flight_log, "END"),
            "credits_start": position(credit_log, "START"),
            "credits_end": position(credit_log, "END")}
    if not ((25, 5) <= cues["swoosh"] <= (25, 8)):
        raise ValueError(f"Drone missed swoosh: {cues['swoosh']}")
    if not ((24, 52) <= cues["overview"] <= (24, 58)):
        raise ValueError(f"Overview missed logo interval: {cues['overview']}")
    if not ((26, 55) <= cues["flight_end"] <= (28, 0)):
        raise ValueError(f"Flyover ended early/late: {cues['flight_end']}")
    if not ((28, 0) <= cues["credits_start"] <= (28, 1)):
        raise ValueError(f"Credits missed theme entry: {cues['credits_start']}")
    return cues


def verify_card_schedule(log, schedule, clock):
    lines=schedule.splitlines();count=int(lines[0]);cues=[list(map(int,line.split())) for line in lines[1:]]
    entries=[tuple(map(int,m)) for m in re.findall(r'^ENTRY order=(\d+) row=(\d+)',log,re.M)]
    if len(entries)!=count or len(cues)!=count:raise ValueError('Missing scheduled credit entries')
    times=struct.unpack('<1024H',clock);errors=[]
    for (order,row),cue in zip(entries,cues):
        if not 28<=order<=43 or not 0<=row<64:raise ValueError('Credit outside tracker interval')
        error=times[(order-28)*64+row]-cue[0]
        if abs(error)>12:raise ValueError(f'Credit missed beat by {error} centiseconds')
        errors.append(error)
    end=re.search(r'^END order=(\d+) row=(\d+)',log,re.M)
    if not end:raise ValueError('Missing credit end')
    order,row=map(int,end.groups())
    if not 28<=order<=43 or abs(times[(order-28)*64+row]-cues[-1][3])>12:
        raise ValueError('Credits changed the original end cue')
    return {'cards':count,'positions':entries,'entry_error_cs':errors,'end':(order,row)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dos-dir",type=Path,default=HERE/"build/dos",help="Isolated runtime directory for comparisons")
    parser.add_argument("--dosbox", default="dosbox-x")
    parser.add_argument("--timeout", type=int, default=300, help="wall-clock limit in seconds")
    parser.add_argument("--no-review",action="store_true",help="Skip automatic Robotron preview/review export")
    parser.add_argument("--color", choices=("ram","direct"), default="ram", help="Protected-mode color backend")
    parser.add_argument("--cycles", type=int, help="Fixed CPU cycles for reproducible comparisons")
    args = parser.parse_args()
    if args.cycles is not None and args.cycles <= 0:
        parser.error("--cycles must be positive")
    emulator = shutil.which(args.dosbox)
    if not emulator:
        raise SystemExit("DOSBox-X not found; pass --dosbox /path/to/dosbox-x")
    dos = args.dos_dir.resolve()
    if not (dos / "RT1715.EXE").is_file():
        raise SystemExit("Build first: python3 RT1715/build.py")
    capture = HERE / "capture" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    capture.mkdir(parents=True)
    (dos/"PM.CFG").write_text(args.color+"\n")
    result = dos / "RESULT.TXT"
    result.unlink(missing_ok=True)
    (dos / "CPU.TXT").unlink(missing_ok=True)
    (dos / "CRED.LOG").unlink(missing_ok=True)
    (dos / "FLIGHT.LOG").unlink(missing_ok=True)
    # Branch immediately on the application's return status, before ECHO
    # or other shell commands have a chance to change ERRORLEVEL.
    batch = """@echo off
config -get cpu cycles > CPU.TXT
set BLASTER=A220 I7 D1 T4
dx-capture /V /A /-D rt1715.exe > demo.log
if errorlevel 1 goto failed
echo PASS > result.txt
goto done
:failed
echo FAIL > result.txt
:done
exit
"""
    (dos / "RUNTEST.BAT").write_bytes(batch.replace("\n", "\r\n").encode("ascii"))
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    command = [emulator, "-conf", "dosbox-x.conf", "-noautoexec", "-fastlaunch",
               "-set", f"dosbox captures={capture}",
               "-c", f'mount c "{dos}"', "-c", "c:", "-c", "runtest.bat"]
    if args.cycles is not None:
        command[1:1] = ["-set", f"cpu cycles=fixed {args.cycles}"]
    print(f"Headless DOSBox-X playback; captures and log: {capture}", flush=True)
    start = time.monotonic()
    with (capture / "dosbox.log").open("w") as log:
        # A separate session keeps Ctrl-C from reaching DOSBox's GUI quit
        # handler. On cancellation/timeout, kill only this owned child.
        process = subprocess.Popen(command, cwd=HERE, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            returncode = process.wait(timeout=args.timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            process.kill()
            process.wait()
            reason = (f"Playback exceeded {args.timeout}s" if isinstance(error, subprocess.TimeoutExpired)
                      else "Playback cancelled")
            raise SystemExit(f"{reason}; inspect {capture / 'dosbox.log'}")
    status = result.read_text().strip() if result.exists() else "NO DOS EXIT STATUS"
    if (dos / "DEMO.LOG").exists():
        shutil.copyfile(dos / "DEMO.LOG", capture / "demo.log")
    if returncode or status != "PASS":
        raise SystemExit(f"Playback failed ({status}); inspect {capture / 'dosbox.log'}")
    if (dos / "CRED.IDX").exists():
        credit_log = dos / "CRED.LOG"
        if not credit_log.exists() or not credit_log.read_text().endswith("COMPLETE\n"):
            raise SystemExit("Custom credits did not complete; inspect build/dos/CRED.LOG")
        shutil.copyfile(credit_log, capture / "credits.log")
    if (dos / "FLIGHT.LOG").exists():
        shutil.copyfile(dos / "FLIGHT.LOG", capture / "flight.log")
    sync_cues = None
    if (dos / "CRED.SYN").exists():
        try:
            sync_cues = verify_sync((capture / "flight.log").read_text(),
                                    (capture / "credits.log").read_text())
        except (OSError, ValueError) as error:
            raise SystemExit(f"Music synchronization failed: {error}")
    card_sync=None
    if (dos/'CRED.CUE').exists():
        card_sync=verify_card_schedule((capture/'credits.log').read_text(),(dos/'CRED.CUE').read_text(),(dos/'CRED.TIM').read_bytes())
    actual_cycles=(dos / "CPU.TXT").read_text().strip()
    if args.cycles is not None and actual_cycles != f"fixed {args.cycles}":
        raise SystemExit(f"DOSBox CPU setting mismatch: {actual_cycles!r}")
    shutil.copyfile(dos / "CPU.TXT", capture / "cpu.txt")
    scene_hash=hashlib.sha256()
    for asset in sorted(dos.glob("U2E.*")):
        if asset.suffix.upper() != ".EXE":
            scene_hash.update(asset.name.encode()+b"\0"+asset.read_bytes())
    # DOS EXEC changes DOSBox's capture prefix to the child program name.
    # Normalize completed segments chronologically for preview/review tools.
    segments=sorted(capture.glob("*.avi"),key=lambda p:p.stat().st_mtime_ns)
    for i,path in enumerate(segments): path.rename(capture/f"segment-{i}.tmp")
    for i in range(len(segments)): (capture/f"segment-{i}.tmp").rename(capture/f"rt1715_{i:03}.avi")
    videos = sorted(capture.glob("*.avi"))
    waves = sorted(capture.glob("*.wav"))
    if not videos or not waves:
        raise SystemExit("Playback returned, but video/audio captures are missing")
    audio = []
    for path in waves:
        with wave.open(str(path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            # DOSBox-X WAV is signed 16-bit PCM. Check for actual sample data.
            audible = False
            while block := wav.readframes(16384):
                audible |= any(block)
            audio.append({"file": path.name, "seconds": duration,
                          "nonzero_samples": audible})
    if not any(item["nonzero_samples"] and item["seconds"] > 30 for item in audio):
        raise SystemExit("Missing sustained audio; inspect captures")
    summary = {"dos_exit": status, "headless": True,
               "wall_seconds": round(time.monotonic() - start, 2),
               "cpu_cycles": actual_cycles,
               "color_backend": args.color,
               "renderer_sha256": hashlib.sha256((dos / "U2E.EXE").read_bytes()).hexdigest(),
               "scene_sha256": scene_hash.hexdigest(),
               "video_files": [p.name for p in videos], "audio": audio}
    flight_text=(capture/"flight.log").read_text() if (capture/"flight.log").exists() else ""
    summary["renderer_mode"]="protected" if flight_text.startswith("PROTECTED ") else "real"
    if summary["renderer_mode"]=="real": summary["color_backend"]="legacy-vga"
    counters=re.search(r"^COUNTERS (.+)$",flight_text,re.M)
    if counters:
        summary["render_counters"]={key:int(value) for key,value in re.findall(r"(\w+)=(\d+)",counters[1])}
    if sync_cues is not None:
        summary["music_cues"] = sync_cues
    if card_sync is not None:summary["credit_schedule"]=card_sync
    (capture / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"PASS: DOS returned successfully; video and non-silent audio captured in {capture}")
    if sync_cues is not None and not args.no_review:
        python=HERE/'build/host-python/bin/python'
        subprocess.run([str(python) if python.exists() else sys.executable,
                        str(HERE/'review.py'),str(capture)],check=True)
    if not args.no_review:
        print("Review the generated reel/contact sheet for visual regressions.")


if __name__ == "__main__":
    main()
