"""Local scan snapshots, OCR data and a persistent ordered document queue."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,sqlite3,sys,uuid
from .export import save_image
from .image_processing import load_image
from .ocr import OCRResult


def default_data_dir():
    if os.environ.get('SMARTSCAN_DATA_DIR'):return Path(os.environ['SMARTSCAN_DATA_DIR']).expanduser()
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'SmartScan'
    if sys.platform=='darwin':return Path.home()/'Library'/'Application Support'/'SmartScan'
    return Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))/'smartscan'

class HistoryStore:
    def __init__(self,directory=None):
        self.directory=Path(directory) if directory else default_data_dir();self.directory.mkdir(parents=True,exist_ok=True)
        self.database=self.directory/'history.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS scans (id TEXT PRIMARY KEY, title TEXT NOT NULL, created TEXT NOT NULL, mode TEXT NOT NULL, width INTEGER, height INTEGER, metadata TEXT NOT NULL, ocr TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS queue (position INTEGER PRIMARY KEY, scan_id TEXT NOT NULL)')
    def connect(self):
        db=sqlite3.connect(self.database,timeout=20);db.row_factory=sqlite3.Row;return db
    def image_path(self,identifier):
        self._check_id(identifier);return self.directory/(identifier+'.png')
    def _check_id(self,identifier):
        if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid scan identifier.')
    def add(self,image,title,mode,metadata=None,ocr=None):
        identifier=uuid.uuid4().hex;path=self.image_path(identifier)
        save_image(image,path)
        try:
            if ocr: (self.directory/(identifier+'.pdf')).write_bytes(ocr.pdf_bytes)
            with self.connect() as db:db.execute('INSERT INTO scans VALUES (?,?,?,?,?,?,?,?)',(identifier,str(title),datetime.now(timezone.utc).isoformat(),mode,image.shape[1],image.shape[0],json.dumps(metadata or {}),json.dumps(ocr.metadata()) if ocr else None))
        except Exception:
            path.unlink(missing_ok=True);(self.directory/(identifier+'.pdf')).unlink(missing_ok=True);raise
        return self.get(identifier)
    def get(self,identifier):
        self._check_id(identifier)
        with self.connect() as db:row=db.execute('SELECT * FROM scans WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('This scan is no longer in history.')
        item=dict(row);item['metadata']=json.loads(item['metadata']);item['ocr']=json.loads(item['ocr']) if item['ocr'] else None
        return item
    def list(self,query='',limit=500):
        # User text is literal, not SQL or LIKE syntax.
        with self.connect() as db:rows=db.execute('SELECT * FROM scans ORDER BY created DESC LIMIT ?', (int(limit),)).fetchall()
        query=query.casefold();items=[]
        for row in rows:
            item=dict(row);ocr=json.loads(item['ocr']) if item['ocr'] else None
            if query and query not in (item['title']+' '+(ocr['text'] if ocr else '')).casefold():continue
            item['metadata']=json.loads(item['metadata']);item['ocr']=ocr;items.append(item)
        return items
    def load(self,identifier):return load_image(self.image_path(identifier))
    def load_ocr(self,identifier):
        item=self.get(identifier)
        if not item['ocr']:return None
        path=self.directory/(identifier+'.pdf')
        return OCRResult(**item['ocr'],pdf_bytes=path.read_bytes() if path.exists() else b'')
    def attach_ocr(self,identifier,result):
        self.get(identifier)
        (self.directory/(identifier+'.pdf')).write_bytes(result.pdf_bytes)
        with self.connect() as db:db.execute('UPDATE scans SET ocr=? WHERE id=?',(json.dumps(result.metadata()),identifier))
    def queue_ids(self):
        with self.connect() as db:return [r['scan_id'] for r in db.execute('SELECT q.scan_id FROM queue q JOIN scans s ON q.scan_id=s.id ORDER BY position')]
    def set_queue(self,identifiers):
        identifiers=list(identifiers)
        if len(identifiers)>20:raise ValueError('The document queue is limited to 20 pages. Export it before adding more.')
        for identifier in identifiers:self.get(identifier)
        with self.connect() as db:
            db.execute('DELETE FROM queue');db.executemany('INSERT INTO queue VALUES (?,?)',enumerate(identifiers))
    def delete(self,identifier):
        self.get(identifier)
        # Remove queued references before deleting the scan snapshot.
        ids=[i for i in self.queue_ids() if i!=identifier];self.set_queue(ids)
        with self.connect() as db:db.execute('DELETE FROM scans WHERE id=?',(identifier,))
        self.image_path(identifier).unlink(missing_ok=True);(self.directory/(identifier+'.pdf')).unlink(missing_ok=True)
