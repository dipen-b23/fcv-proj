# Offline OCR setup

SmartScan 2 uses a local **Tesseract 5** executable and installed language data. The Python requirements install the GUI and PDF libraries; they do not install the native Tesseract engine. No API account, API key or network request is used for recognition. Installing dependencies and language packs requires internet once unless you already have an installer.

## Windows

1. Follow the [Tesseract installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html), which links to Windows builds. The [UB Mannheim Windows build page](https://github.com/UB-Mannheim/tesseract/wiki) provides its installer.
2. Install the engine with **English** language data. The common executable location is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Open SmartScan, select **OCR / text**, and click **Check OCR setup**. If automatic detection fails, click **Browse executable** and select that executable. The chosen path is remembered locally.
4. To verify from PowerShell:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

Alternatively set a path for the current PowerShell session before starting SmartScan:

```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

## Ubuntu / Debian

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
```

The developer library is not required for SmartScan's command-line adapter. On macOS, install `tesseract` through your package manager, then verify `tesseract --list-langs`. Use the GUI executable selector when it is not on PATH.

## Languages and layouts

The default language is `eng`. Use installed combinations such as `eng+hin` only after installing the corresponding `hin.traineddata` file/language package. Click Check OCR setup to see installed codes; type a combined code in the editable language field. The app reports missing language data rather than downloading models silently. Only English was exercised in this project's OCR evaluation.

The layout selector exposes:

| Setting | Tesseract PSM | Suitable input |
|---|---|---|
| Automatic page | 3 | A normal page with headings/paragraphs |
| Single text block | 6 | A uniformly laid-out block |
| Sparse text | 11 | Isolated text labels |

Rotate sideways or upside-down scans with Rotate left/right before recognition. Automatic text-orientation inference is not implemented; manual rotation is. Handwriting, decorative fonts, tables, faint text and strong blur remain difficult. Engine confidence is not validated transcription accuracy.

## OCR and PDF workflow

1. Scan a photograph and inspect its corners.
2. Choose an enhancement mode that keeps thin strokes readable.
3. In OCR / text, choose the language/layout and click Extract text.
4. Inspect the read-only preview. Copy it or export UTF-8 TXT. Editing copied text outside SmartScan does not update the image's searchable layer.
5. Save searchable PDF. It contains the page image and Tesseract's aligned invisible text layer. Ordinary Image PDF remains available when OCR is not desired.
6. For multiple pages, add scans to the document, reorder them in Pages, leave Searchable PDF checked and export. Existing per-page OCR is reused; missing OCR is run with the current language/layout. Page numbers follow the final order.

Changing enhancement or rotation invalidates current OCR, preventing export of an old text layer against a changed image. PDF export preserves the OCR/image coordinate relationship while fitting both to A4. Page numbers sit below the image rather than covering document text.

If Tesseract is missing or fails, a requested searchable export reports the error; it does not silently produce an image-only PDF. In batch mode, the successfully scanned PNG is retained and its row is marked `ocr_error`. Batch cancellation takes effect between pages; a current OCR subprocess can take up to its 90-second timeout.

## Reproducible CLI examples

```powershell
.\.venv\Scripts\python.exe main.py --cli sample_images/perspective.png outputs/searchable.pdf --searchable --number-pages
.\.venv\Scripts\python.exe main.py --cli sample_images/perspective.png outputs/scan.png --ocr --language eng
.\.venv\Scripts\python.exe main.py --cli my_photos outputs/new_batch --batch --ocr
```

The CLI also accepts `--psm 3`, `--psm 6`, `--psm 11` and `--tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"`. `--searchable` requires a PDF filename outside batch mode. Batch input is an image directory and its output must be new or empty.
