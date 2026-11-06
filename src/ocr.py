"""Offline Tesseract adapter. No shell, uploads, model downloads or Python OCR shim."""
from dataclasses import dataclass,field
from pathlib import Path
import csv,io,os,re,shutil,subprocess,tempfile
import cv2
from .image_processing import validate

class OCRError(ValueError):
    """Actionable OCR configuration / recognition error."""

@dataclass
class OCRResult:
    text: str
    language: str
    width: int
    height: int
    words: list = field(default_factory=list)
    mean_confidence: float = 0.
    pdf_bytes: bytes = b''

    def metadata(self):
        return {k:getattr(self,k) for k in ['text','language','width','height','words','mean_confidence']}


def find_tesseract(binary=None):
    configured=binary or os.environ.get('TESSERACT_CMD')
    if configured:
        path=Path(str(configured).strip().strip('"')).expanduser()
        if path.is_file():return str(path.resolve())
        found=shutil.which(str(configured))
        if found:return found
        raise OCRError('Configured Tesseract executable was not found. Choose tesseract.exe in the OCR tab or fix TESSERACT_CMD.')
    found=shutil.which('tesseract')
    if found:return found
    if os.name=='nt':
        for base in [os.environ.get('ProgramFiles',r'C:\Program Files'),os.environ.get('LOCALAPPDATA','')]:
            path=Path(base)/'Tesseract-OCR'/'tesseract.exe'
            if path.is_file():return str(path)
    raise OCRError('Tesseract is not installed or not on PATH. Follow docs/OCR_SETUP.md, then choose the executable in the OCR tab. Image scanning remains available.')


def _run(command,timeout):
    options={'capture_output':True,'text':True,'encoding':'utf-8','errors':'replace','timeout':timeout}
    if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
    try:result=subprocess.run(command,**options)
    except subprocess.TimeoutExpired as exc:raise OCRError('OCR timed out. Try a smaller image or a simpler page segmentation mode.') from exc
    except OSError as exc:raise OCRError(f'Cannot start Tesseract: {exc}') from exc
    if result.returncode:
        raise OCRError('Tesseract failed: '+(result.stderr or result.stdout).strip()[-1600:])
    return result


def available_languages(binary=None):
    result=_run([find_tesseract(binary),'--list-langs'],15)
    return [line.strip() for line in result.stdout.splitlines() if re.fullmatch(r'[A-Za-z0-9_]+',line.strip())]


def recognize(image,language='eng',psm=3,binary=None,timeout=90):
    validate(image)
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*',language):raise OCRError('Use installed language codes such as eng or eng+hin.')
    if int(psm) not in [3,6,11]:raise OCRError('Supported segmentation modes are 3 (automatic), 6 (one block) and 11 (sparse).')
    executable=find_tesseract(binary)
    installed=available_languages(executable)
    missing=set(language.split('+'))-set(installed)
    if missing:raise OCRError('Missing Tesseract language data: '+', '.join(sorted(missing))+'. Install the language pack locally; see docs/OCR_SETUP.md.')
    # One invocation produces matched text, coordinates and Tesseract's embedded-text PDF.
    with tempfile.TemporaryDirectory(prefix='smartscan-ocr-') as directory:
        source=Path(directory)/'page.png';base=Path(directory)/'recognized'
        ok,encoded=cv2.imencode('.png',image)
        if not ok:raise OCRError('Cannot encode this page for OCR.')
        source.write_bytes(encoded.tobytes())
        _run([executable,str(source),str(base),'-l',language,'--psm',str(psm),'--dpi','300','txt','tsv','pdf'],timeout)
        text=base.with_suffix('.txt').read_text(encoding='utf-8').strip()
        words=[]
        for row in csv.DictReader(io.StringIO(base.with_suffix('.tsv').read_text(encoding='utf-8')),delimiter='\t'):
            if row.get('level')!='5' or not row.get('text','').strip():continue
            try:
                words.append({'text':row['text'],'confidence':float(row['conf']),**{k:int(row[k]) for k in ['left','top','width','height','block_num','par_num','line_num']}})
            except (ValueError,KeyError):continue
        confidence=sum(w['confidence'] for w in words)/len(words) if words else 0.
        return OCRResult(text,language,image.shape[1],image.shape[0],words,round(confidence,2),base.with_suffix('.pdf').read_bytes())
