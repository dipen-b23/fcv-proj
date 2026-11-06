# SmartScan · Streamlit document studio

Local document scanning with OpenCV, Streamlit and Tesseract OCR. The frontend is `streamlit_app.py`; the reusable scanning, enhancement, OCR, history and PDF modules live in `src/`.

## Windows setup

Open PowerShell in the folder containing `requirements.txt`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Python 3.11 is also supported. After installation, `run_windows.bat` starts Streamlit. `python main.py` is an alternative launcher for the same frontend.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

OCR/searchable PDFs require a locally installed Tesseract engine and language data. See [OCR setup](docs/OCR_SETUP.md). Scanning and ordinary image/PDF exports work without OCR. Webcam capture uses the browser's camera permission.

## Frontend

Use the sidebar to select Scan, Stages, FCV lab, OCR and export, Document pages, History or Batch. Upload a photograph or try a sample, inspect the boundary, adjust the corner coordinates if needed, and choose an enhancement preset. Rotate scans and compare before/after images with the slider. OCR provides a transcript and searchable PDFs. Document pages support ordering, numbering and multipage export. History persists processed snapshots locally; batch processing produces independent per-file results.

## Command line

```bash
python main.py --cli sample_images/perspective.png outputs/scan.png
python main.py --cli sample_images/perspective.png outputs/searchable.pdf --searchable --number-pages
```

## Tests and evaluation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/evaluate.py
python tools/evaluate_optionals.py
```

OCR tests/evaluation require Tesseract with English data. Streamlit tests use AppTest. The evaluators run without a desktop display or Qt and write measured JSON evidence. The project report and older test evidence under `docs/` describe the earlier desktop release; they are retained as academic history, not claims about the current frontend. Refer to this README for current launch and test instructions.

## Repository layout

- `streamlit_app.py`: browser frontend.
- `main.py`: Streamlit / CLI launcher.
- `src/`: shared computer vision, OCR, history, batch and export logic.
- `tests/`: backend and Streamlit tests.
- `tools/`: sample generation, diagrams and headless evaluation.
- `sample_images/`: reproducible fixtures and reference text.
- `assets/fonts/`: fonts used by PDF page numbering; required at runtime.
- `docs/`: algorithm explanations, OCR setup, reports and historical evidence.

The retired PySide6 dashboard, its widget modules, desktop tests, screenshot assets and desktop report-generation scripts have been removed. PySide6 is no longer a dependency.
