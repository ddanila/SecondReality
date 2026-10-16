import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from chapters import DEFAULT, load, require_buildable, verify_logs, cue_sheet
from music import module_archive

ROOT = Path(__file__).resolve().parent.parent


class ChapterTests(unittest.TestCase):
    def logs(self):
        return {'flight': 'SWOOSH frame=1 order=25 row=6\nOVERVIEW order=24 row=54\nEND order=26 row=57\n',
                'credits': 'START order=28 row=0\nEND order=43 row=29\n'}

    def test_flight_only_checks_do_not_require_credits(self):
        logs = {"flight": self.logs()["flight"]}
        self.assertEqual(set(verify_logs(logs, cut="flight")), {"swoosh", "overview", "flight_end"})

    def test_contract_checks_missing_duplicate_and_late_cues(self):
        self.assertEqual(verify_logs(self.logs())['swoosh'], (25, 6))
        for bad in ('', 'START order=28 row=0\nEND order=43 row=46\n',
                    self.logs()['credits'] * 2):
            logs = self.logs(); logs['credits'] = bad
            with self.assertRaises(ValueError):
                verify_logs(logs)

    def test_contract_rejects_unimplemented_cut_and_invalid_positions(self):
        document, _ = require_buildable()
        with self.assertRaises(ValueError):
            require_buildable(cut='expanded')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chapters.json'
            bad = copy.deepcopy(document)
            bad['scenes']['flight']['status'] = 'planned'
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                require_buildable(path)
            bad = copy.deepcopy(document)
            bad['scenes']['flight']['module'] = 'music1'
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                require_buildable(path)
            bad = copy.deepcopy(document)
            bad['cuts']['short']['checks']['swoosh']['target'] = [25, 64]
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                load(path)

    def test_single_module_archive_is_byte_identical(self):
        music = (ROOT/'MAIN/MUSIC0.S3M').read_bytes()
        expected = struct.pack('<II6xH', 16, 16, 0x1B1C) + music
        self.assertEqual(module_archive(music), expected)

    def test_two_modules_preserve_loader_offsets_and_payloads(self):
        a = (ROOT/'MAIN/MUSIC0.S3M').read_bytes()
        b = (ROOT/'MAIN/MUSIC1.S3M').read_bytes()
        archive = module_archive(a, b)
        first, second = struct.unpack_from('<II', archive)
        self.assertEqual(archive[first:second], a)
        self.assertEqual(archive[second:], b)
        with self.assertRaises(ValueError):
            module_archive(b'not a module')

    def test_original_capture_passes_when_available(self):
        capture = ROOT/'RT1715/capture/20261016-111819-127780'
        if not capture.exists():
            self.skipTest('Local playback evidence not installed')
        logs = {scene: (capture/name).read_text() for scene, name in
                [('flight', 'flight.log'), ('credits', 'credits.log')]}
        self.assertEqual(verify_logs(logs)['credits_end'], (43, 29))

    def test_cue_sheet_uses_scene_relative_times(self):
        flight, credits = cue_sheet()
        self.assertAlmostEqual(flight['cue_seconds_from_scene_entry']['swoosh'], 51.6)
        self.assertEqual(credits['cue_seconds_from_scene_entry']['credits_start'], 0)
        self.assertGreater(credits['seconds'], 100)
