import tempfile
import unittest

from pathlib import Path

from dk64_lib.texture_analysis import (
    TextureTableEntry,
    analyze_rom_textures,
    analyze_texture_entry,
    export_texture_analysis_review,
    load_texture_reference_labels,
    results_to_csv,
    results_to_json,
)


class TextureAnalysisTest(unittest.TestCase):
    def test_review_export_writes_status_sorted_pngs_and_reports(self):
        class FakeRom:
            pass

        def generate_rom_table_data(tables):
            self.assertEqual(tables, [7])
            yield {"offset": 0x1234, "raw_data": b"\xff\xff" * 1024}

        fake_rom = FakeRom()
        fake_rom.generate_rom_table_data = generate_rom_table_data

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            written_paths = export_texture_analysis_review(
                fake_rom,
                root,
                tables=(7,),
                clear=True,
            )
            png_paths = list((root / "likely_ok" / "table_07").glob("*.png"))

            self.assertIn(root / "texture_analysis.json", written_paths)
            self.assertIn(root / "texture_analysis.csv", written_paths)
            self.assertIn(root / "README.txt", written_paths)
            self.assertEqual(len(png_paths), 1)
            self.assertTrue(png_paths[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(png_paths[0].name.startswith("000000_offset_00001234_"))

    def test_review_export_skips_referenced_entries_by_default(self):
        class FakeRom:
            pass

        def generate_rom_table_data(tables):
            self.assertEqual(tables, [7])
            yield {"offset": 0x1234, "raw_data": b"\xff\xff" * 1024}

        fake_rom = FakeRom()
        fake_rom.generate_rom_table_data = generate_rom_table_data

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            reference = (
                root
                / "proper_textures"
                / "table_07"
                / "000000_offset_00001234_guess_f0_s2_32x32.png"
            )
            reference.parent.mkdir(parents=True, exist_ok=True)
            reference.write_bytes(b"png")

            export_texture_analysis_review(
                fake_rom,
                root / "review",
                tables=(7,),
                reference_root=root,
            )
            self.assertEqual(list((root / "review").rglob("*.png")), [])

            export_texture_analysis_review(
                fake_rom,
                root / "review_with_refs",
                tables=(7,),
                reference_root=root,
                include_referenced=True,
            )
            self.assertEqual(len(list((root / "review_with_refs").rglob("*.png"))), 1)

    def test_reference_root_calibrates_similar_unlabeled_entries(self):
        class FakeRom:
            pass

        raw_entries = (
            b"\xff\xff" * 1024,
            bytes(range(256)) * 8,
            bytes(range(255, -1, -1)) * 8,
            bytes(range(128)) * 16,
        )

        def generate_rom_table_data(tables):
            for index, raw_data in enumerate(raw_entries):
                yield {"offset": index, "raw_data": raw_data}

        fake_rom = FakeRom()
        fake_rom.generate_rom_table_data = generate_rom_table_data

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            reference_paths = (
                root
                / "proper_textures"
                / "table_07"
                / "000000_offset_00000000_guess_f0_s2_32x32.png",
                root
                / "broken_textures"
                / "table_07"
                / "wrong_format"
                / "000001_offset_00000001_guess_f0_s2_32x32.png",
                root
                / "broken_textures"
                / "table_07"
                / "wrong_format"
                / "000002_offset_00000002_guess_f0_s2_32x32.png",
            )
            for path in reference_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"png")

            results = analyze_rom_textures(
                fake_rom,
                tables=(7,),
                reference_root=root,
            )

        unlabeled_result = results[3]
        self.assertEqual(unlabeled_result.reference_prediction.label, "wrong_format")
        self.assertEqual(unlabeled_result.status, "format_ambiguous")

    def test_reference_labels_ignore_table25_proper_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            proper_7 = (
                root
                / "proper_textures"
                / "table_07"
                / "000000_offset_00000000_guess_f0_s2_32x32.png"
            )
            proper_25 = (
                root
                / "proper_textures"
                / "table_25"
                / "000001_offset_00000001_guess_f0_s2_32x32.png"
            )
            mipmap_25 = (
                root
                / "broken_textures"
                / "table_25"
                / "mipmap"
                / "000002_offset_00000002_guess_f0_s2_32x64.png"
            )
            for path in (proper_7, proper_25, mipmap_25):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"png")

            labels = load_texture_reference_labels(root)

            self.assertEqual(labels[(7, 0)].label, "proper")
            self.assertEqual(labels[(25, 2)].label, "mipmap")
            self.assertNotIn((25, 1), labels)

            trusted_labels = load_texture_reference_labels(
                root,
                trust_table25_proper=True,
            )
            self.assertEqual(trusted_labels[(25, 1)].label, "proper")

    def test_packed_rgba_mipmap_candidate_ranks_over_direct_size_guess(self):
        entry = TextureTableEntry(
            table_id=25,
            index=2,
            offset=0x123456,
            raw_data=b"\xff\xff" * (0xAA0 // 2),
        )

        result = analyze_texture_entry(entry, table_entries=(entry,))

        self.assertEqual(result.status, "mipmap_candidate")
        self.assertEqual(result.best_candidate.kind, "mipmap")
        self.assertEqual(result.best_candidate.format_name, "RGBA16")
        self.assertEqual(result.best_candidate.fmt, 0)
        self.assertEqual(result.best_candidate.size, 2)
        self.assertEqual(result.best_candidate.width, 32)
        self.assertEqual(result.best_candidate.height, 32)
        self.assertEqual(result.best_candidate.storage_layout, "packed_rgba16")

    def test_adjacent_palette_promotes_color_indexed_candidate(self):
        texture = TextureTableEntry(
            table_id=25,
            index=0,
            offset=0x200000,
            raw_data=(bytes(range(256)) * 8),
        )
        palette = TextureTableEntry(
            table_id=25,
            index=1,
            offset=0x200800,
            raw_data=b"\xff\xff" * 16,
        )

        result = analyze_texture_entry(texture, table_entries=(texture, palette))

        self.assertEqual(result.status, "alternate_format_candidate")
        self.assertEqual(result.best_candidate.format_name, "CI4")
        self.assertEqual(result.best_candidate.fmt, 2)
        self.assertEqual(result.best_candidate.size, 0)
        self.assertEqual(result.best_candidate.palette_index, 1)

    def test_report_serializers_include_best_candidate(self):
        entry = TextureTableEntry(
            table_id=25,
            index=2,
            offset=0x123456,
            raw_data=b"\xff\xff" * (0xAA0 // 2),
        )
        result = analyze_texture_entry(entry, table_entries=(entry,))

        json_report = results_to_json((result,), candidate_limit=1)
        csv_report = results_to_csv((result,))

        self.assertIn('"mipmap_candidate"', json_report)
        self.assertIn('"packed_rgba16"', json_report)
        self.assertIn("mipmap_candidate", csv_report)
        self.assertIn("packed_rgba16", csv_report)


if __name__ == "__main__":
    unittest.main()
