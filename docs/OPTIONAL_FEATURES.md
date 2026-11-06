# All requested optional features

All optional features named in the project brief are included in SmartScan 2. OCR uses the locally installed Tesseract engine; it is not a network API.

| Optional feature from brief | Implementation | How to demonstrate |
|---|---|---|
| OCR with Tesseract or equivalent | `ocr.recognize`, `advanced_gui.extract_text` | Scan, select language/layout, Extract text |
| Extracted text preview | `advanced_gui.build_ocr_tab`, `show_ocr`, `copy_text`, `export_text` | Read preview, copy text and save UTF-8 TXT |
| Searchable PDF generation | `export.save_pdf(ocr_pages=...)`, `advanced_gui.export_current_to` | Export searchable PDF and search a visible word in a PDF viewer |
| Multi-page document scanning | `history.HistoryStore.set_queue`, `advanced_gui.add_page`, `export_queue_to` | Add several uploaded/camera scans, reorder and export |
| Automatic page numbering | `export._number_overlay`, Pages checkbox | Reorder pages; export with Page N of total footer |
| Document rotation | `advanced_gui.rotate_current` | Rotate left/right, then run OCR on corrected orientation |
| Manual boundary adjustment | `gui.ImageCanvas` and `apply_manual` | Drag markers or clear/reselect four corners |
| Drag-and-drop image upload | `advanced_gui.dropEvent`, `gui.dragEnterEvent` | Drop one image to scan or several to batch-process |
| Scan history | `history.HistoryStore`, History tab | Search titles/OCR text; reopen or delete snapshot; restart to verify persistence |
| Batch processing | `batch.process_batch`, Batch tab, CLI `--batch` | Mixed valid/invalid/no-page images produce independent statuses and a JSON report |
| Side-by-side comparison slider | `gui_widgets.ComparisonCanvas` | Drag registered before/after divider; original/photo view remains in Workspace |

## OCR and text-layer integrity

OCR runs on the final displayed scan. Tesseract returns text, TSV word boxes/confidence and a PDF containing the corresponding image and invisible text. The application does not place an unrelated transcript on a page. Export transforms the OCR PDF as a whole to fit A4, preserving text/image alignment. Visible footer numbers are added outside the page image. Changing enhancement or rotation clears the current OCR cache. A searchable export re-runs missing OCR; an engine/configuration failure is shown instead of silently downgrading the request.

## Multi-page and history behavior

Each queued entry references a processed image snapshot in a local SQLite catalog. The order is stored persistently, supports duplicates, and can be changed with Move up/down. Remove page affects the document; delete snapshot affects history and its queue references. Clear document leaves history intact. Reopening a history snapshot displays that processed page as the source; it does not pretend to restore an original photograph that was never stored.

Automatic scans are archived when a valid boundary produces an output. To archive a later enhancement/rotation, use Save current snapshot or Add scan to document. OCR is attached to its matching snapshot. History search includes OCR text for the latest 500 snapshots. The document queue is capped at 20 pages, but older scan snapshots remain in history until deleted.

## Batch and cancellation behavior

Each file is scanned independently. A failed document boundary is marked `manual_required`; a malformed input is `error`; OCR failures after successful scanning are `ocr_error`, with the PNG retained. A cancelled run marks remaining files `cancelled`. The GUI opens a unique output run directory and writes a per-file JSON report. Double-click a failed row to open its source and adjust corners manually. Batch work runs outside the GUI thread. Cancellation is checked between pages, not halfway through OpenCV or a Tesseract process.

## Comparison geometry

The original and final images are side by side in Workspace. The wipe slider compares the already rectified page before enhancement against its enhanced output. This keeps both halves registered; a wipe between a distorted photo and rectified page would have mismatched geometry.

## Scope

Only English printed-text OCR is tested in this release. Other locally installed language codes can be selected but require their own validation. The image-processing pipeline remains classical OpenCV. Tesseract itself may use its trained neural recognition engine; this is an external local OCR component, not a newly trained model claimed by this project. Searchable-PDF text and reading order depend on recognition quality. Automatic orientation, handwriting recognition, PDF input parsing and curved-page correction are not claimed.
