"""Offscreen Qt integration exercises real widgets and the actual worker pipeline."""
import time
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPoint
from src.gui import MainWindow,ImageCanvas

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def wait_idle(app,window,timeout=25):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.processEvents();QTest.qWait(10)
        if not window.busy:return
    raise AssertionError('Background operation timed out')

def test_gui_end_to_end(app,image,tmp_path):
    window=MainWindow();window.show();app.processEvents()
    window.set_source(image,'Integration fixture');window.process()
    # Event loop remains active while the background scanner runs.
    ticks=[]
    from PySide6.QtCore import QTimer
    timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(10)
    wait_idle(app,window);timer.stop()
    assert ticks and window.result.output is not None
    assert window.source.pix is not None and window.output.pix is not None
    assert window.stage_choice.count()>=9
    window.mode.setCurrentText('Black-and-white');window.update_enhancement();wait_idle(app,window)
    assert window.result.output.ndim==2
    window.manual();assert window.source.editable
    window.apply_manual();wait_idle(app,window);assert window.result.detection.strategy=='Manual corners'
    window.compare_modes();wait_idle(app,window);assert len(window.comparisons)==5
    window.run_lab();wait_idle(app,window);assert window.lab_canvas.pix is not None
    window.add_page();assert len(window.pages)==1
    window.clear_queue();assert not window.pages
    window.tabs.setCurrentIndex(0);window.grab().save(str(tmp_path/'gui.png'))
    window.close();app.processEvents()

def test_manual_click_mapping(app,image):
    canvas=ImageCanvas();canvas.resize(900,700);canvas.set_image(image);canvas.editable=True;canvas.show();app.processEvents()
    s,x,y=canvas.geometry_map()
    for px,py in [[390,150],[1030,65],[1140,980],[230,1030]]:
        QTest.mouseClick(canvas,Qt.MouseButton.LeftButton,pos=QPoint(round(x+px*s),round(y+py*s)))
    assert len(canvas.points)==4
    assert abs(canvas.points[0][0]-390)<3
    # Drag an existing marker and verify that coordinates move, without adding a point.
    pos=QPoint(round(x+390*s),round(y+150*s))
    QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=pos)
    QTest.mouseMove(canvas,pos+QPoint(10,10));QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=pos+QPoint(10,10))
    assert canvas.points[0][0]>390 and len(canvas.points)==4
    canvas.close()
