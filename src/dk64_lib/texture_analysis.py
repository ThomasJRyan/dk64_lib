"""Heuristic texture table analysis utilities.

The texture exporter can only be exact when F3DEX2 display lists provide the
format, size, palette, width, and height. This module handles the harder case:
raw table entries with no display-list metadata. It ranks likely interpretations
from byte size, nearby palette entries, known packed-mipmap storage formulas,
and simple raw-data statistics. When hand-sorted reference folders are provided,
it also calibrates those rankings with a nearest-neighbor pass over raw-byte
features, without creating a static per-index manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys

from collections import Counter
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
from typing import Iterable, Sequence


TEXTURE_ANALYSIS_TABLES = (7, 14, 25)

_REFERENCE_FILENAME = re.compile(r"^(?P<index>\d{6})_offset_[0-9a-fA-F]+_")
_REFERENCE_TABLE = re.compile(r"^table_(?P<table>\d+)$")


@dataclass(frozen=True, slots=True)
class TextureFormat:
    """N64 texture format/size pair used for candidate ranking."""

    name: str
    fmt: int
    size: int
    bits_per_texel: int
    needs_palette: bool = False


TEXTURE_FORMATS: tuple[TextureFormat, ...] = (
    TextureFormat("RGBA16", 0, 2, 16),
    TextureFormat("RGBA32", 0, 3, 32),
    TextureFormat("CI4", 2, 0, 4, needs_palette=True),
    TextureFormat("CI8", 2, 1, 8, needs_palette=True),
    TextureFormat("IA4", 3, 0, 4),
    TextureFormat("IA8", 3, 1, 8),
    TextureFormat("IA16", 3, 2, 16),
    TextureFormat("I4", 4, 0, 4),
    TextureFormat("I8", 4, 1, 8),
)

_TEXTURE_FORMAT_BY_CODE = {
    (texture_format.fmt, texture_format.size): texture_format
    for texture_format in TEXTURE_FORMATS
}

_COMMON_DIMENSIONS = {
    (4, 4),
    (8, 8),
    (16, 16),
    (16, 32),
    (32, 16),
    (32, 32),
    (32, 44),
    (32, 64),
    (44, 44),
    (48, 42),
    (64, 32),
    (64, 64),
    (128, 64),
    (64, 128),
}

_PREFERRED_RGBA16_DIMENSIONS = {
    (32, 32),
    (32, 44),
    (32, 64),
    (44, 44),
    (48, 42),
}

_MIPMAP_BASE_DIMENSIONS = (
    (32, 64),
    (64, 32),
    (32, 32),
    (64, 64),
    (16, 32),
    (32, 16),
    (16, 16),
)

_PALETTE_BYTE_SIZES = {0x20, 0x200}
_CI4_PALETTE_BYTE_SIZES = {0x20, 0x200}
_CI8_PALETTE_BYTE_SIZES = {0x200}


@dataclass(frozen=True, slots=True)
class TextureTableEntry:
    """Raw texture-table entry used by the analyzer."""

    table_id: int
    index: int
    offset: int
    raw_data: bytes

    @property
    def raw_size(self) -> int:
        return len(self.raw_data)


@dataclass(frozen=True, slots=True)
class TextureCandidate:
    """A possible interpretation of a raw texture-table entry."""

    kind: str
    format_name: str
    fmt: int | None
    size: int | None
    width: int | None
    height: int | None
    storage_layout: str
    expected_bytes: int
    score: float
    confidence: str
    notes: tuple[str, ...] = tuple()
    palette_index: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "format_name": self.format_name,
            "fmt": self.fmt,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "storage_layout": self.storage_layout,
            "expected_bytes": self.expected_bytes,
            "score": round(self.score, 2),
            "confidence": self.confidence,
            "palette_index": self.palette_index,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class TextureReferenceLabel:
    """Optional hand-sorted reference label for evaluating the heuristic."""

    label: str
    path: str
    trusted: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "path": self.path,
            "trusted": self.trusted,
        }


@dataclass(frozen=True, slots=True)
class TextureReferenceNeighbor:
    """Nearest hand-labeled entry used by the reference-calibrated pass."""

    table_id: int
    index: int
    label: str
    distance: float

    def to_dict(self) -> dict[str, object]:
        return {
            "table": self.table_id,
            "index": self.index,
            "label": self.label,
            "distance": round(self.distance, 4),
        }


@dataclass(frozen=True, slots=True)
class TextureReferencePrediction:
    """Dynamic prediction learned from optional hand-sorted reference folders."""

    label: str
    confidence: float
    neighbors: tuple[TextureReferenceNeighbor, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "neighbors": [neighbor.to_dict() for neighbor in self.neighbors],
        }


@dataclass(frozen=True, slots=True)
class TextureAnalysisResult:
    """Analysis result for one raw texture-table entry."""

    table_id: int
    index: int
    offset: int
    raw_size: int
    status: str
    candidates: tuple[TextureCandidate, ...]
    reference: TextureReferenceLabel | None = None
    reference_prediction: TextureReferencePrediction | None = None
    signals: dict[str, float] | None = None

    @property
    def best_candidate(self) -> TextureCandidate | None:
        return self.candidates[0] if self.candidates else None

    def to_dict(self, candidate_limit: int | None = 5) -> dict[str, object]:
        candidates = self.candidates
        if candidate_limit is not None:
            candidates = candidates[:candidate_limit]
        return {
            "table": self.table_id,
            "index": self.index,
            "offset": f"0x{self.offset:08x}",
            "raw_size": self.raw_size,
            "status": self.status,
            "reference": self.reference.to_dict() if self.reference else None,
            "reference_prediction": (
                self.reference_prediction.to_dict()
                if self.reference_prediction
                else None
            ),
            "signals": self.signals,
            "best_candidate": (
                self.best_candidate.to_dict() if self.best_candidate else None
            ),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }


def analyze_rom_textures(
    rom: object,
    tables: Sequence[int] = TEXTURE_ANALYSIS_TABLES,
    reference_root: str | Path | None = None,
    max_entries: int | None = None,
    trust_table25_proper: bool = False,
) -> tuple[TextureAnalysisResult, ...]:
    """Analyze raw texture tables and return ranked format/layout guesses.

    ``reference_root`` may point at a folder containing ``proper_textures`` and
    ``broken_textures`` subfolders. Those labels are attached for evaluation
    only; they are never required for candidate generation.
    """

    reference_labels = (
        load_texture_reference_labels(
            reference_root,
            trust_table25_proper=trust_table25_proper,
        )
        if reference_root is not None
        else {}
    )
    results = list()
    for table_id in tables:
        entries = texture_table_entries(rom, table_id, max_entries=max_entries)
        results.extend(
            analyze_texture_entry(
                entry,
                table_entries=entries,
                reference=reference_labels.get((entry.table_id, entry.index)),
            )
            for entry in entries
        )
    results = tuple(results)
    if reference_labels:
        return _apply_reference_predictions(results)
    return results


def texture_table_entries(
    rom: object,
    table_id: int,
    max_entries: int | None = None,
) -> tuple[TextureTableEntry, ...]:
    """Read raw entries from one ROM texture table."""

    entries = list()
    for index, table_data in enumerate(rom.generate_rom_table_data([table_id])):
        raw_data = table_data.get("raw_data", b"")
        if not raw_data:
            continue
        entries.append(
            TextureTableEntry(
                table_id=table_id,
                index=index,
                offset=int(table_data.get("offset", 0)),
                raw_data=bytes(raw_data),
            )
        )
        if max_entries is not None and len(entries) >= max_entries:
            break
    return tuple(entries)


def analyze_texture_entry(
    entry: TextureTableEntry,
    table_entries: Sequence[TextureTableEntry] = tuple(),
    reference: TextureReferenceLabel | None = None,
) -> TextureAnalysisResult:
    """Analyze one raw texture table entry."""

    entry_by_index = {candidate.index: candidate for candidate in table_entries}
    candidates = []
    if entry.raw_size in _PALETTE_BYTE_SIZES:
        candidates.append(_palette_candidate(entry, entry_by_index))
    candidates.extend(_base_texture_candidates(entry, entry_by_index))
    candidates.extend(_mipmap_texture_candidates(entry, entry_by_index))
    candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.kind == "mipmap",
            candidate.width or 0,
            candidate.height or 0,
        ),
        reverse=True,
    )
    return TextureAnalysisResult(
        table_id=entry.table_id,
        index=entry.index,
        offset=entry.offset,
        raw_size=entry.raw_size,
        status=_status_for_candidates(tuple(candidates)),
        candidates=tuple(candidates),
        reference=reference,
        signals=_entry_signals(entry, entry_by_index),
    )


def load_texture_reference_labels(
    reference_root: str | Path,
    trust_table25_proper: bool = False,
) -> dict[tuple[int, int], TextureReferenceLabel]:
    """Load optional hand-sorted reference labels from an output folder.

    ``proper_textures/table_25`` is treated as untrusted by default because it
    was not manually classified in the same way as the smaller table folders.
    """

    root = Path(reference_root)
    labels: dict[tuple[int, int], TextureReferenceLabel] = {}
    reference_sets = (
        ("proper_textures", "proper"),
        ("broken_textures", "broken"),
    )
    for folder_name, default_label in reference_sets:
        folder = root / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.png"):
            table_id = _table_id_from_reference_path(path)
            if table_id is None:
                continue
            index_match = _REFERENCE_FILENAME.match(path.name)
            if not index_match:
                continue
            label = default_label
            if default_label == "broken":
                label = path.parent.name
            trusted = not (
                folder_name == "proper_textures"
                and table_id == 25
                and not trust_table25_proper
            )
            if not trusted:
                continue
            labels[(table_id, int(index_match.group("index")))] = (
                TextureReferenceLabel(
                    label=label,
                    path=str(path),
                    trusted=trusted,
                )
            )
    return labels


def summarize_texture_analysis(
    results: Iterable[TextureAnalysisResult],
) -> dict[str, object]:
    """Build a small summary for JSON reports and CLI output."""

    result_tuple = tuple(results)
    status_counts = Counter(result.status for result in result_tuple)
    reference_counts = Counter(
        result.reference.label for result in result_tuple if result.reference
    )
    matches = Counter()
    for result in result_tuple:
        if result.reference is None:
            continue
        if _result_matches_reference(result):
            matches["matched"] += 1
        else:
            matches["mismatched"] += 1
    return {
        "total": len(result_tuple),
        "statuses": dict(sorted(status_counts.items())),
        "reference_labels": dict(sorted(reference_counts.items())),
        "reference_matches": dict(sorted(matches.items())),
    }


def _apply_reference_predictions(
    results: tuple[TextureAnalysisResult, ...],
) -> tuple[TextureAnalysisResult, ...]:
    training_results = tuple(result for result in results if result.reference)
    if len(training_results) < 3:
        return results

    training_by_raw_size: dict[int, list[TextureAnalysisResult]] = {}
    for training_result in training_results:
        training_by_raw_size.setdefault(training_result.raw_size, []).append(
            training_result
        )

    calibrated_results = list()
    for result in results:
        size_bucket = tuple(training_by_raw_size.get(result.raw_size, ()))
        if len(size_bucket) < 3:
            size_bucket = training_results
        prediction = _reference_prediction_for_result(result, size_bucket)
        calibrated_results.append(
            replace(
                result,
                status=_status_with_reference_prediction(result, prediction),
                reference_prediction=prediction,
            )
        )
    return tuple(calibrated_results)


def _reference_prediction_for_result(
    result: TextureAnalysisResult,
    training_results: tuple[TextureAnalysisResult, ...],
    neighbor_count: int = 7,
) -> TextureReferencePrediction | None:
    neighbors = []
    for training_result in training_results:
        if (
            result.table_id == training_result.table_id
            and result.index == training_result.index
        ):
            continue
        if training_result.reference is None:
            continue
        neighbors.append(
            TextureReferenceNeighbor(
                table_id=training_result.table_id,
                index=training_result.index,
                label=training_result.reference.label,
                distance=_feature_distance(result, training_result),
            )
        )
    if not neighbors:
        return None

    nearest = tuple(sorted(neighbors, key=lambda neighbor: neighbor.distance))[
        :neighbor_count
    ]
    votes: Counter[str] = Counter()
    for neighbor in nearest:
        votes[neighbor.label] += 1 / (neighbor.distance + 0.01)
    label, weight = votes.most_common(1)[0]
    confidence = weight / sum(votes.values())
    if confidence < 0.5:
        return None
    return TextureReferencePrediction(
        label=label,
        confidence=confidence,
        neighbors=nearest,
    )


def _status_with_reference_prediction(
    result: TextureAnalysisResult,
    prediction: TextureReferencePrediction | None,
) -> str:
    if prediction is None or prediction.confidence < 0.58:
        return result.status
    if result.status in {"palette_candidate", "unknown"}:
        return result.status
    if prediction.label == "proper":
        if result.status != "mipmap_candidate" or prediction.confidence >= 0.72:
            return "likely_ok"
    if prediction.label == "mipmap":
        return "mipmap_candidate"
    if prediction.label == "wrong_format":
        best = result.best_candidate
        if best and (best.fmt != 0 or best.size != 2):
            return "alternate_format_candidate"
        return "format_ambiguous"
    return result.status


def results_to_json(
    results: Sequence[TextureAnalysisResult],
    candidate_limit: int | None = 5,
) -> str:
    """Serialize texture analysis results as JSON."""

    report = {
        "summary": summarize_texture_analysis(results),
        "results": [
            result.to_dict(candidate_limit=candidate_limit) for result in results
        ],
    }
    return json.dumps(report, indent=2) + "\n"


def results_to_csv(
    results: Sequence[TextureAnalysisResult],
) -> str:
    """Serialize texture analysis results as CSV."""

    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "table",
            "index",
            "offset",
            "raw_size",
            "status",
            "reference",
            "reference_prediction",
            "prediction_confidence",
            "kind",
            "format",
            "fmt",
            "size",
            "width",
            "height",
            "layout",
            "score",
            "confidence",
            "palette_index",
        ),
    )
    writer.writeheader()
    for result in results:
        best = result.best_candidate
        prediction = result.reference_prediction
        writer.writerow(
            {
                "table": result.table_id,
                "index": result.index,
                "offset": f"0x{result.offset:08x}",
                "raw_size": result.raw_size,
                "status": result.status,
                "reference": result.reference.label if result.reference else "",
                "reference_prediction": prediction.label if prediction else "",
                "prediction_confidence": (
                    round(prediction.confidence, 4) if prediction else ""
                ),
                "kind": best.kind if best else "",
                "format": best.format_name if best else "",
                "fmt": best.fmt if best else "",
                "size": best.size if best else "",
                "width": best.width if best else "",
                "height": best.height if best else "",
                "layout": best.storage_layout if best else "",
                "score": round(best.score, 2) if best else "",
                "confidence": best.confidence if best else "",
                "palette_index": best.palette_index if best else "",
            }
        )
    return output.getvalue()


def _base_texture_candidates(
    entry: TextureTableEntry,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[TextureCandidate, ...]:
    candidates = list()
    for texture_format in TEXTURE_FORMATS:
        pixel_count = _pixel_count_for_size(
            entry.raw_size,
            texture_format.bits_per_texel,
        )
        if pixel_count is None:
            continue
        for width, height in _factor_dimensions(pixel_count):
            score, notes, palette_index = _score_base_candidate(
                entry,
                texture_format,
                width,
                height,
                entry_by_index,
            )
            candidates.append(
                TextureCandidate(
                    kind="base",
                    format_name=texture_format.name,
                    fmt=texture_format.fmt,
                    size=texture_format.size,
                    width=width,
                    height=height,
                    storage_layout="exact",
                    expected_bytes=entry.raw_size,
                    score=score,
                    confidence=_confidence(score),
                    notes=notes,
                    palette_index=palette_index,
                )
            )
    return tuple(candidates)


def _mipmap_texture_candidates(
    entry: TextureTableEntry,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[TextureCandidate, ...]:
    candidates = list()
    for width, height in _MIPMAP_BASE_DIMENSIONS:
        candidates.extend(
            _known_mipmap_candidates(entry, width, height, entry_by_index)
        )
    return tuple(candidates)


def _known_mipmap_candidates(
    entry: TextureTableEntry,
    width: int,
    height: int,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[TextureCandidate, ...]:
    candidates = list()
    layout_specs = (
        ("packed_ci4_32x64", _TEXTURE_FORMAT_BY_CODE[(2, 0)], _packed_ci4_pixels),
        (
            "packed_ci4_64x32",
            _TEXTURE_FORMAT_BY_CODE[(2, 0)],
            _packed_ci4_64x32_pixels,
        ),
        (
            "standard_indexed",
            _TEXTURE_FORMAT_BY_CODE[(2, 0)],
            _standard_indexed_pixels,
        ),
        (
            "standard_indexed",
            _TEXTURE_FORMAT_BY_CODE[(2, 1)],
            _standard_indexed_pixels,
        ),
        ("packed_rgba16", _TEXTURE_FORMAT_BY_CODE[(0, 2)], _packed_rgba_pixels),
    )
    for layout_name, texture_format, storage_pixels in layout_specs:
        if layout_name == "packed_ci4_32x64" and (width, height) != (32, 64):
            continue
        if layout_name == "packed_ci4_64x32" and (width, height) != (64, 32):
            continue
        if layout_name == "packed_rgba16" and (width, height) != (32, 32):
            continue
        pixels = storage_pixels(width, height, texture_format.size)
        expected_bytes = _bytes_for_pixels(pixels, texture_format.bits_per_texel)
        if expected_bytes != entry.raw_size:
            continue
        score, notes, palette_index = _score_mipmap_candidate(
            entry,
            texture_format,
            width,
            height,
            layout_name,
            entry_by_index,
        )
        candidates.append(
            TextureCandidate(
                kind="mipmap",
                format_name=texture_format.name,
                fmt=texture_format.fmt,
                size=texture_format.size,
                width=width,
                height=height,
                storage_layout=layout_name,
                expected_bytes=expected_bytes,
                score=score,
                confidence=_confidence(score),
                notes=notes,
                palette_index=palette_index,
            )
        )
    return tuple(candidates)


def _score_base_candidate(
    entry: TextureTableEntry,
    texture_format: TextureFormat,
    width: int,
    height: int,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[float, tuple[str, ...], int | None]:
    score = 30.0
    notes = ["raw byte size exactly matches dimensions"]

    dimension_score, dimension_notes = _dimension_score(width, height)
    score += dimension_score
    notes.extend(dimension_notes)

    palette_score, palette_notes, palette_index = _palette_score(
        entry,
        texture_format,
        entry_by_index,
    )
    score += palette_score
    notes.extend(palette_notes)

    if texture_format.name == "RGBA16":
        if (width, height) in _PREFERRED_RGBA16_DIMENSIONS:
            score += 8.0
            notes.append("dimensions match the current RGBA5551 export prior")
        alpha_score, alpha_note = _rgba16_alpha_score(entry.raw_data)
        score += alpha_score
        notes.append(alpha_note)
    elif texture_format.name == "RGBA32":
        alpha_score, alpha_note = _rgba32_alpha_score(entry.raw_data)
        score += alpha_score
        notes.append(alpha_note)
        score -= 4.0
        notes.append("RGBA32 is less common in known DK64 texture tables")
    elif texture_format.name.startswith("I"):
        score -= 6.0
        notes.append("intensity formats are plausible but need visual review")

    return score, tuple(notes), palette_index


def _score_mipmap_candidate(
    entry: TextureTableEntry,
    texture_format: TextureFormat,
    width: int,
    height: int,
    layout_name: str,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[float, tuple[str, ...], int | None]:
    score = 84.0
    notes = [f"raw byte size exactly matches {layout_name} mipmap storage"]
    dimension_score, dimension_notes = _dimension_score(width, height)
    score += min(dimension_score, 18.0)
    notes.extend(dimension_notes)
    palette_score, palette_notes, palette_index = _palette_score(
        entry,
        texture_format,
        entry_by_index,
    )
    score += palette_score
    notes.extend(palette_notes)
    if texture_format.name == "RGBA16":
        alpha_score, alpha_note = _rgba16_alpha_score(entry.raw_data)
        score += alpha_score
        notes.append(alpha_note)
    return score, tuple(notes), palette_index


def _palette_candidate(
    entry: TextureTableEntry,
    entry_by_index: dict[int, TextureTableEntry],
) -> TextureCandidate:
    score = 78.0
    notes = ["raw size matches a common RGBA16 palette table entry"]
    previous_entry = entry_by_index.get(entry.index - 1)
    if previous_entry and previous_entry.raw_size not in _PALETTE_BYTE_SIZES:
        score += 12.0
        notes.append("previous entry is a plausible texture using this palette")
    width = 16 if entry.raw_size == 0x20 else 16
    height = 1 if entry.raw_size == 0x20 else 16
    return TextureCandidate(
        kind="palette",
        format_name="RGBA16 palette",
        fmt=0,
        size=2,
        width=width,
        height=height,
        storage_layout="palette",
        expected_bytes=entry.raw_size,
        score=score,
        confidence=_confidence(score),
        notes=tuple(notes),
    )


def _palette_score(
    entry: TextureTableEntry,
    texture_format: TextureFormat,
    entry_by_index: dict[int, TextureTableEntry],
) -> tuple[float, list[str], int | None]:
    if not texture_format.needs_palette:
        return 0.0, [], None

    next_entry = entry_by_index.get(entry.index + 1)
    expected_sizes = (
        _CI8_PALETTE_BYTE_SIZES
        if texture_format.size == 1
        else _CI4_PALETTE_BYTE_SIZES
    )
    if next_entry and next_entry.raw_size in expected_sizes:
        return (
            34.0,
            [f"next entry {next_entry.index} has a matching palette byte size"],
            next_entry.index,
        )
    if next_entry and next_entry.raw_size in _PALETTE_BYTE_SIZES:
        return (
            16.0,
            [f"next entry {next_entry.index} is palette-sized but not ideal"],
            next_entry.index,
        )
    return -12.0, ["no adjacent palette-sized entry found"], None


def _entry_signals(
    entry: TextureTableEntry,
    entry_by_index: dict[int, TextureTableEntry],
) -> dict[str, float]:
    raw_data = entry.raw_data
    byte_count = len(raw_data)
    byte_counts = Counter(raw_data)
    alpha_bytes = raw_data[1::2]
    if alpha_bytes:
        alpha16_ratio = sum(value & 1 for value in alpha_bytes) / len(alpha_bytes)
    else:
        alpha16_ratio = 0.0
    mean = sum(raw_data) / byte_count if byte_count else 0.0
    variance = (
        sum((value - mean) ** 2 for value in raw_data) / byte_count
        if byte_count
        else 0.0
    )
    entropy = 0.0
    if byte_count:
        for count in byte_counts.values():
            probability = count / byte_count
            entropy -= probability * math.log2(probability)

    next_entry = entry_by_index.get(entry.index + 1)
    previous_entry = entry_by_index.get(entry.index - 1)
    next_size = float(next_entry.raw_size) if next_entry else 0.0
    previous_size = float(previous_entry.raw_size) if previous_entry else 0.0
    return {
        "raw_size": float(byte_count),
        "raw_size_log2": math.log2(byte_count + 1),
        "alpha16_ratio": alpha16_ratio,
        "unique_ratio": len(byte_counts) / 256,
        "zero_ratio": byte_counts.get(0, 0) / byte_count if byte_count else 0.0,
        "ff_ratio": byte_counts.get(0xFF, 0) / byte_count if byte_count else 0.0,
        "byte_mean": mean / 255,
        "byte_stdev": math.sqrt(variance) / 255,
        "entropy": entropy / 8,
        "next_palette_32": 1.0 if next_size == 0x20 else 0.0,
        "next_palette_512": 1.0 if next_size == 0x200 else 0.0,
        "previous_palette_32": 1.0 if previous_size == 0x20 else 0.0,
        "previous_palette_512": 1.0 if previous_size == 0x200 else 0.0,
    }


def _feature_distance(
    left: TextureAnalysisResult,
    right: TextureAnalysisResult,
) -> float:
    left_signals = left.signals or {}
    right_signals = right.signals or {}
    weighted_keys = (
        ("raw_size_log2", 1.8),
        ("alpha16_ratio", 1.4),
        ("unique_ratio", 1.0),
        ("zero_ratio", 0.5),
        ("ff_ratio", 0.5),
        ("byte_mean", 0.7),
        ("byte_stdev", 0.7),
        ("entropy", 0.9),
        ("next_palette_32", 0.7),
        ("next_palette_512", 0.7),
        ("previous_palette_32", 0.4),
        ("previous_palette_512", 0.4),
    )
    distance = 0.0
    for key, weight in weighted_keys:
        distance += weight * abs(
            left_signals.get(key, 0.0) - right_signals.get(key, 0.0)
        )
    if left.table_id != right.table_id:
        distance += 0.25
    left_best = left.best_candidate
    right_best = right.best_candidate
    if left_best and right_best:
        if left_best.kind != right_best.kind:
            distance += 0.3
        if (left_best.fmt, left_best.size) != (right_best.fmt, right_best.size):
            distance += 0.25
        if (left_best.width, left_best.height) != (
            right_best.width,
            right_best.height,
        ):
            distance += 0.15
    if left.status != right.status:
        distance += 0.2
    return distance


def _dimension_score(width: int, height: int) -> tuple[float, list[str]]:
    score = 0.0
    notes = []
    if (width, height) in _COMMON_DIMENSIONS:
        score += 20.0
        notes.append("dimensions match a common DK64 texture shape")
    if _is_power_of_two(width):
        score += 5.0
    if _is_power_of_two(height):
        score += 5.0
    if _is_power_of_two(width) and _is_power_of_two(height):
        notes.append("both dimensions are powers of two")
    aspect = max(width / height, height / width)
    if aspect <= 2:
        score += 5.0
        notes.append("aspect ratio is compact")
    elif aspect <= 4:
        score += 1.0
    else:
        score -= 8.0
        notes.append("aspect ratio is unusually wide or tall")
    if width < 4 or height < 4:
        score -= 12.0
        notes.append("very small dimensions are unlikely for standalone textures")
    return score, notes


def _rgba16_alpha_score(raw_data: bytes) -> tuple[float, str]:
    if len(raw_data) < 2:
        return 0.0, "not enough data for RGBA16 alpha sampling"
    alpha_bytes = raw_data[1::2]
    opaque = sum(value & 1 for value in alpha_bytes)
    ratio = opaque / len(alpha_bytes)
    if ratio >= 0.92:
        return 16.0, f"RGBA16 alpha bit is mostly opaque ({ratio:.2f})"
    if ratio >= 0.65:
        return 8.0, f"RGBA16 alpha bit is mostly opaque ({ratio:.2f})"
    if ratio <= 0.08:
        return (
            -26.0,
            f"RGBA16 alpha bit is almost entirely transparent ({ratio:.2f})",
        )
    if 0.35 <= ratio <= 0.65:
        return -2.0, f"RGBA16 alpha bit is mixed ({ratio:.2f})"
    return 0.0, f"RGBA16 alpha bit is inconclusive ({ratio:.2f})"


def _rgba32_alpha_score(raw_data: bytes) -> tuple[float, str]:
    if len(raw_data) < 4:
        return 0.0, "not enough data for RGBA32 alpha sampling"
    alpha_bytes = raw_data[3::4]
    solid = sum(1 for value in alpha_bytes if value in (0, 255))
    ratio = solid / len(alpha_bytes)
    if ratio >= 0.9:
        return 8.0, f"RGBA32 alpha bytes look deliberate ({ratio:.2f})"
    return -8.0, f"RGBA32 alpha bytes look noisy ({ratio:.2f})"


def _status_for_candidates(candidates: tuple[TextureCandidate, ...]) -> str:
    if not candidates:
        return "unknown"
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    if best.kind == "palette":
        return "palette_candidate"
    if best.kind == "mipmap":
        return "mipmap_candidate"
    if second and best.score - second.score < 8:
        return "format_ambiguous"
    if best.fmt != 0 or best.size != 2:
        return "alternate_format_candidate"
    if best.confidence == "low":
        return "format_ambiguous"
    return "likely_ok"


def _result_matches_reference(result: TextureAnalysisResult) -> bool:
    if result.reference is None:
        return False
    if result.reference.label == "proper":
        return result.status == "likely_ok"
    if result.reference.label == "mipmap":
        return result.status in {"mipmap_candidate", "format_ambiguous"}
    if result.reference.label == "wrong_format":
        return result.status in {
            "alternate_format_candidate",
            "format_ambiguous",
            "palette_candidate",
        }
    return False


def _confidence(score: float) -> str:
    if score >= 95:
        return "high"
    if score >= 68:
        return "medium"
    return "low"


def _factor_dimensions(
    pixel_count: int,
    min_dimension: int = 4,
    max_dimension: int = 128,
) -> tuple[tuple[int, int], ...]:
    dimensions = set()
    for width in range(min_dimension, max_dimension + 1):
        if pixel_count % width:
            continue
        height = pixel_count // width
        if min_dimension <= height <= max_dimension:
            dimensions.add((width, height))
    return tuple(sorted(dimensions))


def _pixel_count_for_size(byte_size: int, bits_per_texel: int) -> int | None:
    bit_count = byte_size * 8
    if bit_count % bits_per_texel:
        return None
    return bit_count // bits_per_texel


def _bytes_for_pixels(pixel_count: int, bits_per_texel: int) -> int:
    bit_count = pixel_count * bits_per_texel
    return math.ceil(bit_count / 8)


def _packed_ci4_pixels(width: int, height: int, size: int) -> int:
    del size
    level0_width, level0_height = width, height
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    return (
        (level0_width * level0_height)
        + (level1_width * level1_height)
        + (width * math.ceil(level2_height / 2))
        + (width * math.ceil(level3_height / 2))
    )


def _packed_ci4_64x32_pixels(width: int, height: int, size: int) -> int:
    del size
    level1_height = max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    return (
        (width * height)
        + (width * math.ceil(level1_height / 2))
        + (width * math.ceil(level2_height / 4))
        + (width * math.ceil(level3_height / 4))
    )


def _standard_indexed_pixels(width: int, height: int, size: int) -> int:
    level2_width = max(1, width // 4)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    return (
        (width * height)
        + (max(1, width // 2) * max(1, height // 2))
        + _standard_level2_pixels(width, level2_width, level2_height, size)
        + _standard_level3_pixels(width, level3_height, size)
    )


def _standard_level2_pixels(
    source_width: int,
    output_width: int,
    output_height: int,
    size: int,
) -> int:
    if size == 1:
        rows_per_storage_row = max(1, source_width // output_width)
        return source_width * math.ceil(output_height / rows_per_storage_row)
    return source_width * math.ceil(output_height / 2)


def _standard_level3_pixels(
    source_width: int,
    output_height: int,
    size: int,
) -> int:
    if size == 1:
        return source_width * math.ceil(output_height / 4)
    return source_width * math.ceil(output_height / 2)


def _packed_rgba_pixels(width: int, height: int, size: int) -> int:
    del size
    level1_height = max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    return (
        (width * height)
        + (width * math.ceil(level1_height / 2))
        + (width * math.ceil(level2_height / 4))
        + ((level3_width * 4) * math.ceil(level3_height / 4))
    )


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _table_id_from_reference_path(path: Path) -> int | None:
    for parent in path.parents:
        match = _REFERENCE_TABLE.match(parent.name)
        if match:
            return int(match.group("table"))
    return None


def _parse_tables(value: str) -> tuple[int, ...]:
    return tuple(int(table.strip()) for table in value.split(",") if table.strip())


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for texture table analysis."""

    parser = argparse.ArgumentParser(
        description="Analyze DK64 texture tables and rank likely formats.",
    )
    parser.add_argument("rom", help="Path to a big-endian DK64 ROM")
    parser.add_argument(
        "--tables",
        default="7,14,25",
        help="Comma-separated pointer table IDs to analyze. Default: 7,14,25",
    )
    parser.add_argument(
        "--reference-root",
        help=(
            "Optional root containing proper_textures/ and broken_textures/ "
            "folders for evaluation labels."
        ),
    )
    parser.add_argument(
        "--trust-table25-proper",
        action="store_true",
        help="Treat proper_textures/table_25 labels as trusted evaluation data.",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        help="Limit entries analyzed per table.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Report output format. Default: json",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=5,
        help="Maximum candidates per JSON result. Use 0 for all candidates.",
    )
    parser.add_argument(
        "--output",
        help="Optional report path. Defaults to stdout.",
    )
    args = parser.parse_args(argv)

    from dk64_lib.rom import Rom

    results = analyze_rom_textures(
        Rom(args.rom),
        tables=_parse_tables(args.tables),
        reference_root=args.reference_root,
        max_entries=args.max_entries,
        trust_table25_proper=args.trust_table25_proper,
    )
    if args.format == "csv":
        report = results_to_csv(results)
    else:
        candidate_limit = None if args.candidate_limit == 0 else args.candidate_limit
        report = results_to_json(results, candidate_limit=candidate_limit)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(report)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
