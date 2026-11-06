"""PySide6 desktop workspace. CV and disk work run on the Qt thread pool."""
from pathlib import Path
import json
import sys
import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool, QPointF, QTimer, QThread, QSettings
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QPolygonF
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QSlider, QScrollArea, QTabWidget,
    QTextBrowser, QMessageBox, QFrame, QSplitter, QProgressBar, QDialog)
from .image_processing import load_image,resize_longest,TECHNIQUES,demonstrate
from .enhancement import MODES,EnhancementSettings,enhance
from .pipeline import scan
from .quality_analysis import analyze_quality
from .perspective_correction import validate_corners
from .export import save_image,save_pdf

STYLE = """
QWidget {background:#111c27; color:#e8edf2; font-family:'Segoe UI',sans-serif; font-size:13px;}
QMainWindow {background:#111c27;}
QLabel#brand {font-size:27px;font-weight:700;color:#f7fbff;}
QLabel#eyebrow {color:#50d6b5;font-size:11px;font-weight:700;}
QLabel#subtle {color:#96a9bb;}
QLabel#paneltitle {font-size:15px;font-weight:600;}
QFrame#card {background:#172633;border:1px solid #2b3d4c;border-radius:10px;}
QPushButton {background:#263b4b;border:1px solid #385164;border-radius:7px;padding:9px 14px;font-weight:600;}
QPushButton:hover {background:#335366;border-color:#50d6b5;}
QPushButton:disabled {color:#617382;background:#1a2935;border-color:#293b49;}
QPushButton#primary {background:#50d6b5;color:#0b2822;border:0;}
QPushButton#primary:hover {background:#78e5c9;}
QComboBox {background:#203341;padding:8px;border:1px solid #385164;border-radius:6px;}
QComboBox QAbstractItemView {background:#203341;selection-background-color:#385164;}
QSlider::groove:horizontal {height:4px;background:#344d60;border-radius:2px;}
QSlider::handle:horizontal {background:#50d6b5;width:13px;margin:-5px 0;border-radius:6px;}
QTabWidget::pane {border:1px solid #2b3d4c;border-radius:7px;}
QTabBar::tab {background:#172633;padding:11px 18px;color:#9db0c1;}
QTabBar::tab:selected {color:#50d6b5;border-bottom:2px solid #50d6b5;}
QTextBrowser {background:#172633;border:0;padding:15px;}
QScrollArea {border:0;} QScrollBar:vertical {width:8px;background:#14232f;}
QScrollBar::handle:vertical {background:#385164;border-radius:4px;min-height:25px;}
QProgressBar {border:0;background:#233a4b;height:5px;} QProgressBar::chunk {background:#50d6b5;}
"""

def qimage(image):
    image=resize_longest(image,1800)[0]
    rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB) if image.ndim==3 else cv2.cvtColor(image,cv2.COLOR_GRAY2RGB)
    rgb=np.ascontiguousarray(rgb)
    return QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy()

