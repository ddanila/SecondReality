#!/usr/bin/env python3
"""Run and capture the DOS extraction headlessly in DOSBox-X."""
import argparse
from datetime import datetime
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dosbox", default="dosbox-x")
    parser.add_argument("--timeout", type=int, default=300, help="wall-clock limit in seconds")
    parser.add_argument("--no-review",action="store_true",help="Skip automatic Robotron preview/review export")
    args = parser.parse_args()
    emulator = shutil.which(args.dosbox)
    if not emulator:
        raise SystemExit("DOSBox-X not found; pass --dosbox /path/to/dosbox-x")
    dos = HERE / "build/dos"
    if not (dos / "RT1715.EXE").is_file():
        raise SystemExit("Build first: python3 RT1715/build.py")
    capture = HERE / "capture" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    capture.mkdir(parents=True)
    result = dos / "RESULT.TXT"
    result.unlink(missing_ok=True)
    (dos / "CRED.LOG").unlink(missing_ok=True)
    (dos / "FLIGHT.LOG").unlink(missing_ok=True)
    # Branch immediately on the application's return status, before ECHO
    # or other shell commands have a chance to change ERRORLEVEL.
    batch = """@echo off
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
               "-c", "mount c build/dos", "-c", "c:", "-c", "runtest.bat"]
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
               "video_files": [p.name for p in videos], "audio": audio}
    if sync_cues is not None:
        summary["music_cues"] = sync_cues
    (capture / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"PASS: DOS returned successfully; video and non-silent audio captured in {capture}")
    if sync_cues is not None and not args.no_review:
        python=HERE/'build/host-python/bin/python'
        subprocess.run([str(python) if python.exists() else sys.executable,
                        str(HERE/'review.py'),str(capture)],check=True)
    print("Review the generated reel/contact sheet for visual regressions.")


if __name__ == "__main__":
    main()
