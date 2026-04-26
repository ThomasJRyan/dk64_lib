# DK64 Lib Refactor Plan

## Verified Baseline

- The project is installed in editable mode in `.venv`.
- Use `.venv/bin/python -m pytest -q` as the baseline verification command.
- Current baseline result: `11 passed, 432 subtests passed`.
- The existing tests cover ROM metadata, text extraction, geometry table metadata, display-list command counts, and OBJ output against 216 golden OBJ fixtures.

## Known Issue

- `GeometryData.create_dae()` currently fails because `input_list` is used before assignment in `src/dk64_lib/data_types/geometry.py`.
- DAE export is not covered by the existing test suite, so add a regression test before or alongside the fix.

## Refactor Sequence

1. Add DAE export coverage and fix the current `create_dae()` ordering bug.
2. Introduce an explicit binary reader over `bytes` or `memoryview` with `read_u8`, `read_u16`, `read_u32`, `read_at`, and `slice` style operations.
3. Refactor ROM pointer-table extraction into explicit table-entry records before decoding payloads.
4. Convert parsed records such as vertices, triangles, table entries, display-list chunks, expansions, and text fragments into clear value objects.
5. Keep OBJ output and display-list command counts stable throughout the refactor using the existing golden tests.
6. After the binary and table layers are clearer, simplify F3DEX2 command parsing into a compact registry and command model.

## Rust Migration Notes

- Prefer explicit byte offsets, sizes, and endianness over hidden file-pointer state.
- Keep parsing and export behavior separated so the eventual Rust implementation can mirror the parser without inheriting Python-specific output code.
- Preserve golden fixtures as compatibility tests during both Python refactoring and later Rust porting.
