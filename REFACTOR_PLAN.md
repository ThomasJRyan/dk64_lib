# DK64 Lib Refactor Plan

## Verified Baseline

- The project is installed in editable mode in `.venv`.
- Use `.venv/bin/python -m pytest -q` as the baseline verification command.
- Current baseline result: `19 passed, 432 subtests passed`.
- The existing tests cover ROM metadata, text extraction, geometry table metadata, display-list command counts, and OBJ output against 216 golden OBJ fixtures.

## Resolved Issue

- `GeometryData.create_dae()` previously failed because `input_list` was used before assignment in `src/dk64_lib/data_types/geometry.py`.
- DAE export is now covered by a regression test and fixed in `7dc9000`.

## Refactor Sequence

1. Add DAE export coverage and fix the current `create_dae()` ordering bug. Done in `7dc9000`.
2. Introduce an explicit binary reader over `bytes` or `memoryview` with `read_u8`, `read_u16`, `read_u32`, `read_at`, and `slice` style operations. Done in `21b725c`.
3. Refactor ROM pointer-table extraction into explicit table-entry records before decoding payloads. Done in `79b56b8`.
4. Convert parsed records such as vertices, triangles, table entries, display-list chunks, expansions, and text fragments into clear value objects.
5. Keep OBJ output and display-list command counts stable throughout the refactor using the existing golden tests.
6. After the binary and table layers are clearer, simplify F3DEX2 command parsing into a compact registry and command model.

## Current Test Baseline

- Latest verification command: `.venv/bin/python -m pytest -q`
- Latest result: `19 passed, 432 subtests passed`

## Rust Migration Notes

- Prefer explicit byte offsets, sizes, and endianness over hidden file-pointer state.
- Keep parsing and export behavior separated so the eventual Rust implementation can mirror the parser without inheriting Python-specific output code.
- Preserve golden fixtures as compatibility tests during both Python refactoring and later Rust porting.
