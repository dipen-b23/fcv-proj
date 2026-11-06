"""Exercise the shipping GUI with real OCR, disk history, PDF and batch workflows."""
import time
from pathlib import Path
import cv2,numpy as np,pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPoint,QMimeData,QUrl
from PySide6.QtGui import QDropEvent
from pypdf import PdfReader
from src.advanced_gui import AdvancedWindow
from src.image_processing import load_image
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def idle(app,window,timeout=40):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        app.processEvents();QTest.qWait(10)
        if not window.busy:
            assert not window.test_errors,window.test_errors
            return
    raise AssertionError('GUI worker did not complete')

@pytest.fixture
def window(app):
    window=AdvancedWindow();window.test_errors=[];window.error=window.test_errors.append;window.show();app.processEvents()
    yield window
    idle(app,window);window.close();app.processEvents()

def scan_image(app,window):
    window.set_source(load_image(ROOT/'sample_images'/'perspective.png'),'perspective.png');window.process();idle(app,window)
    assert window.result.output is not None

def test_ocr_rotate_history_and_queue(app,window,tmp_path):
    scan_image(app,window);assert len(window.history_store.list())==1
    window.ocr_psm.setCurrentIndex(0);window.extract_text();idle(app,window)
    assert window.ocr_result is not None and 'SMARTSCAN' in window.ocr_text.toPlainText()
    window.copy_text();assert 'SMARTSCAN' in QApplication.clipboard().text()
    window.add_page();idle(app,window);assert len(window.pages)==1
    before=window.result.output.copy();H=window.result.homography.copy()
    window.rotate_current();idle(app,window);assert window.ocr_result is None
    assert np.array_equal(window.result.output,cv2.rotate(before,cv2.ROTATE_90_CLOCKWISE))
    window.rotate_current(False);idle(app,window);assert np.array_equal(window.result.output,before) and np.allclose(window.result.homography,H)
    window.add_page();idle(app,window);assert len(window.pages)==2
    ids=list(window.pages);window.page_list.setCurrentRow(1);window.move_page(-1);assert window.pages==ids[::-1]
    window.export_queue_to(tmp_path/'document.pdf',True);idle(app,window)
    reader=PdfReader(tmp_path/'document.pdf');assert len(reader.pages)==2 and all('SMARTSCAN' in page.extract_text() for page in reader.pages)
    assert 'Page 2 of 2' in reader.pages[1].extract_text()
    restored=AdvancedWindow();restored.test_errors=[];restored.error=restored.test_errors.append
    assert restored.pages==window.pages
    restored.history_table.selectRow(0);restored.open_history();idle(app,restored);assert restored.result.output is not None
    restored.close();window.page_list.setCurrentRow(0);window.remove_page();assert len(window.pages)==1

def test_batch_and_manual_failure(app,window,tmp_path):
    paths=[str(ROOT/'sample_images'/'normal.png'),str(ROOT/'sample_images'/'no_document.png')]
    window.start_batch(paths,tmp_path/'batch');idle(app,window)
    assert [r['status'] for r in window.batch_rows]==['saved','manual_required']
    assert len(window.pages)==1 and Path(window.batch_rows[0]['pdf']).exists()
    window.open_batch_row(1)
    # open_path schedules automatic detection after the decoding worker.
    until=time.monotonic()+30
    while time.monotonic()<until:
        app.processEvents();QTest.qWait(20)
        if not window.busy and window.result is not None:break
    assert window.result.output is None and window.manual_button.isEnabled()

def test_wipe_slider_and_stale_ocr(app,window):
    scan_image(app,window);assert window.wipe_canvas.before is not None
    window.tabs.setCurrentIndex(window.wipe_tab_index);app.processEvents()
    window.wipe_slider.setValue(20);assert window.wipe_canvas.position==20
    rect=window.wipe_canvas.rect_for_image();pos=QPoint(round(rect.left()+rect.width()*.75),round(rect.center().y()))
    QTest.mouseClick(window.wipe_canvas,Qt.MouseButton.LeftButton,pos=pos);assert 72<=window.wipe_slider.value()<=77
    window.extract_text();idle(app,window);assert window.ocr_result is not None
    window.sliders['brightness'].setValue(10);window.update_enhancement();idle(app,window);assert window.ocr_result is None and not window.ocr_text.toPlainText()

def test_multiple_file_drop_routes_to_batch(app,window):
    calls=[];window.start_batch=lambda paths:calls.append(paths)
    data=QMimeData();data.setUrls([QUrl.fromLocalFile(str(ROOT/'sample_images'/'normal.png')),QUrl.fromLocalFile(str(ROOT/'sample_images'/'tilted.png'))])
    event=QDropEvent(QPoint(20,20),Qt.DropAction.CopyAction,data,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    window.dropEvent(event);assert len(calls)==1 and len(calls[0])==2


def test_searchable_export_also_updates_history(app,window,tmp_path):
    scan_image(app,window);assert window.ocr_result is None
    window.export_current_to(tmp_path/'direct.pdf',True);idle(app,window)
    assert window.ocr_result is not None
    assert window.history_store.list('SMARTSCAN')
    assert 'SMARTSCAN' in PdfReader(tmp_path/'direct.pdf').pages[0].extract_text()
