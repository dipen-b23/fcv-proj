# streamlit_app.py
from pathlib import Path
import io
import json
import tempfile
import zipfile

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

from src.image_processing import (
    load_image,
    resize_longest,
    demonstrate,
    TECHNIQUES,
    MAX_PIXELS,
    validate,
)
from src.document_detection import Detection, boundary_overlay
from src.perspective_correction import validate_corners
from src.pipeline import scan, ScanResult
from src.enhancement import MODES, EnhancementSettings, enhance
from src.quality_analysis import analyze_quality
from src.export import save_pdf
from src.ocr import recognize, available_languages
from src.history import HistoryStore
from src.batch import process_batch


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="SmartScan",
    page_icon="📄",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #101923;
        color: #e8edf2;
    }
    [data-testid="stSidebar"] {
        background: #172633;
    }
    .block-container {
        max-width: 1500px;
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #eff8fa;
    }
    .hero {
        padding: 24px 28px;
        border: 1px solid #304858;
        border-radius: 18px;
        background: linear-gradient(120deg, #173c3a, #172633);
        margin-bottom: 24px;
    }
    .hero h1 {
        margin: 0;
        font-size: 38px;
    }
    .hero p {
        color: #b7cdd5;
        margin-bottom: 0;
    }
    div.stButton > button {
        border-radius: 9px;
    }
    [data-testid="stMetric"] {
        padding: 16px;
        border: 1px solid #304858;
        border-radius: 12px;
        background: #172633;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    store = HistoryStore()
except Exception as exc:
    st.error(f"Cannot open local scan history: {exc}")
    st.stop()

s = st.session_state

for key, value in {
    "source": None,
    "source_name": "",
    "result": None,
    "ocr": None,
    "history_id": None,
    "revision": 0,
    "exports": {},
    "comparison_modes": {},
    "batch_rows": [],
    "batch_zip": None,
}.items():
    if key not in s:
        s[key] = value


def work(function):
    """Display errors without discarding the current workspace."""
    try:
        with st.spinner("Processing…"):
            return function()
    except Exception as exc:
        st.error(str(exc))
        return None


def decode_upload(data):
    """Decode an uploaded image with EXIF orientation and size checks."""
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError(
                "Image exceeds 40 megapixels. Resize it before uploading."
            )
        image = ImageOps.exif_transpose(image).convert("RGB")
        bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return validate(bgr)


def show_image(image, caption=None):
    if image is None:
        return
    preview, _ = resize_longest(image, 1400)
    kwargs = {"channels": "BGR"} if preview.ndim == 3 else {}
    st.image(
        preview,
        caption=caption,
        use_container_width=True,
        **kwargs,
    )


def image_bytes(image, extension=".png"):
    options = (
        [cv2.IMWRITE_JPEG_QUALITY, 95]
        if extension == ".jpg"
        else []
    )
    ok, encoded = cv2.imencode(extension, image, options)
    if not ok:
        raise ValueError("Could not encode the image.")
    return encoded.tobytes()


def invalidate_derived():
    s["revision"] += 1
    s["ocr"] = None
    s["history_id"] = None
    s["exports"] = {}
    s["comparison_modes"] = {}


def remember_current():
    result = s["result"]
    if result is None or result.output is None:
        raise ValueError("Create a scan first.")

    record = store.add(
        result.output,
        s["source_name"] or "Document",
        selected_mode,
        {
            "input_quality": result.input_quality,
            "output_quality": result.output_quality,
        },
        s["ocr"],
    )
    s["history_id"] = record["id"]
    return record["id"]


def accept_scan(image, name, corners=None):
    result = scan(image, selected_mode, settings, corners)
    s["source"] = image
    s["source_name"] = name
    s["result"] = result
    invalidate_derived()

    if result.output is not None:
        remember_current()
    return True


def current_ocr():
    result = s["result"]
    if result is None or result.output is None:
        raise ValueError("Create a scan before running OCR.")

    cached = s["ocr"]
    if cached is None or cached.language != language:
        cached = recognize(
            result.output,
            language=language,
            psm=psm,
            binary=tesseract_path or None,
        )
        s["ocr"] = cached

        if s["history_id"]:
            store.attach_ocr(s["history_id"], cached)
        else:
            remember_current()

    return cached


def pdf_bytes(images, searchable=False, recognized=None):
    with tempfile.TemporaryDirectory(prefix="smartscan-web-pdf-") as folder:
        path = Path(folder) / "document.pdf"
        save_pdf(
            images,
            path,
            page_numbers=number_pages,
            ocr_pages=recognized if searchable else None,
        )
        return path.read_bytes()


def rotate_current(clockwise):
    result = s["result"]
    h, w = result.output.shape[:2]

    code = (
        cv2.ROTATE_90_CLOCKWISE
        if clockwise
        else cv2.ROTATE_90_COUNTERCLOCKWISE
    )
    transform = (
        np.array([[0, -1, h - 1], [1, 0, 0], [0, 0, 1]], float)
        if clockwise
        else np.array([[0, 1, 0], [-1, 0, w - 1], [0, 0, 1]], float)
    )

    result.output = cv2.rotate(result.output, code)
    result.warped = cv2.rotate(result.warped, code)
    result.homography = transform @ result.homography
    result.output_quality = analyze_quality(result.output)
    result.stages["Perspective correction"] = resize_longest(
        result.warped, 1200
    )[0]
    result.stages["Enhancement / final"] = resize_longest(
        result.output, 1200
    )[0]
    invalidate_derived()


def restore_snapshot(identifier):
    record = store.get(identifier)
    image = store.load(identifier)
    h, w = image.shape[:2]
    corners = np.float32(
        [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]
    )
    quality = analyze_quality(image)

    s["source"] = image
    s["source_name"] = record["title"]
    s["result"] = ScanResult(
        Detection(
            corners,
            None,
            "History snapshot",
            "Processed snapshot restored.",
        ),
        image.copy(),
        image.copy(),
        np.eye(3),
        {"Restored scan": resize_longest(image, 1200)[0]},
        quality,
        quality,
        0,
    )
    invalidate_derived()
    s["history_id"] = identifier
    s["ocr"] = store.load_ocr(identifier)
    return True


# Sidebar navigation and controls
with st.sidebar:
    st.title("📄 SmartScan")
    st.caption("LOCAL DOCUMENT STUDIO")

    page = st.radio(
        "Workspace",
        [
            "Scan",
            "Stages",
            "FCV lab",
            "OCR and export",
            "Document pages",
            "History",
            "Batch",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    with st.form("appearance"):
        selected_mode = st.selectbox(
            "Scan mode",
            MODES,
            index=MODES.index("Enhanced document"),
        )
        brightness = st.slider("Brightness", -80, 80, 0)
        contrast = st.slider("Contrast", 0.5, 1.8, 1.0, 0.05)
        gamma = st.slider("Gamma", 0.4, 2.2, 1.0, 0.05)
        sharpening = st.slider("Sharpening", 0.0, 1.0, 0.25, 0.05)
        denoise = st.slider("Denoising", 0, 3, 1)
        threshold_block = st.slider(
            "Threshold window",
            3,
            101,
            31,
            step=2,
        )
        threshold_c = st.slider("Threshold offset", -10, 30, 11)
        threshold_method = st.selectbox(
            "Threshold method",
            ["Adaptive", "Otsu"],
        )
        apply_enhancement = st.form_submit_button(
            "Update enhancement",
            use_container_width=True,
        )

    with st.expander("OCR settings"):
        language = st.text_input("Language codes", "eng")
        psm_label = st.selectbox(
            "Page layout",
            ["Automatic page", "Single text block", "Sparse text"],
        )
        psm = {
            "Automatic page": 3,
            "Single text block": 6,
            "Sparse text": 11,
        }[psm_label]
        tesseract_path = st.text_input(
            "Tesseract executable",
            placeholder=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        if st.button("Check installed languages"):
            installed = work(
                lambda: available_languages(tesseract_path or None)
            )
            if installed is not None:
                st.success(", ".join(installed))

    number_pages = st.checkbox("Number PDF pages", value=True)

settings = EnhancementSettings(
    brightness=brightness,
    contrast=contrast,
    gamma=gamma,
    sharpening=sharpening,
    denoise=denoise,
    threshold_block=threshold_block,
    threshold_c=threshold_c,
    threshold_method=threshold_method,
)

if apply_enhancement:
    result = s["result"]
    if result is None or result.warped is None:
        st.warning("Create a scan before changing its enhancement.")
    else:
        updated = work(
            lambda: enhance(result.warped, selected_mode, settings)
        )
        if updated is not None:
            result.output = updated
            result.output_quality = analyze_quality(updated)
            result.stages["Enhancement / final"] = resize_longest(
                updated, 1200
            )[0]
            invalidate_derived()

st.markdown(
    """
    <div class="hero">
        <h1>SmartScan</h1>
        <p>Detect. Correct. Enhance. Extract.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

result = s["result"]
valid_scan = result is not None and result.output is not None

if page == "Scan":
    left, right = st.columns([3, 1])

    with left:
        uploaded = st.file_uploader(
            "Drop a document photograph here",
            type=["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"],
        )
        if uploaded and st.button("Scan uploaded image", type="primary"):
            payload = uploaded.getvalue()

            def scan_uploaded():
                return accept_scan(
                    decode_upload(payload),
                    uploaded.name,
                )

            if work(scan_uploaded):
                st.rerun()

    with right:
        st.write("Sample document")
        if st.button("Try sample", use_container_width=True):
            sample = ROOT / "sample_images" / "perspective.png"
            if work(
                lambda: accept_scan(load_image(sample), sample.name)
            ):
                st.rerun()

    with st.expander("Capture with camera"):
        captured = st.camera_input("Photograph your document")
        if captured and st.button("Scan camera image"):
            payload = captured.getvalue()
            if work(
                lambda: accept_scan(
                    decode_upload(payload),
                    "Camera capture",
                )
            ):
                st.rerun()

    if s["source"] is None:
        st.info("Upload a document, capture a photograph, or try the sample.")
    else:
        result = s["result"]
        a, b = st.columns(2)
        with a:
            st.subheader("Original")
            show_image(
                boundary_overlay(
                    s["source"],
                    result.detection.corners,
                ),
                s["source_name"],
            )
        with b:
            st.subheader("Processed scan")
            if result.output is not None:
                show_image(result.output)
            else:
                st.warning(result.detection.message)

        with st.expander(
            "Adjust document corners",
            expanded=result.output is None,
        ):
            h, w = s["source"].shape[:2]
            points = result.detection.corners
            if points is None:
                points = np.float32(
                    [
                        [w * 0.1, h * 0.1],
                        [w * 0.9, h * 0.1],
                        [w * 0.9, h * 0.9],
                        [w * 0.1, h * 0.9],
                    ]
                )

            st.caption(
                "Coordinates refer to the original image. "
                "Adjust the four points and apply the correction."
            )
            with st.form(f"corners_{s['revision']}"):
                columns = st.columns(4)
                edited = []
                labels = ["Top-left", "Top-right", "Bottom-right", "Bottom-left"]
                for index, column in enumerate(columns):
                    with column:
                        st.write(labels[index])
                        x = st.number_input(
                            "X",
                            min_value=0.0,
                            max_value=float(w - 1),
                            value=float(np.clip(points[index][0], 0, w - 1)),
                            key=f"x_{s['revision']}_{index}",
                        )
                        y = st.number_input(
                            "Y",
                            min_value=0.0,
                            max_value=float(h - 1),
                            value=float(np.clip(points[index][1], 0, h - 1)),
                            key=f"y_{s['revision']}_{index}",
                        )
                        edited.append([x, y])

                apply_corners = st.form_submit_button(
                    "Apply corners and correct",
                    type="primary",
                )

            if apply_corners:
                def manual_scan():
                    corners = validate_corners(
                        edited,
                        s["source"].shape,
                    )
                    return accept_scan(
                        s["source"],
                        s["source_name"],
                        corners,
                    )

                if work(manual_scan):
                    st.rerun()

        if result.output is not None:
            a, b, c = st.columns(3)
            if a.button("↶ Rotate left", use_container_width=True):
                rotate_current(False)
                st.rerun()
            if b.button("↷ Rotate right", use_container_width=True):
                rotate_current(True)
                st.rerun()
            if c.button("Save snapshot", use_container_width=True):
                if work(remember_current):
                    st.success("Snapshot saved to history.")

            st.subheader("Before / after")
            position = st.slider(
                "Move the comparison divider",
                0,
                100,
                50,
            )
            before = result.warped
            after = result.output
            if before.ndim == 2:
                before = cv2.cvtColor(before, cv2.COLOR_GRAY2BGR)
            if after.ndim == 2:
                after = cv2.cvtColor(after, cv2.COLOR_GRAY2BGR)

            wipe = after.copy()
            split = int(wipe.shape[1] * position / 100)
            wipe[:, :split] = before[:, :split]
            if 0 < split < wipe.shape[1]:
                cv2.line(
                    wipe,
                    (split, 0),
                    (split, wipe.shape[0] - 1),
                    (96, 220, 70),
                    3,
                )
            show_image(
                wipe,
                "Left: perspective-corrected input · Right: enhanced output",
            )

            with st.expander("Compare all enhancement modes"):
                if st.button("Generate all five modes"):
                    modes = work(
                        lambda: {
                            mode: enhance(result.warped, mode, settings)
                            for mode in MODES
                        }
                    )
                    if modes is not None:
                        s["comparison_modes"] = modes

                if s["comparison_modes"]:
                    chosen = st.selectbox(
                        "Preview mode",
                        list(s["comparison_modes"]),
                    )
                    show_image(s["comparison_modes"][chosen])

            st.subheader("Quality diagnostics")
            quality = result.output_quality
            metrics = st.columns(4)
            metrics[0].metric("Heuristic quality", f"{quality['score']}/100")
            metrics[1].metric("Brightness", quality["brightness"])
            metrics[2].metric("Contrast", quality["contrast"])
            metrics[3].metric(
                "Laplacian variance",
                quality["laplacian_variance"],
            )
            st.caption(quality["methodology"])

            with st.expander("Full input/output quality report"):
                st.json(
                    {
                        "input": result.input_quality,
                        "output": result.output_quality,
                    }
                )
                for suggestion in result.input_quality["suggestions"]:
                    st.write("•", suggestion)

elif page == "Stages":
    st.subheader("Processing stages")
    if result is None:
        st.info("Scan a document first.")
    else:
        selected = st.selectbox("Stage", list(result.stages))
        show_image(result.stages[selected], selected)

        if st.button("Prepare stage download"):
            def make_stage_archive():
                buffer = io.BytesIO()
                with zipfile.ZipFile(
                    buffer,
                    "w",
                    zipfile.ZIP_DEFLATED,
                ) as archive:
                    for index, (name, image) in enumerate(result.stages.items()):
                        archive.writestr(
                            f"{index:02d}_stage.png",
                            image_bytes(image),
                        )
                    archive.writestr(
                        "quality.json",
                        json.dumps(
                            {
                                "input": result.input_quality,
                                "output": result.output_quality,
                                "homography": (
                                    result.homography.tolist()
                                    if result.homography is not None
                                    else None
                                ),
                            },
                            indent=2,
                        ),
                    )
                return buffer.getvalue()

            archive = work(make_stage_archive)
            if archive is not None:
                s["exports"]["stages"] = archive

        if "stages" in s["exports"]:
            st.download_button(
                "Download stages",
                s["exports"]["stages"],
                "smartscan_stages.zip",
                "application/zip",
            )

elif page == "FCV lab":
    st.subheader("Explore computer vision techniques")
    st.caption("These experiments do not change your saved scan.")
    if s["source"] is None:
        st.info("Load an image first.")
    else:
        technique = st.selectbox("Technique", TECHNIQUES)
        if st.button("Run technique", type="primary"):
            output = work(
                lambda: demonstrate(s["source"], technique)
            )
            if output is not None:
                show_image(output, technique)

elif page == "OCR and export":
    st.subheader("Text recognition and downloads")
    if not valid_scan:
        st.info("Create a scan first.")
    else:
        if st.button("Extract text", type="primary"):
            work(current_ocr)

        if s["ocr"] is not None:
            recognized = s["ocr"]
            st.caption(
                f"{len(recognized.words)} words · "
                f"Mean engine confidence {recognized.mean_confidence:.1f}/100"
            )
            st.code(recognized.text or "No text recognized.", language=None)
            st.download_button(
                "Download recognized text",
                recognized.text.encode("utf-8"),
                "smartscan.txt",
                "text/plain",
            )
            st.caption(
                "Proofread the transcript. Engine confidence is not "
                "validated transcription accuracy."
            )

        st.divider()
        format_name = st.selectbox(
            "Output format",
            ["PNG", "JPEG", "Image PDF", "Searchable PDF"],
        )
        signature = (
            s["revision"],
            format_name,
            number_pages,
            language,
            psm,
        )

        if st.button("Prepare download"):
            def prepare_export():
                if format_name == "PNG":
                    return image_bytes(result.output), "smartscan.png", "image/png"
                if format_name == "JPEG":
                    return (
                        image_bytes(result.output, ".jpg"),
                        "smartscan.jpg",
                        "image/jpeg",
                    )
                searchable = format_name == "Searchable PDF"
                recognized = [current_ocr()] if searchable else None
                return (
                    pdf_bytes([result.output], searchable, recognized),
                    "smartscan.pdf",
                    "application/pdf",
                )

            prepared = work(prepare_export)
            if prepared is not None:
                s["exports"]["current"] = (signature, prepared)

        prepared = s["exports"].get("current")
        if prepared and prepared[0] == signature:
            data, filename, mime = prepared[1]
            st.download_button(
                "Download scan",
                data,
                filename,
                mime,
                type="primary",
            )

elif page == "Document pages":
    st.subheader("Build a multipage document")
    identifiers = store.queue_ids()

    if valid_scan and st.button("Add current scan to document"):
        def add_current():
            if len(identifiers) >= 20:
                raise ValueError("The document is limited to 20 pages.")
            identifier = remember_current()
            store.set_queue(identifiers + [identifier])
            return True

        if work(add_current):
            st.rerun()

    if not identifiers:
        st.info("Add scans from the workspace or history.")
    else:
        records = [store.get(identifier) for identifier in identifiers]
        selected = st.selectbox(
            "Document page",
            range(len(records)),
            format_func=lambda i: f"{i + 1:02d} · {records[i]['title']}",
        )
        show_image(store.load(identifiers[selected]))

        a, b, c, d = st.columns(4)
        if a.button("Move up", disabled=selected == 0):
            identifiers[selected - 1], identifiers[selected] = (
                identifiers[selected],
                identifiers[selected - 1],
            )
            store.set_queue(identifiers)
            s["exports"].pop("document", None)
            st.rerun()

        if b.button("Move down", disabled=selected == len(records) - 1):
            identifiers[selected + 1], identifiers[selected] = (
                identifiers[selected],
                identifiers[selected + 1],
            )
            store.set_queue(identifiers)
            s["exports"].pop("document", None)
            st.rerun()

        if c.button("Remove page"):
            identifiers.pop(selected)
            store.set_queue(identifiers)
            s["exports"].pop("document", None)
            st.rerun()

        if d.button("Clear document"):
            store.set_queue([])
            s["exports"].pop("document", None)
            st.rerun()

        searchable = st.checkbox("Searchable document PDF", value=True)
        signature = (
            tuple(identifiers),
            searchable,
            number_pages,
            language,
            psm,
        )

        if st.button("Prepare document PDF", type="primary"):
            def build_document():
                images, recognized = [], []
                for identifier in identifiers:
                    image = store.load(identifier)
                    images.append(image)
                    if searchable:
                        text = store.load_ocr(identifier)
                        if text is None or not text.pdf_bytes:
                            text = recognize(
                                image,
                                language,
                                psm,
                                tesseract_path or None,
                            )
                            store.attach_ocr(identifier, text)
                        recognized.append(text)

                return pdf_bytes(
                    images,
                    searchable,
                    recognized if searchable else None,
                )

            document = work(build_document)
            if document is not None:
                s["exports"]["document"] = (signature, document)

        document = s["exports"].get("document")
        if document and document[0] == signature:
            st.download_button(
                "Download document PDF",
                document[1],
                "smartscan_document.pdf",
                "application/pdf",
            )

elif page == "History":
    st.subheader("Saved scans")
    query = st.text_input("Search document titles or recognized text")
    records = store.list(query)

    if not records:
        st.info("No matching snapshots.")
    else:
        selected = st.selectbox(
            "Snapshot",
            range(len(records)),
            format_func=lambda i: (
                f"{records[i]['title']} · "
                f"{records[i]['created'][:19]} UTC"
            ),
        )
        record = records[selected]
        identifier = record["id"]

        show_image(store.load(identifier))
        st.caption(
            f"{record['width']} × {record['height']} pixels · "
            f"{record['mode']}"
        )

        a, b, c = st.columns(3)
        if a.button("Open snapshot"):
            if work(lambda: restore_snapshot(identifier)):
                st.success("Snapshot loaded. Open Scan to edit it.")

        if b.button("Add snapshot to document"):
            def queue_snapshot():
                identifiers = store.queue_ids()
                if len(identifiers) >= 20:
                    raise ValueError("The document is limited to 20 pages.")
                store.set_queue(identifiers + [identifier])
                return True

            if work(queue_snapshot):
                st.success("Snapshot added to document.")

        confirm_delete = st.checkbox("Confirm snapshot deletion")
        if c.button("Delete snapshot", disabled=not confirm_delete):
            def delete_snapshot():
                store.delete(identifier)
                return True

            if work(delete_snapshot):
                st.rerun()

        st.caption(
            "History contains processed snapshots and OCR. "
            "Original photographs are not copied."
        )

elif page == "Batch":
    st.subheader("Process multiple documents")
    uploads = st.file_uploader(
        "Drop multiple document photographs",
        type=["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"],
        accept_multiple_files=True,
    )
    include_ocr = st.checkbox(
        "Extract text and create searchable PDFs",
        value=True,
    )

    if uploads and st.button("Process batch", type="primary"):
        progress = st.progress(0.0)

        def run_batch():
            with tempfile.TemporaryDirectory(
                prefix="smartscan-web-batch-"
            ) as folder:
                incoming = Path(folder) / "input"
                outgoing = Path(folder) / "output"
                incoming.mkdir()

                paths = []
                for index, uploaded in enumerate(uploads):
                    extension = Path(uploaded.name).suffix.lower()
                    path = incoming / f"{index + 1:03d}{extension}"
                    path.write_bytes(uploaded.getvalue())
                    paths.append(path)

                def update(index, total, message):
                    progress.progress(
                        index / max(total, 1),
                        text=message,
                    )

                rows = process_batch(
                    paths,
                    outgoing,
                    mode=selected_mode,
                    settings=settings,
                    ocr=include_ocr,
                    language=language,
                    psm=psm,
                    binary=tesseract_path or None,
                    store=store,
                    progress=update,
                )

                for index, row in enumerate(rows):
                    row["source"] = uploads[index].name

                (outgoing / "batch_report.json").write_text(
                    json.dumps(rows, indent=2),
                    encoding="utf-8",
                )

                identifiers = store.queue_ids()
                additions = [
                    row["history_id"]
                    for row in rows
                    if row["history_id"]
                ]
                store.set_queue(
                    identifiers + additions[:20 - len(identifiers)]
                )

                buffer = io.BytesIO()
                with zipfile.ZipFile(
                    buffer,
                    "w",
                    zipfile.ZIP_DEFLATED,
                ) as archive:
                    for path in outgoing.rglob("*"):
                        if path.is_file():
                            archive.write(
                                path,
                                path.relative_to(outgoing).as_posix(),
                            )

                return rows, buffer.getvalue()

        completed = work(run_batch)
        if completed is not None:
            s["batch_rows"], s["batch_zip"] = completed

    if s["batch_rows"]:
        st.dataframe(
            [
                {
                    "Document": row["source"],
                    "Status": row["status"],
                    "Details": row["message"],
                }
                for row in s["batch_rows"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if s["batch_zip"] is not None:
        st.download_button(
            "Download batch results",
            s["batch_zip"],
            "smartscan_batch.zip",
            "application/zip",
        )

    if uploads:
        selected = st.selectbox(
            "Open a batch image for manual correction",
            range(len(uploads)),
            format_func=lambda i: uploads[i].name,
        )
        if st.button("Load selected image into Scan"):
            uploaded = uploads[selected]
            payload = uploaded.getvalue()
            if work(
                lambda: accept_scan(
                    decode_upload(payload),
                    uploaded.name,
                )
            ):
                st.success(
                    "Image loaded. Open Scan and adjust its corners."
                )