class ImageCanvas(QWidget):
    """Fit preview with corner coordinates stored in the original pixel space."""
    pointsChanged=Signal(object)
    def __init__(self,text="Open a document photograph"):
        super().__init__();self.setMinimumSize(250,280)
        self.image=None;self.pix=None;self.points=[];self.editable=False;self.drag=None;self.text=text
    def set_image(self,image,points=None):
        self.image=image;self.pix=QPixmap.fromImage(qimage(image)) if image is not None else None
        self.points=[] if points is None else [list(p) for p in points]
        self.update()
    def geometry_map(self):
        if self.image is None:return 1.,0.,0.
        h,w=self.image.shape[:2];scale=min((self.width()-32)/w,(self.height()-32)/h)
        return scale,(self.width()-w*scale)/2,(self.height()-h*scale)/2
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor('#0d1720'))
        if self.pix is None:
            painter.setPen(QColor('#8b9fb2'));painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,self.text);return
        s,x,y=self.geometry_map();h,w=self.image.shape[:2]
        from PySide6.QtCore import QRectF
        painter.drawPixmap(QRectF(x,y,w*s,h*s),self.pix,QRectF(self.pix.rect()))
        if self.points:
            pts=[QPointF(x+p[0]*s,y+p[1]*s) for p in self.points]
            painter.setPen(QPen(QColor('#50d6b5'),2))
            if len(pts)==4:painter.drawPolygon(QPolygonF(pts))
            else:painter.drawPolyline(QPolygonF(pts))
            for i,p in enumerate(pts):
                painter.setBrush(QColor('#50d6b5'));painter.drawEllipse(p,8,8)
                painter.setPen(QColor('#081f19'));painter.drawText(int(p.x())-3,int(p.y())+4,str(i+1));painter.setPen(QPen(QColor('#50d6b5'),2))
    def mousePressEvent(self,event):
        if not self.editable or self.image is None:return
        s,x,y=self.geometry_map();pos=event.position();h,w=self.image.shape[:2]
        if not (x<=pos.x()<=x+w*s and y<=pos.y()<=y+h*s):return
        for i,p in enumerate(self.points):
            if np.hypot(x+p[0]*s-pos.x(),y+p[1]*s-pos.y())<17:self.drag=i;return
        if len(self.points)<4:
            self.points.append([(pos.x()-x)/s,(pos.y()-y)/s]);self.pointsChanged.emit(self.points);self.update()
    def mouseMoveEvent(self,event):
        if self.drag is None:return
        s,x,y=self.geometry_map();h,w=self.image.shape[:2]
        self.points[self.drag]=[float(np.clip((event.position().x()-x)/s,0,w-1)),float(np.clip((event.position().y()-y)/s,0,h-1))]
        self.update()
    def mouseReleaseEvent(self,event):
        if self.drag is not None:self.pointsChanged.emit(self.points)
        self.drag=None

class Signals(QObject):
    success=Signal(object)
    error=Signal(str)
    done=Signal()

class Task(QRunnable):
    def __init__(self,function):super().__init__();self.function=function;self.signals=Signals()
    def run(self):
        try:self.signals.success.emit(self.function())
        except Exception as exc:self.signals.error.emit(str(exc))
        finally:self.signals.done.emit()

class CameraThread(QThread):
    frame=Signal(object)
    error=Signal(str)
    def run(self):
        cap=cv2.VideoCapture(0)
        try:
            if not cap.isOpened():self.error.emit('No webcam available. Check camera permissions or upload an image.');return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
            while not self.isInterruptionRequested():
                ok,frame=cap.read()
                if not ok:self.error.emit('Cannot read from webcam.');break
                self.frame.emit(frame);self.msleep(70)
        finally:cap.release()

class CameraDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent);self.setWindowTitle('Capture document');self.resize(850,650);self.captured=None;self.latest=None;self.failed=False
        layout=QVBoxLayout(self);self.canvas=ImageCanvas('Starting camera...');layout.addWidget(self.canvas)
        self.message=QLabel('Place the full page in view, focus, then capture.');layout.addWidget(self.message)
        self.button=QPushButton('Capture frame');self.button.setEnabled(False);layout.addWidget(self.button);self.button.clicked.connect(self.capture)
        self.thread=CameraThread(self);self.thread.frame.connect(self.show_frame);self.thread.error.connect(self.error);self.thread.finished.connect(self.stopped);self.thread.start()
    def show_frame(self,frame):self.latest=frame;self.canvas.set_image(frame);self.button.setEnabled(True)
    def error(self,text):self.message.setText(text);self.failed=True;self.button.setEnabled(False)
    def capture(self):
        if self.latest is not None:self.captured=self.latest.copy();self.thread.requestInterruption();self.button.setEnabled(False)
    def stopped(self):
        if self.captured is not None:self.accept()
        elif not self.failed:self.reject()
    def closeEvent(self,event):
        if self.thread.isRunning():self.thread.requestInterruption();self.thread.finished.connect(self.close);event.ignore()
        else:super().closeEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('SmartScan | Document studio');self.resize(1460,940);self.setMinimumSize(1060,740)
        self.image=None;self.result=None;self.pages=[];self.busy=False;self.settings=QSettings('SmartScan','DocumentStudio');self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.tasks=[]
        self.setAcceptDrops(True);self.setStyleSheet(STYLE)
        root=QWidget();outer=QVBoxLayout(root);outer.setContentsMargins(24,18,24,14);outer.setSpacing(14);self.setCentralWidget(root)
        header=QHBoxLayout();brand=QVBoxLayout();tag=QLabel('FCV LAB  /  DOCUMENT STUDIO');tag.setObjectName('eyebrow');brand.addWidget(tag)
        title=QLabel('SmartScan');title.setObjectName('brand');brand.addWidget(title);header.addLayout(brand);header.addStretch()
        self.load_button=QPushButton('Open image');self.load_button.setObjectName('primary');self.load_button.clicked.connect(self.open_file);header.addWidget(self.load_button)
        self.camera_button=QPushButton('Webcam');self.camera_button.clicked.connect(self.capture);header.addWidget(self.camera_button)
        self.demo_button=QPushButton('Try sample');self.demo_button.clicked.connect(self.demo);header.addWidget(self.demo_button);outer.addLayout(header)
        self.subtitle=QLabel('Turn a photograph into a clean scan. Drop an image here to start.');self.subtitle.setObjectName('subtle');outer.addWidget(self.subtitle)
        body=QHBoxLayout();body.setSpacing(18);outer.addLayout(body,1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFixedWidth(282);panel=QWidget();controls=QVBoxLayout(panel);controls.setContentsMargins(0,0,8,0);controls.setSpacing(11);scroll.setWidget(panel);body.addWidget(scroll)
        def section(text):
            label=QLabel(text);label.setObjectName('eyebrow');controls.addWidget(label)
        section('01  BOUNDARY & GEOMETRY')
        self.detect_button=QPushButton('Detect automatically');self.detect_button.clicked.connect(self.process);controls.addWidget(self.detect_button)
        self.manual_button=QPushButton('Edit four corners');self.manual_button.clicked.connect(self.manual);controls.addWidget(self.manual_button)
        self.clear_button=QPushButton('Clear corner points');self.clear_button.clicked.connect(self.clear_corners);controls.addWidget(self.clear_button)
        self.apply_button=QPushButton('Apply corners and correct');self.apply_button.clicked.connect(self.apply_manual);controls.addWidget(self.apply_button)
        hint=QLabel('In edit mode, click four corners or drag the markers. Check the boundary before saving.');hint.setWordWrap(True);hint.setObjectName('subtle');controls.addWidget(hint)
        section('02  SCAN APPEARANCE')
        self.mode=QComboBox();self.mode.addItems(MODES);self.mode.setCurrentText('Enhanced document');controls.addWidget(self.mode)
        self.sliders={};self.value_labels={}
        for key,title,low,high,default in [('brightness','Brightness',-80,80,0),('contrast','Contrast ×100',50,180,100),('gamma','Gamma ×100',40,220,100),('sharpening','Sharpen ×100',0,100,25),('denoise','Denoise',0,3,1),('threshold_block','Threshold window (odd)',3,101,31),('threshold_c','Threshold offset C',-10,30,11)]:
            row=QHBoxLayout();row.addWidget(QLabel(title));row.addStretch();value=QLabel(str(default));value.setObjectName('subtle');row.addWidget(value);controls.addLayout(row)
            slider=QSlider(Qt.Orientation.Horizontal);slider.setRange(low,high);slider.setValue(default);slider.valueChanged.connect(lambda v,label=value:label.setText(str(v)));controls.addWidget(slider);self.sliders[key]=slider;self.value_labels[key]=value
        self.threshold_method=QComboBox();self.threshold_method.addItems(['Adaptive','Otsu']);controls.addWidget(self.threshold_method)
        self.enhance_button=QPushButton('Update enhancement');self.enhance_button.setObjectName('primary');self.enhance_button.clicked.connect(self.update_enhancement);controls.addWidget(self.enhance_button)
        self.reset_button=QPushButton('Reset scan');self.reset_button.clicked.connect(self.reset);controls.addWidget(self.reset_button)
        section('03  EXPORT')
        self.export_button=QPushButton('Save image / PDF');self.export_button.clicked.connect(self.export_current);controls.addWidget(self.export_button)
        self.stages_button=QPushButton('Save processing stages');self.stages_button.clicked.connect(self.export_stages);controls.addWidget(self.stages_button)
        self.add_page_button=QPushButton('Add scan to PDF queue');self.add_page_button.clicked.connect(self.add_page);controls.addWidget(self.add_page_button)
        self.queue_label=QLabel('0 pages in queue');self.queue_label.setObjectName('subtle');controls.addWidget(self.queue_label)
        self.pdf_button=QPushButton('Export queued PDF');self.pdf_button.clicked.connect(self.export_queue);controls.addWidget(self.pdf_button)
        self.clear_queue_button=QPushButton('Clear PDF queue');self.clear_queue_button.clicked.connect(self.clear_queue);controls.addWidget(self.clear_queue_button)
        section('RECENT IMAGES')
        self.recent=QComboBox();self.recent.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.recent.setMinimumContentsLength(12);self.recent.setMaximumWidth(250);self.refresh_recent();controls.addWidget(self.recent)
        self.recent_button=QPushButton('Open selected recent');self.recent_button.clicked.connect(self.open_recent);controls.addWidget(self.recent_button);controls.addStretch()
        self.tabs=QTabWidget();body.addWidget(self.tabs,1)
        workspace=QWidget();wl=QVBoxLayout(workspace);wl.setSpacing(10)
        row=QHBoxLayout();left=QLabel('SOURCE  /  BOUNDARY');left.setObjectName('eyebrow');row.addWidget(left);row.addStretch();right=QLabel('SCAN  /  OUTPUT');right.setObjectName('eyebrow');row.addWidget(right);wl.addLayout(row)
        split=QSplitter();self.source=ImageCanvas('01\nOpen a document photograph\nor choose Try sample');self.output=ImageCanvas('02\nYour corrected scan appears here');split.addWidget(self.source);split.addWidget(self.output);split.setSizes([500,500]);wl.addWidget(split,1)
        self.info=QLabel('All processing runs locally. PNG, JPEG, TIFF, BMP and WebP input.');self.info.setWordWrap(True);self.info.setObjectName('subtle');wl.addWidget(self.info);self.tabs.addTab(workspace,'Workspace')
        stages=QWidget();sl=QVBoxLayout(stages);self.stage_choice=QComboBox();self.stage_choice.currentTextChanged.connect(self.show_stage);sl.addWidget(self.stage_choice);self.stage_canvas=ImageCanvas('Run detection to inspect real processing stages');sl.addWidget(self.stage_canvas,1);self.tabs.addTab(stages,'Processing stages')
        lab=QWidget();ll=QVBoxLayout(lab);labrow=QHBoxLayout();self.technique=QComboBox();self.technique.addItems(TECHNIQUES);labrow.addWidget(self.technique,1);self.lab_button=QPushButton('Run technique');self.lab_button.clicked.connect(self.run_lab);labrow.addWidget(self.lab_button);ll.addLayout(labrow)
        self.lab_canvas=ImageCanvas('Explore filters, histograms and segmentation independently');ll.addWidget(self.lab_canvas,1);note=QLabel('Experiments use the source image at up to 1200 px. They do not change your final scan.');note.setObjectName('subtle');ll.addWidget(note);self.tabs.addTab(lab,'FCV technique lab')
        modes=QWidget();ml=QVBoxLayout(modes);self.compare_button=QPushButton('Generate all five modes');self.compare_button.clicked.connect(self.compare_modes);ml.addWidget(self.compare_button);self.compare_choice=QComboBox();self.compare_choice.currentTextChanged.connect(self.show_comparison);ml.addWidget(self.compare_choice);self.compare_canvas=ImageCanvas('Compare all presets using the same corrected page');ml.addWidget(self.compare_canvas,1);self.comparisons={};self.tabs.addTab(modes,'Mode comparison')
        self.quality=QTextBrowser();self.quality.setHtml('<h2>Quality diagnostics</h2><p>Open an image to inspect brightness, contrast, focus, noise and resolution.</p><p>The 0–100 score is an educational heuristic, not a validated readability measurement.</p>');self.tabs.addTab(self.quality,'Quality report')
        self.progress=QProgressBar();self.progress.setRange(0,1);self.progress.setValue(0);self.progress.setFixedHeight(4);outer.addWidget(self.progress)
        self.status=QLabel('Ready  •  Offline scanning  •  No account required');self.status.setObjectName('subtle');outer.addWidget(self.status)
        self.actions=[self.load_button,self.camera_button,self.demo_button,self.detect_button,self.manual_button,self.clear_button,self.apply_button,self.enhance_button,self.reset_button,self.export_button,self.stages_button,self.add_page_button,self.pdf_button,self.clear_queue_button,self.lab_button,self.compare_button,self.recent_button]
        self.sync_actions()
    def refresh_recent(self):
        self.recent.clear();self.recent.addItems(self.settings.value('recent',[],list))
    def sync_actions(self):
        for button in self.actions:button.setEnabled(not self.busy)
        if not self.busy:
            for b in [self.detect_button,self.manual_button,self.clear_button,self.apply_button,self.reset_button,self.lab_button]:b.setEnabled(self.image is not None)
            valid=self.result is not None and self.result.output is not None
            for b in [self.enhance_button,self.export_button,self.stages_button,self.add_page_button,self.compare_button]:b.setEnabled(valid)
            self.pdf_button.setEnabled(bool(self.pages));self.clear_queue_button.setEnabled(bool(self.pages));self.recent_button.setEnabled(self.recent.count()>0)
        self.source.editable=self.source.editable and not self.busy
    def run_task(self,text,function,callback):
        if self.busy:return
        self.busy=True;self.sync_actions();self.status.setText(text);self.progress.setRange(0,0)
        task=Task(function);self.tasks.append(task)
        task.signals.success.connect(callback);task.signals.error.connect(self.error)
        task.signals.done.connect(lambda:self.task_done(task));self.pool.start(task)
    def task_done(self,task):
        self.busy=False;self.progress.setRange(0,1);self.progress.setValue(1);self.tasks.remove(task);self.sync_actions()
    def error(self,text):self.status.setText('Action could not be completed');QMessageBox.warning(self,'SmartScan',text)
    def get_settings(self):
        d={k:v.value() for k,v in self.sliders.items()}
        for k in ['contrast','gamma','sharpening']:d[k]/=100
        d['threshold_block']|=1;d['threshold_method']=self.threshold_method.currentText()
        return EnhancementSettings(**d)
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Open document photograph','','Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')
        if path:self.open_path(path)
    def open_path(self,path):
        if self.busy:return
        def loaded(image):
            self.set_source(image,Path(path).name)
            recent=self.settings.value('recent',[],list);recent=[str(path)]+[p for p in recent if p!=str(path)];self.settings.setValue('recent',recent[:8]);self.refresh_recent()
            QTimer.singleShot(0,self.process)
        self.run_task('Opening photograph…',lambda:load_image(path),loaded)
    def set_source(self,image,name='Webcam capture'):
        self.image=image;self.result=None;self.source.editable=False;self.source.set_image(image);self.output.set_image(None);self.stage_choice.clear();self.stage_canvas.set_image(None);self.lab_canvas.set_image(None);self.comparisons={};self.compare_choice.clear();self.compare_canvas.set_image(None)
        self.subtitle.setText(f'{name}   /   {image.shape[1]} × {image.shape[0]} pixels');self.tabs.setCurrentIndex(0);self.status.setText('Photograph loaded');self.sync_actions()
    def demo(self):
        path=Path(__file__).resolve().parents[1]/'sample_images'/'perspective.png'
        if path.exists():self.open_path(path)
        else:self.error('Sample is missing. Run python tools/generate_samples.py from the project folder.')
    def open_recent(self):
        if self.recent.currentText():self.open_path(self.recent.currentText())
    def process(self,corners=None):
        if self.image is None or self.busy:return
        # clicked(bool) is not a manual-corner array.
        if isinstance(corners,bool):corners=None
        image=self.image;mode=self.mode.currentText();settings=self.get_settings()
        self.run_task('Detecting page and preparing scan…',lambda:scan(image,mode,settings,corners),self.accept_result)
    def accept_result(self,result):
        self.result=result;self.source.set_image(self.image,result.detection.corners);self.source.editable=False;self.output.set_image(result.output)
        self.stage_choice.clear();self.stage_choice.addItems(result.stages);self.stage_choice.setCurrentText('Document boundary')
        confidence='manual' if result.detection.confidence is None else f'{result.detection.confidence*100:.0f}% heuristic confidence'
        self.info.setText(f'{result.detection.message}  {result.detection.strategy} · {confidence} · {result.elapsed_ms:.0f} ms')
        self.status.setText('Scan ready — inspect the corners and choose an enhancement.' if result.output is not None else 'Boundary not found — use Edit four corners, then Apply corners & correct.')
        self.render_quality();self.comparisons={};self.compare_choice.clear();self.compare_canvas.set_image(None)
    def manual(self):
        if self.image is not None:self.source.editable=True;self.tabs.setCurrentIndex(0);self.status.setText('Edit mode: drag markers, or clear and click four document corners. Then Apply corners & correct.')
    def clear_corners(self):self.source.points=[];self.manual();self.source.update()
    def apply_manual(self):
        try:corners=validate_corners(self.source.points,self.image.shape)
        except ValueError as exc:self.error(str(exc));return
        self.process(corners)
    def update_enhancement(self):
        if self.result is None or self.result.warped is None:return
        warped=self.result.warped;mode=self.mode.currentText();settings=self.get_settings()
        def compute():
            out=enhance(warped,mode,settings)
            return out,analyze_quality(out)
        def accept(value):
            out,quality=value;self.result.output=out;self.result.output_quality=quality;self.result.stages['Enhancement / final']=resize_longest(out,1200)[0];self.output.set_image(out);self.show_stage(self.stage_choice.currentText());self.render_quality();self.status.setText(f'{mode} applied — {out.shape[1]} × {out.shape[0]} pixels')
            self.comparisons={};self.compare_choice.clear();self.compare_canvas.set_image(None)
        self.run_task('Updating enhancement…',compute,accept)
    def reset(self):
        defaults=EnhancementSettings()
        for k,slider in self.sliders.items():slider.setValue(int(getattr(defaults,k)*(100 if k in ['contrast','gamma','sharpening'] else 1)))
        self.mode.setCurrentText('Enhanced document');self.threshold_method.setCurrentText('Adaptive');self.process()
    def show_stage(self,name):
        if self.result is not None and name in self.result.stages:self.stage_canvas.set_image(self.result.stages[name])
    def run_lab(self):
        if self.image is not None:
            image=self.image;technique=self.technique.currentText()
            self.run_task('Running FCV experiment…',lambda:demonstrate(image,technique),lambda im:(self.lab_canvas.set_image(im),self.status.setText('Technique completed on source image')))
    def compare_modes(self):
        if self.result is None or self.result.warped is None:return
        warped=self.result.warped;s=self.get_settings()
        def accept(result):
            self.comparisons=result;self.compare_choice.clear();self.compare_choice.addItems(result);self.status.setText('Five enhancement modes ready for comparison')
        self.run_task('Comparing five enhancement modes…',lambda:{mode:enhance(warped,mode,s) for mode in MODES},accept)
    def show_comparison(self,name):
        if name in self.comparisons:self.compare_canvas.set_image(self.comparisons[name])
    def render_quality(self):
        if self.result is None:return
        a=self.result.input_quality;b=self.result.output_quality
        fields=[('Resolution','width'),('Brightness / 255','brightness'),('Contrast (std dev)','contrast'),('Laplacian variance','laplacian_variance'),('Flat-region noise MAD','noise_mad')]
        rows=''
        for label,key in fields:
            def value(q):return f"{q['width']} × {q['height']}" if key=='width' else str(q[key])
            rows+=f'<tr><td style="padding:10px">{label}</td><td>{value(a)}</td><td>{value(b) if b else "—"}</td></tr>'
        suggestions='<br>'.join(a['suggestions']) or 'No strong acquisition warning detected; inspect the text visually.'
        perspective=a['perspective_asymmetry'];perspective='unavailable' if perspective is None else f'{perspective:.3f}'
        self.quality.setHtml(f'<h1>Quality diagnostics</h1><p style="color:#50d6b5;font-size:24px">Input {a["score"]}/100 · {a["classification"]}</p><p style="font-size:22px">Output {str(b["score"])+"/100 · "+b["classification"] if b else "Awaiting a boundary"}</p><table width="100%" cellspacing="0"><tr><th align="left">Metric</th><th align="left">Input</th><th align="left">Output</th></tr>{rows}</table><h3>Acquisition suggestions</h3><p>{suggestions}</p><p>Opposite-edge asymmetry: {perspective}. This is a shape proxy, not a camera-pose estimate.</p><h3>How the score works</h3><p>{a["methodology"]}</p><p>Whole-photo input includes the background; the output contains only the page. Scores are not directly comparable ground-truth measures. Manual boundaries have no automatic confidence score.</p>')
    def export_current(self):
        if self.result is None or self.result.output is None:return
        path,selected=QFileDialog.getSaveFileName(self,'Save current scan',str(Path(self.settings.value('output_dir',str(Path.home())))/'smartscan.png'),'PNG (*.png);;JPEG (*.jpg);;PDF (*.pdf)')
        if not path:return
        suffix='.pdf' if 'PDF' in selected else '.jpg' if 'JPEG' in selected else '.png'
        if Path(path).suffix.lower() not in ['.png','.jpg','.jpeg','.pdf']:path+=suffix
        im=self.result.output.copy();self.settings.setValue('output_dir',str(Path(path).parent))
        self.run_task('Saving scan…',lambda:save_pdf([im],path) if Path(path).suffix.lower()=='.pdf' else save_image(im,path),lambda p:self.status.setText(f'Saved {p}'))
    def export_stages(self):
        directory=QFileDialog.getExistingDirectory(self,'Choose processing-stage output directory')
        if not directory or self.result is None:return
        stages=dict(self.result.stages)
        quality={'input':self.result.input_quality,'output':self.result.output_quality,'strategy':self.result.detection.strategy,'corners':self.result.detection.corners.tolist() if self.result.detection.corners is not None else None,'homography':self.result.homography.tolist() if self.result.homography is not None else None}
        def write():
            for i,(name,im) in enumerate(stages.items()):save_image(im,Path(directory)/f'{i:02d}_{name.lower().replace(" / ","_").replace(" ","_")}.png')
            (Path(directory)/'quality.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
            return directory
        self.run_task('Saving processing stages…',write,lambda p:self.status.setText(f'Saved stages and quality report to {p}'))
    def add_page(self):
        if self.result is not None and self.result.output is not None:
            if len(self.pages)>=20:self.error('The in-memory PDF queue is limited to 20 pages. Export and clear it first.');return
            self.pages.append(self.result.output.copy());self.queue_label.setText(f'{len(self.pages)} pages in queue');self.sync_actions();self.status.setText('Current scan added to PDF queue')
    def clear_queue(self):self.pages=[];self.queue_label.setText('0 pages in queue');self.sync_actions()
    def export_queue(self):
        path,_=QFileDialog.getSaveFileName(self,'Export queued PDF','smartscan_pages.pdf','PDF (*.pdf)')
        if path:
            if not path.lower().endswith('.pdf'):path+='.pdf'
            pages=list(self.pages);self.run_task('Exporting multipage PDF…',lambda:save_pdf(pages,path),lambda p:self.status.setText(f'Saved {len(pages)} pages to {p}'))
    def capture(self):
        dialog=CameraDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted and dialog.captured is not None:self.set_source(dialog.captured);self.process()
    def dragEnterEvent(self,event):
        if not self.busy and event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if urls and urls[0].isLocalFile():self.open_path(urls[0].toLocalFile())
    def closeEvent(self,event):
        if self.busy:self.status.setText('Wait for the current operation to finish before closing.');event.ignore()
        else:super().closeEvent(event)

def launch():
    app=QApplication.instance() or QApplication(sys.argv)
    from .advanced_gui import AdvancedWindow
    window=AdvancedWindow();window.show()
    return app.exec()
