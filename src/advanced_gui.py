"""SmartScan's OCR, page management, history, batch and comparison workspaces."""
from pathlib import Path
from datetime import datetime
import threading,io
import cv2,numpy as np
from PySide6.QtCore import Qt,QTimer,Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QSlider,
    QFileDialog,QPlainTextEdit,QLineEdit,QCheckBox,QListWidget,QTableWidget,QTableWidgetItem,
    QHeaderView,QSplitter,QApplication,QAbstractItemView)
from .gui import MainWindow as BaseWindow,ImageCanvas,Task
from .gui_widgets import ComparisonCanvas
from .history import HistoryStore
from .ocr import recognize,available_languages,find_tesseract
from .batch import process_batch
from .pipeline import scan,ScanResult
from .document_detection import Detection
from .image_processing import resize_longest
from .quality_analysis import analyze_quality
from .export import save_image,save_pdf,save_text

class AdvancedWindow(BaseWindow):
    batchProgress=Signal(int,int,str)
    def __init__(self):
        super().__init__();self.setWindowTitle('SmartScan 2 | Document and OCR studio')
        self.history_store=HistoryStore();self.pages=self.history_store.queue_ids();self.current_history_id=None
        self.ocr_result=None;self.source_name='Document';self.cancel_event=threading.Event();self.batch_rows=[]
        self.tabs.setUsesScrollButtons(True)
        self.batchProgress.connect(self.batch_progress)
        self.build_ocr_tab();self.build_pages_tab();self.build_history_tab();self.build_batch_tab();self.build_wipe_tab()
        for index,label in enumerate(['Workspace','Stages','FCV lab','Modes','Quality','OCR / text','Pages','History','Batch','Before / after']):self.tabs.setTabText(index,label)
        row=QHBoxLayout();self.rotate_left_button=QPushButton('Rotate left');self.rotate_right_button=QPushButton('Rotate right')
        self.rotate_left_button.clicked.connect(lambda:self.rotate_current(False));self.rotate_right_button.clicked.connect(lambda:self.rotate_current(True));row.addWidget(self.rotate_left_button);row.addWidget(self.rotate_right_button)
        self.tabs.widget(0).layout().insertLayout(1,row)
        self.actions += [self.rotate_left_button,self.rotate_right_button,self.ocr_button,self.ocr_setup_button,self.copy_text_button,self.save_text_button,self.searchable_button,self.choose_engine_button,self.queue_up_button,self.queue_down_button,self.queue_remove_button,self.queue_preview_button,self.queue_ocr_button,self.snapshot_button,self.history_open_button,self.history_queue_button,self.history_delete_button,self.batch_button]
        self.pdf_button.setText('Export document PDF');self.add_page_button.setText('Add scan to document');self.clear_queue_button.setText('Clear document pages')
        self.refresh_pages();self.refresh_history();self.sync_actions()
    def make_button(self,label,slot,row):
        button=QPushButton(label);button.clicked.connect(slot);row.addWidget(button);return button
    def build_ocr_tab(self):
        widget=QWidget();layout=QVBoxLayout(widget)
        note=QLabel('Extract printed text locally with Tesseract. Recognition can make mistakes; proofread important text.');note.setWordWrap(True);note.setObjectName('subtle');layout.addWidget(note)
        engine=QHBoxLayout();self.engine_path=QLineEdit(str(self.settings.value('tesseract_cmd','')));self.engine_path.setPlaceholderText('Automatic detection, or full path to tesseract.exe');engine.addWidget(self.engine_path,1);self.choose_engine_button=self.make_button('Browse executable',self.choose_engine,engine);layout.addLayout(engine)
        options=QHBoxLayout();options.addWidget(QLabel('Language'));self.ocr_language=QComboBox();self.ocr_language.setEditable(True);self.ocr_language.addItem('eng');options.addWidget(self.ocr_language)
        options.addWidget(QLabel('Layout'));self.ocr_psm=QComboBox()
        for text,value in [('Automatic page',3),('Single text block',6),('Sparse text',11)]:self.ocr_psm.addItem(text,value)
        options.addWidget(self.ocr_psm);self.ocr_setup_button=self.make_button('Check OCR setup',self.check_ocr_setup,options);options.addStretch();layout.addLayout(options)
        self.ocr_status=QLabel('Tesseract must be installed once. See docs/OCR_SETUP.md for Windows, Linux and macOS.');self.ocr_status.setWordWrap(True);self.ocr_status.setObjectName('subtle');layout.addWidget(self.ocr_status)
        buttons=QHBoxLayout();self.ocr_button=self.make_button('Extract text',self.extract_text,buttons);self.ocr_button.setObjectName('primary');self.copy_text_button=self.make_button('Copy text',self.copy_text,buttons);self.save_text_button=self.make_button('Save TXT',self.export_text,buttons);self.searchable_button=self.make_button('Save searchable PDF',self.export_searchable,buttons);buttons.addStretch();layout.addLayout(buttons)
        self.ocr_text=QPlainTextEdit();self.ocr_text.setReadOnly(True);self.ocr_text.setPlaceholderText('Recognized text appears here. Re-run OCR after changing or rotating the scan.');layout.addWidget(self.ocr_text,1)
        self.ocr_tab_index=self.tabs.addTab(widget,'OCR and text')
    def build_pages_tab(self):
        widget=QWidget();layout=QVBoxLayout(widget);self.page_numbers=QCheckBox('Number PDF pages automatically');self.page_numbers.setChecked(True);self.queue_searchable=QCheckBox('Create a searchable PDF (run missing OCR locally)');self.queue_searchable.setChecked(True)
        layout.addWidget(self.page_numbers);layout.addWidget(self.queue_searchable)
        note=QLabel('Add scans from the workspace, webcam or history. Page order and snapshots persist across restarts. Maximum 20 pages per document.');note.setWordWrap(True);note.setObjectName('subtle');layout.addWidget(note)
        split=QSplitter();self.page_list=QListWidget();self.page_list.setMinimumWidth(220);split.addWidget(self.page_list);self.page_preview=ImageCanvas('Select a page and click Preview page');split.addWidget(self.page_preview);split.setSizes([260,620]);layout.addWidget(split,1)
        buttons=QHBoxLayout();self.queue_up_button=self.make_button('Move up',lambda:self.move_page(-1),buttons);self.queue_down_button=self.make_button('Move down',lambda:self.move_page(1),buttons);self.queue_remove_button=self.make_button('Remove page',self.remove_page,buttons);self.queue_preview_button=self.make_button('Preview page',self.preview_page,buttons);self.queue_ocr_button=self.make_button('Export document PDF',self.export_queue,buttons);buttons.addStretch();layout.addLayout(buttons)
        self.pages_tab_index=self.tabs.addTab(widget,'Document pages')
    def build_history_tab(self):
        widget=QWidget();layout=QVBoxLayout(widget);self.history_search=QLineEdit();self.history_search.setPlaceholderText('Search saved titles and recognized text');self.history_search.textChanged.connect(self.refresh_history);layout.addWidget(self.history_search)
        self.history_table=QTableWidget(0,4);self.history_table.setHorizontalHeaderLabels(['Saved (UTC)','Document','Mode','OCR']);self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.history_table,1)
        buttons=QHBoxLayout();self.snapshot_button=self.make_button('Save current snapshot',self.save_snapshot,buttons);self.history_open_button=self.make_button('Open snapshot',self.open_history,buttons);self.history_queue_button=self.make_button('Add to document',self.queue_history,buttons);self.history_delete_button=self.make_button('Delete snapshot',self.delete_history,buttons);buttons.addStretch();layout.addLayout(buttons)
        label=QLabel('History stores processed images and OCR locally. Delete removes that snapshot and its queued references. Original photos are not copied.');label.setObjectName('subtle');label.setWordWrap(True);layout.addWidget(label)
        self.history_tab_index=self.tabs.addTab(widget,'Scan history')
    def build_batch_tab(self):
        widget=QWidget();layout=QVBoxLayout(widget);row=QHBoxLayout();self.batch_ocr=QCheckBox('Extract text and save searchable PDFs');self.batch_ocr.setChecked(True);row.addWidget(self.batch_ocr);row.addStretch();self.batch_button=self.make_button('Choose images and scan',self.choose_batch,row);self.batch_cancel_button=self.make_button('Cancel batch',self.cancel_batch,row);self.batch_cancel_button.setEnabled(False);layout.addLayout(row)
        hint=QLabel('Uses the selected scan mode and OCR language. Successful scans enter history; the first available pages join the document. Failed boundaries remain available for manual correction.');hint.setWordWrap(True);hint.setObjectName('subtle');layout.addWidget(hint)
        self.batch_table=QTableWidget(0,3);self.batch_table.setHorizontalHeaderLabels(['Source image','Result','Details']);self.batch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.batch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.batch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.batch_table.cellDoubleClicked.connect(self.open_batch_row);layout.addWidget(self.batch_table,1)
        self.batch_summary=QLabel('Drop multiple images into the window, or choose images above. Double-click a result to open its source.');self.batch_summary.setWordWrap(True);layout.addWidget(self.batch_summary)
        self.batch_tab_index=self.tabs.addTab(widget,'Batch processing')
    def build_wipe_tab(self):
        widget=QWidget();layout=QVBoxLayout(widget);note=QLabel('Compare the perspective-corrected input and enhanced output in the same geometry. Drag the divider or use the slider.');note.setObjectName('subtle');note.setWordWrap(True);layout.addWidget(note)
        self.wipe_canvas=ComparisonCanvas();layout.addWidget(self.wipe_canvas,1);self.wipe_slider=QSlider(Qt.Orientation.Horizontal);self.wipe_slider.setRange(0,100);self.wipe_slider.setValue(50);self.wipe_slider.valueChanged.connect(self.wipe_canvas.set_position);self.wipe_canvas.positionChanged.connect(self.wipe_slider.setValue);layout.addWidget(self.wipe_slider)
        self.wipe_tab_index=self.tabs.addTab(widget,'Before / after')
    def sync_actions(self):
        super().sync_actions()
        if not hasattr(self,'history_store'):return
        valid=self.result is not None and self.result.output is not None
        for button in [self.rotate_left_button,self.rotate_right_button,self.ocr_button,self.searchable_button,self.snapshot_button]:button.setEnabled(valid and not self.busy)
        for button in [self.copy_text_button,self.save_text_button]:button.setEnabled(self.ocr_result is not None and not self.busy)
        for button in [self.queue_up_button,self.queue_down_button,self.queue_remove_button,self.queue_preview_button,self.queue_ocr_button]:button.setEnabled(bool(self.pages) and not self.busy)
    def ocr_options(self):return self.ocr_language.currentText().strip(),int(self.ocr_psm.currentData()),self.engine_path.text().strip() or None
    def clear_ocr(self):
        self.ocr_result=None
        if hasattr(self,'ocr_text'):self.ocr_text.clear();self.ocr_status.setText('Run OCR on the current scan. Changing the image invalidates earlier text.')
    def set_source(self,image,name='Webcam capture'):
        self.source_name=name;self.current_history_id=None;self.clear_ocr();super().set_source(image,name)
        if hasattr(self,'wipe_canvas'):self.wipe_canvas.set_pair(None,None)
    def process(self,corners=None):
        if self.image is None or self.busy:return
        if isinstance(corners,bool):corners=None
        image=self.image;mode=self.mode.currentText();settings=self.get_settings();title=self.source_name
        def compute():
            result=scan(image,mode,settings,corners);record=None;warning=''
            if result.output is not None:
                try:record=self.history_store.add(result.output,title,mode,{'input_quality':result.input_quality,'output_quality':result.output_quality})
                except (OSError,ValueError) as exc:warning='History could not be saved: '+str(exc)
            return result,record,warning
        def accept(value):
            result,record,warning=value;self.accept_result(result);self.current_history_id=record['id'] if record else None;self.refresh_history()
            if warning:self.status.setText(warning)
        self.run_task('Detecting document and saving scan history…',compute,accept)
    def accept_result(self,result):
        self.clear_ocr();self.current_history_id=None;super().accept_result(result)
    def render_quality(self):
        super().render_quality()
        if hasattr(self,'wipe_canvas') and self.result is not None:self.wipe_canvas.set_pair(self.result.warped,self.result.output)
    def update_enhancement(self):
        if self.busy:return
        self.clear_ocr();self.current_history_id=None;super().update_enhancement()
    def rotate_current(self,clockwise=True):
        if self.result is None or self.result.output is None or self.busy:return
        result=self.result;h,w=result.output.shape[:2];code=cv2.ROTATE_90_CLOCKWISE if clockwise else cv2.ROTATE_90_COUNTERCLOCKWISE
        def compute():
            out=cv2.rotate(result.output,code);warped=cv2.rotate(result.warped,code)
            R=np.float64([[0,-1,h-1],[1,0,0],[0,0,1]]) if clockwise else np.float64([[0,1,0],[-1,0,w-1],[0,0,1]])
            return out,warped,R@result.homography,analyze_quality(out)
        def accept(value):
            result.output,result.warped,result.homography,result.output_quality=value;self.clear_ocr();self.current_history_id=None
            result.stages['Perspective correction']=resize_longest(result.warped,1200)[0];result.stages['Enhancement / final']=resize_longest(result.output,1200)[0]
            self.output.set_image(result.output);self.show_stage(self.stage_choice.currentText());self.render_quality();self.comparisons={};self.compare_choice.clear();self.compare_canvas.set_image(None);self.status.setText('Page rotated 90 degrees. Run OCR again for the new orientation.')
        self.run_task('Rotating document…',compute,accept)
    def choose_engine(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose Tesseract executable','','Executable (tesseract.exe tesseract);;All files (*)')
        if path:self.engine_path.setText(path);self.check_ocr_setup()
    def check_ocr_setup(self):
        _,_,binary=self.ocr_options()
        def compute():return find_tesseract(binary),available_languages(binary)
        def accept(value):
            executable,languages=value;selected=self.ocr_language.currentText();self.ocr_language.clear();self.ocr_language.addItems([x for x in languages if x!='osd']);self.ocr_language.setCurrentText(selected);self.settings.setValue('tesseract_cmd',binary or '')
            self.ocr_status.setText(f'OCR ready: {executable}. Installed language data: {", ".join(languages)}');self.status.setText('Local OCR engine is ready')
        self.run_task('Checking local Tesseract setup…',compute,accept)
    def extract_text(self,after=None):
        if self.result is None or self.result.output is None or self.busy:return
        if isinstance(after,bool):after=None
        image=self.result.output;language,psm,binary=self.ocr_options();identifier=self.current_history_id;title=self.source_name;mode=self.mode.currentText()
        def compute():
            result=recognize(image,language,psm,binary)
            if identifier:self.history_store.attach_ocr(identifier,result);record_id=identifier
            else:record_id=self.history_store.add(image,title,mode,ocr=result)['id']
            return result,record_id
        def accept(value):
            self.ocr_result,self.current_history_id=value;self.show_ocr();self.refresh_history();self.status.setText('OCR complete — proofread the extracted text')
            if after:QTimer.singleShot(0,after)
        self.run_task('Recognizing text locally…',compute,accept)
    def show_ocr(self):
        if self.ocr_result is None:return
        result=self.ocr_result;self.ocr_text.setPlainText(result.text)
        self.ocr_status.setText(f'{len(result.words)} recognized words · {result.language} · mean engine confidence {result.mean_confidence:.1f}/100 (not validated accuracy)' if result.words else 'No text recognized. Try rotating the page, another layout or better lighting; the image is retained.')
    def copy_text(self):
        if self.ocr_result is not None:QApplication.clipboard().setText(self.ocr_result.text);self.status.setText('Recognized text copied')
    def export_text(self):
        if self.ocr_result is None:return
        path,_=QFileDialog.getSaveFileName(self,'Save recognized text','smartscan.txt','UTF-8 text (*.txt)')
        if path:
            if not path.lower().endswith('.txt'):path+='.txt'
            text=self.ocr_result.text;self.run_task('Saving recognized text…',lambda:save_text(text,path),lambda p:self.status.setText(f'Saved {p}'))
    def export_searchable(self):
        path,_=QFileDialog.getSaveFileName(self,'Save searchable PDF','smartscan_searchable.pdf','Searchable PDF (*.pdf)')
        if path:
            if not path.lower().endswith('.pdf'):path+='.pdf'
            self.export_current_to(path,True)
    def export_current_to(self,path,searchable=False):
        if self.result is None or self.result.output is None:return
        image=self.result.output;language,psm,binary=self.ocr_options();cached=self.ocr_result;numbers=self.page_numbers.isChecked();identifier=self.current_history_id;title=self.source_name;mode=self.mode.currentText()
        def compute():
            recognized=cached or recognize(image,language,psm,binary) if searchable else None
            saved=save_pdf([image],path,numbers,[recognized] if searchable else None) if Path(path).suffix.lower()=='.pdf' else save_image(image,path)
            record_id=identifier
            if recognized:
                if identifier:self.history_store.attach_ocr(identifier,recognized)
                else:record_id=self.history_store.add(image,title,mode,ocr=recognized)['id']
            return saved,recognized,record_id
        def accept(value):
            saved,recognized,record_id=value
            if recognized:
                self.ocr_result=recognized;self.current_history_id=record_id;self.show_ocr();self.refresh_history()
            self.status.setText(f'Saved {saved}')
        self.run_task('Recognizing and exporting searchable PDF…' if searchable else 'Saving scan…',compute,accept)
    def export_current(self):
        if self.result is None or self.result.output is None:return
        path,selected=QFileDialog.getSaveFileName(self,'Save scan','smartscan.png','PNG (*.png);;JPEG (*.jpg);;Image PDF (*.pdf);;Searchable PDF (*.pdf)')
        if not path:return
        suffix='.pdf' if 'PDF' in selected else '.jpg' if 'JPEG' in selected else '.png'
        if Path(path).suffix.lower()!=suffix:path=str(Path(path).with_suffix(suffix))
        self.export_current_to(path,'Searchable' in selected)
    def snapshot_data(self):
        return self.result.output,self.source_name,self.mode.currentText(),{'input_quality':self.result.input_quality,'output_quality':self.result.output_quality},self.ocr_result
    def save_snapshot(self):
        if self.result is None or self.result.output is None:return
        image,title,mode,metadata,ocr=self.snapshot_data()
        def accept(record):self.current_history_id=record['id'];self.refresh_history();self.status.setText('Current image and OCR saved to local history')
        self.run_task('Saving scan snapshot…',lambda:self.history_store.add(image,title,mode,metadata,ocr),accept)
    def refresh_history(self,*args):
        if not hasattr(self,'history_table'):return
        rows=self.history_store.list(self.history_search.text());self.history_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate([row['created'][:19].replace('T',' '),row['title'],row['mode'],'Yes' if row['ocr'] else '—']):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row['id']);self.history_table.setItem(i,j,item)
    def selected_history_id(self):
        row=self.history_table.currentRow();item=self.history_table.item(row,0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None
    def open_history(self):
        identifier=self.selected_history_id()
        if not identifier:return
        def compute():return self.history_store.get(identifier),self.history_store.load(identifier),self.history_store.load_ocr(identifier)
        def accept(value):
            record,image,recognized=value;self.set_source(image,'History: '+record['title']);h,w=image.shape[:2];corners=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
            quality=analyze_quality(image);detection=Detection(corners,None,'History snapshot','Processed snapshot restored; original photograph is not stored.')
            result=ScanResult(detection,image.copy(),image.copy(),np.eye(3),{'Restored scan':resize_longest(image,1200)[0]},quality,quality,0)
            self.accept_result(result);self.current_history_id=identifier;self.ocr_result=recognized;self.show_ocr();self.status.setText('Saved scan restored; no automatic re-detection applied')
        self.run_task('Restoring scan from local history…',compute,accept)
    def delete_history(self):
        identifier=self.selected_history_id()
        if not identifier:return
        def accept(_):
            self.pages=self.history_store.queue_ids();self.refresh_pages();self.refresh_history()
            if self.current_history_id==identifier:self.current_history_id=None
            self.status.setText('Snapshot deleted from history and document queue')
        self.run_task('Deleting selected snapshot…',lambda:self.history_store.delete(identifier),accept)
    def refresh_pages(self):
        self.page_list.clear()
        for i,identifier in enumerate(self.pages):
            try:record=self.history_store.get(identifier);self.page_list.addItem(f'{i+1:02d}  {record["title"]}')
            except ValueError:self.page_list.addItem(f'{i+1:02d}  Missing snapshot')
        self.queue_label.setText(f'{len(self.pages)} document pages')
    def append_queue(self,identifier):
        if len(self.pages)>=20:raise ValueError('The document already has 20 pages. Export or remove a page first.')
        ids=self.pages+[identifier];self.history_store.set_queue(ids);self.pages=ids;self.refresh_pages()
    def add_page(self):
        if self.result is None or self.result.output is None or self.busy:return
        if len(self.pages)>=20:self.error('The document already has 20 pages. Export or remove a page first.');return
        image,title,mode,metadata,ocr=self.snapshot_data()
        def accept(record):self.current_history_id=record['id'];self.append_queue(record['id']);self.refresh_history();self.status.setText('Page saved and added to the persistent document')
        self.run_task('Adding scan to document…',lambda:self.history_store.add(image,title,mode,metadata,ocr),accept)
    def queue_history(self):
        identifier=self.selected_history_id()
        if identifier:
            try:self.append_queue(identifier);self.sync_actions();self.status.setText('History snapshot added to document')
            except ValueError as exc:self.error(str(exc))
    def move_page(self,delta):
        row=self.page_list.currentRow();target=row+delta
        if row<0 or not 0<=target<len(self.pages):return
        ids=list(self.pages);ids[row],ids[target]=ids[target],ids[row];self.history_store.set_queue(ids);self.pages=ids;self.refresh_pages();self.page_list.setCurrentRow(target)
    def remove_page(self):
        row=self.page_list.currentRow()
        if row<0:return
        ids=list(self.pages);ids.pop(row);self.history_store.set_queue(ids);self.pages=ids;self.refresh_pages();self.page_preview.set_image(None);self.sync_actions()
    def preview_page(self):
        row=self.page_list.currentRow()
        if row<0:return
        identifier=self.pages[row];self.run_task('Loading document page…',lambda:self.history_store.load(identifier),lambda image:self.page_preview.set_image(image))
    def clear_queue(self):
        self.history_store.set_queue([]);self.pages=[];self.refresh_pages();self.page_preview.set_image(None);self.sync_actions();self.status.setText('Document queue cleared; history snapshots retained')
    def export_queue_to(self,path,searchable=True):
        identifiers=list(self.pages);language,psm,binary=self.ocr_options();numbers=self.page_numbers.isChecked()
        def compute():
            images=[];recognized=[]
            for identifier in identifiers:
                image=self.history_store.load(identifier);images.append(image)
                if searchable:
                    ocr=self.history_store.load_ocr(identifier)
                    if ocr is None or not ocr.pdf_bytes:
                        ocr=recognize(image,language,psm,binary);self.history_store.attach_ocr(identifier,ocr)
                    recognized.append(ocr)
            return save_pdf(images,path,numbers,recognized if searchable else None)
        def accept(saved):self.refresh_history();self.status.setText(f'Saved {len(identifiers)} numbered pages to {saved}' if numbers else f'Saved {len(identifiers)} pages to {saved}')
        self.run_task('Preparing document OCR and PDF…' if searchable else 'Exporting document PDF…',compute,accept)
    def export_queue(self):
        if not self.pages:return
        path,_=QFileDialog.getSaveFileName(self,'Export document PDF','smartscan_document.pdf','PDF (*.pdf)')
        if path:
            if not path.lower().endswith('.pdf'):path+='.pdf'
            self.export_queue_to(path,self.queue_searchable.isChecked())
    def choose_batch(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Choose document photographs','','Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')
        if paths:self.start_batch(paths)
    def start_batch(self,paths,directory=None):
        if self.busy or not paths:return
        if directory is None:
            parent=QFileDialog.getExistingDirectory(self,'Choose batch output parent directory')
            if not parent:return
            directory=Path(parent)/('SmartScan_batch_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        directory=Path(directory);mode=self.mode.currentText();settings=self.get_settings();use_ocr=self.batch_ocr.isChecked();language,psm,binary=self.ocr_options();self.cancel_event.clear();self.batch_cancel_button.setEnabled(True);self.tabs.setCurrentIndex(self.batch_tab_index)
        def compute():return process_batch(paths,directory,mode,settings,use_ocr,language,psm,binary,self.history_store,self.batchProgress.emit,self.cancel_event)
        def accept(rows):
            self.batch_rows=rows;self.batch_table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate([Path(row['source']).name,row['status'],row['message']]):self.batch_table.setItem(i,j,QTableWidgetItem(value))
            ids=[row['history_id'] for row in rows if row['history_id']];capacity=20-len(self.pages);self.pages+=ids[:capacity];self.history_store.set_queue(self.pages);self.refresh_pages();self.refresh_history()
            saved=sum(row['status'] in ['saved','ocr_error'] for row in rows);manual=sum(row['status']=='manual_required' for row in rows);cancelled=sum(row['status']=='cancelled' for row in rows)
            self.batch_summary.setText(f'{saved} scans saved · {manual} need manual corners · {cancelled} cancelled · {len(ids[:capacity])} added to document. Outputs: {directory}')
            self.status.setText('Batch complete — inspect per-file results and batch_report.json');self.batch_cancel_button.setEnabled(False)
        self.run_task('Batch processing document images…',compute,accept)
        # Error and cancellation are also handled when the worker emits done.
        if self.tasks:self.tasks[-1].signals.done.connect(lambda:self.batch_cancel_button.setEnabled(False))
    def batch_progress(self,index,total,message):
        self.progress.setRange(0,total);self.progress.setValue(index);self.status.setText(f'Batch {index}/{total} · {message}')
    def cancel_batch(self):self.cancel_event.set();self.status.setText('Cancelling after the current page finishes…');self.batch_cancel_button.setEnabled(False)
    def open_batch_row(self,row,column=0):
        if not self.busy and 0<=row<len(self.batch_rows):self.open_path(self.batch_rows[row]['source'])
    def dropEvent(self,event):
        paths=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if len(paths)>1:self.start_batch(paths)
        elif paths:self.open_path(paths[0])
