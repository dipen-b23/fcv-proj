"""Refresh human-readable evidence from executed JUnit and OCR evaluation files."""
from pathlib import Path
import json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/'docs'

def main():
    suites=list(ET.parse(DOCS/'test_results.xml').getroot().iter('testsuite'))
    total=sum(int(s.get('tests',0)) for s in suites);failures=sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites);skips=sum(int(s.get('skipped',0)) for s in suites);seconds=sum(float(s.get('time',0)) for s in suites)
    ocr=json.loads((DOCS/'optional_evaluation.json').read_text())
    text=f'''# SmartScan 2 testing report

Executed evidence date: 2 November 2026. Linux x86_64 / CPython 3.12.14, Qt offscreen. Native OCR engine: {ocr['engine']}.

## Final automated result

**{total} tests; {failures} failures/errors; {skips} skipped; {seconds:.2f} seconds.** The complete machine-readable run is docs/test_results.xml. Command from the extracted project root:

```text
python -m pytest -q --junitxml=docs/test_results.xml
```

Install requirements-dev.txt and the Tesseract engine with eng data first. The extended tests invoke real Tesseract and actual Qt widgets rather than fabricating recognition results.

| Area | Executed verification |
|---|---|
| Boundary detection | Ten generated full-page scenes with polygon IoU >0.90; blank, negative object and truncated-page rejection |
| Geometry | Corner permutations, convexity/bounds/degeneracy, homography reprojection, 6000×4200 array and 2600-pixel warp cap |
| Image processing | All five enhancement presets and 18 independent lab operations; binary range and invalid parameters |
| Image/PDF I/O | Unicode paths, EXIF, lossless PNG/JPEG dimensions, actual embedded images and page counts |
| Quality | Blur and noise changes produce expected proxy behavior; finite bounded scores |
| Core GUI | Actual widgets, processing previews, timer events during scanning, manual click/drag, modes and lab |
| Real OCR | Known printed text, word boxes, UTF-8 transcript, mean engine confidence, missing engine/language errors |
| Searchable PDF | Extracted text on every page; numbering; page image retained; stale dimension mismatch rejected |
| Persistent data | Snapshots, OCR and duplicate ordered page IDs restored by fresh HistoryStore/window instances; text search; deletion removes queue references |
| Batch | Mixed successful/no-document/invalid files, OCR failure retains PNG, cancellation before remaining files, JSON report |
| Shipping GUI | Rotation and homography composition, stale OCR cleared by enhancement/rotation, clipboard, persistent page order, numbered searchable document, batch table, multi-file drop, wipe slider |
| Export/history consistency | Exporting a searchable PDF without first extracting text also saves its recognized text to history |
| CLI | Raster and searchable outputs, stages/JSON, error codes and OCR text sidecar |

## Measured fixtures and limits

The generated geometric scenes and their exact corners are in sample_images/ground_truth.json. Their measured detection IoUs and single-observation pipeline timings are in docs/evaluation.json. These are controlled fixtures, not a real-camera accuracy benchmark.

The OCR fixture has {ocr['reference_words']} English reference words and {ocr['reference_characters']} normalized reference characters. Observed character edits: {ocr['character_edits']}; word edits: {ocr['word_edits']}. Case, punctuation and whitespace are normalized. This is one clean generated printed-text fixture, not general OCR accuracy. Mean engine confidence is not used as an accuracy substitute. The actual transcript and measured flags are in optional_evaluation.json.

The OCR demo PDF contains {ocr['pdf_pages']} pages. Text extraction on every page: {ocr['searchable_text_on_all_pages']}; numbering verified: {ocr['numbering_verified']}. Queue restart: {ocr['queue_restart_verified']}; history OCR-text search: {ocr['history_text_search_verified']}. Mixed-batch statuses: {', '.join(ocr['batch_statuses'])}.

A fresh Python venv without inherited system packages installed the pinned dependencies successfully. `pip check` reported no broken requirements. The actual main.main() entry point launched the shipping interface in a timed offscreen event loop with exit 0. The searchable CLI exported with exit 0, and its extracted PDF text contained SMARTSCAN. The native system Tesseract installation was used by this venv.

## Visual verification

The running workspace, OCR view and comparison view were captured from actual Qt widgets. The report and searchable demo were rendered with Poppler. Page layout, footer placement, embedded images and legible text were inspected. A sidebar sizing issue caused by long recent paths was corrected; the resulting screenshot shows the full controls.

## Local Windows/camera checklist

Windows native windowing, a physical webcam, diverse phone photographs, handwriting and non-English OCR were not exercised here. Verify these on your laptop before presenting:

1. Follow README and OCR_SETUP. Check Tesseract availability and installed eng data in OCR / text.
2. Run main.py in a normal desktop session, without QT_QPA_PLATFORM=offscreen.
3. Try sample, then a real phone photograph. Inspect every corner, edit/drag them and apply.
4. Try all five modes and the independent FCV experiments; compare thin strokes visually.
5. Rotate the page, extract text, copy/export TXT and inspect the transcript. Open a searchable PDF in another viewer and search for a visible word.
6. Add several scanned/camera pages, reorder/preview/remove, enable numbering and searchable export. Check page order, page count and footer numbers in another viewer.
7. Restart the app and confirm history/queue restoration. Search for recognized text. Reopen a snapshot and confirm it is the processed page; the original photo is not stored.
8. Drop several images or choose Batch. Include a no-document image. Check independent statuses, retained PNGs and the JSON report; cancel between pages. Double-click a failed row for manual correction.
9. Move the Before / after divider and verify that both halves show the same rectified geometry. The original/photo comparison remains in Workspace.
10. Test Webcam with operating-system permissions, then without a connected camera. Upload remains usable. Camera-driver opening/closing delays depend on the laptop.
11. Test a large phone image, exports into a chosen directory and the stage/quality JSON files. Processing should keep the window painting; action buttons are temporarily disabled.
12. Test missing engine/language feedback if practical. A requested searchable PDF must not silently become raster-only. Batch OCR failure must retain its scanned PNG.

Heavy blur, glare and hidden content cannot be reconstructed by choosing corners. OCR can make reading-order/transcription errors. Proofread important text.
'''
    (DOCS/'TESTING.md').write_text(text,encoding='utf-8');print(f'Testing report updated: {total} tests, {failures} failures/errors.')
if __name__=='__main__':main()
