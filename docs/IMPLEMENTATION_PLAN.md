# Implementation plan and requirement decisions

Primary requirements: the supplied SmartScan synopsis (CSE 3176, academic year 2026) and the attached detailed implementation brief.

## Phase 1 — Analyze

Inputs: local document photographs and webcam frames. Outputs: corrected colour/grayscale/binary scan, PNG/JPEG/PDF, quality report, actual processing stages. The project must remain offline and expose every FCV technique rather than force all techniques through one chain.

Reasonable decisions: use PySide6 for a native desktop frontend; classical scan processing plus a local Tesseract OCR dependency; one document per photograph; user selects the final boundary when automatic inference is unreliable. All optional features from the detailed brief are included in version 2. Partial visibility is treated as an acquisition limitation, not grounds to invent hidden text. Quality scores and boundary confidence are explicitly heuristic.

## Phase 2 — Design

Pure CV modules accept NumPy arrays. `pipeline.scan` orchestrates them. GUI and CLI share the same pipeline. Qt workers execute CV, loading and export outside the event loop. Manual points remain in original pixel coordinates. Camera I/O uses a separate QThread. Independent experiments make alternative FCV operations observable without changing the saved scan.

## Phase 3 — Implement

1. Validate images, EXIF, crop, resize and grayscale.
2. Build contour proposals from Canny/Otsu/HSV; supplement with Hough intersections; rank and reject weak candidates.
3. Validate/order convex corners, calculate a four-point homography, warp and crop.
4. Implement five modes plus common controls and an independent technique lab.
5. Implement transparent diagnostics and atomic image/PDF exports.
6. Integrate side-by-side previews, manual edits, stages, comparison, recent paths, capture and multipage queue.

## Phase 4 — Test

Generate deterministic document scenes with known quadrilaterals. Measure polygon IoU, check corner reprojection, output type/range, blur/noise behavior, invalid inputs, a 25.2-MP array, image/PDF round-trips and actual offscreen GUI interactions. Record failures, fix defects and rerun affected checks. Do not infer real-photo performance from fixture tests.

## Phase 5 — Polish

Consistent navy/teal visual style, numbered processing controls, readable status, usable empty/failure states, scrollable controls, user-space export selection, task blocking that prevents conflicting operations, queue bounds and clear diagnostic limitations.

## Phase 6 — Deliver

Source ZIP, reproducible dependencies, samples, unit/integration tests, measured testing evidence, algorithm guide, architecture/pipeline diagrams, demonstration instructions, viva Q&A and a complete project report.

## Core acceptance mapping

| Requirement | Implementation / evidence |
|---|---|
| Automatic boundaries and fallback | document_detection.py; editable ImageCanvas; test_detection.py |
| Perspective correction and homography | perspective_correction.py; reprojection test |
| All FCV topics | FCV_GUIDE.md mapping and technique-lab tests |
| Five modes and adjustments | enhancement.py; test_processing.py |
| Honest quality comparison | quality_analysis.py; Quality report; test_quality.py |
| GUI and long-operation responsiveness | gui.py workers; event-loop timer test |
| PNG/JPEG/PDF + directory selection | export.py; file dialogs; round-trip tests |
| Camera and real photographs | implemented; hardware validation explicitly local |
| Installation on Windows | venv executable commands; run_windows.bat; local verification procedure |
| Report, diagrams, viva | docs/ |

## Extended-feature implementation

All optional features are implemented: local OCR, preview/copy/TXT, aligned searchable PDFs, persistent multipage documents, page numbering, manual rotation, manual boundary adjustment, single/multiple file drop, scan history with OCR search, cancellable batch processing and a registered comparison slider.

`ocr.py` invokes local Tesseract without a shell; `history.py` stores snapshots and queue order in SQLite; `batch.py` isolates per-file failures; `advanced_gui.py` integrates the shipping interface; `gui_widgets.py` provides the wipe view. Changed images invalidate cached OCR. Searchable-PDF failure is explicit. Batch OCR failure retains the successfully scanned PNG.
