"""Real Tesseract, PDF text layers, persistent state, batch failure/cancellation."""
from pathlib import Path
import threading
import cv2,numpy as np,pytest
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfReader
from src.ocr import recognize,find_tesseract,OCRError
from src.history import HistoryStore
from src.batch import process_batch
from src.export import save_pdf
from src.cli import main
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def printed_page():
    image=Image.new('RGB',(1200,800),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(ROOT/'assets'/'fonts'/'DejaVuSans.ttf'),42)
    for i,text in enumerate(['SMARTSCAN OCR TEST','Offline document scanning','Invoice number 2026','Total amount 1250']):draw.text((70,90+i*145),text,font=font,fill='black')
    return cv2.cvtColor(np.array(image),cv2.COLOR_RGB2BGR)

@pytest.fixture
def recognized(printed_page):return recognize(printed_page,psm=6)

def test_real_ocr(printed_page,recognized):
    assert 'SMARTSCAN' in recognized.text and '2026' in recognized.text and '1250' in recognized.text
    assert len(recognized.words)>=12 and 0<=recognized.mean_confidence<=100
    assert recognized.pdf_bytes.startswith(b'%PDF')
    for word in recognized.words:assert 0<=word['left']<printed_page.shape[1] and word['width']>0

def test_searchable_numbered_pdf(printed_page,recognized,tmp_path):
    path=save_pdf([printed_page,printed_page],tmp_path/'searchable.pdf',True,[recognized,recognized])
    reader=PdfReader(path);assert len(reader.pages)==2
    for i,page in enumerate(reader.pages):
        text=page.extract_text();assert 'SMARTSCAN' in text and '1250' in text and f'Page {i+1} of 2' in text
        assert len(page.images)>0

def test_raster_pdf_numbering(printed_page,tmp_path):
    path=save_pdf([printed_page],tmp_path/'raster.pdf',True)
    text=PdfReader(path).pages[0].extract_text();assert 'Page 1 of 1' in text and 'SMARTSCAN' not in text

def test_ocr_setup_errors(printed_page,tmp_path):
    with pytest.raises(OCRError,match='not found'):find_tesseract(tmp_path/'absent-tesseract')
    with pytest.raises(OCRError):recognize(printed_page,language='eng; command')
    with pytest.raises(OCRError,match='Missing'):recognize(printed_page,language='not_installed_language')
    with pytest.raises(OCRError):recognize(printed_page,psm=0)

def test_stale_ocr_rejected(printed_page,recognized,tmp_path):
    with pytest.raises(ValueError,match='stale'):save_pdf([cv2.rotate(printed_page,cv2.ROTATE_90_CLOCKWISE)],tmp_path/'bad.pdf',ocr_pages=[recognized])
    with pytest.raises(ValueError):save_pdf([printed_page],tmp_path/'bad.pdf',ocr_pages=[])

def test_history_restart_and_ocr(printed_page,recognized,tmp_path):
    store=HistoryStore(tmp_path/'history');a=store.add(printed_page,'invoice','Original scan',ocr=recognized);b=store.add(printed_page,'second page','Original scan')
    store.set_queue([b['id'],a['id'],b['id']]);restored=HistoryStore(tmp_path/'history')
    assert restored.queue_ids()==[b['id'],a['id'],b['id']]
    assert np.array_equal(restored.load(a['id']),printed_page)
    assert restored.load_ocr(a['id']).text==recognized.text
    assert len(restored.list('1250'))==1 and not restored.list("' OR 1=1")
    restored.attach_ocr(b['id'],recognized);assert len(restored.list('1250'))==2
    restored.delete(b['id']);assert restored.queue_ids()==[a['id']]
    with pytest.raises(ValueError):restored.image_path('../unsafe')

def test_batch_partial_failure_and_report(tmp_path):
    paths=[ROOT/'sample_images'/'perspective.png',ROOT/'sample_images'/'no_document.png',tmp_path/'missing.png']
    progress=[];store=HistoryStore(tmp_path/'history')
    rows=process_batch(paths,tmp_path/'batch',store=store,progress=lambda i,n,s:progress.append((i,n)))
    assert [row['status'] for row in rows]==['saved','manual_required','error']
    assert len(store.list())==1 and (tmp_path/'batch'/'batch_report.json').exists() and progress[-1]==(3,3)

def test_batch_cancel_between_pages(tmp_path):
    event=threading.Event();paths=[ROOT/'sample_images'/'perspective.png']*3
    rows=process_batch(paths,tmp_path/'batch',cancel=event,progress=lambda i,n,s:event.set())
    assert [row['status'] for row in rows]==['saved','cancelled','cancelled']

def test_batch_ocr_failure_retains_image(tmp_path):
    rows=process_batch([ROOT/'sample_images'/'perspective.png'],tmp_path/'batch',ocr=True,binary=str(tmp_path/'missing'))
    assert rows[0]['status']=='ocr_error' and Path(rows[0]['image']).exists() and 'not found' in rows[0]['message']

def test_cli_searchable(printed_page,tmp_path):
    from src.export import save_image
    source=tmp_path/'page.png';save_image(printed_page,source);h,w=printed_page.shape[:2]
    import json
    corners=json.dumps([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    assert main([str(source),str(tmp_path/'ocr.pdf'),'--corners',corners,'--searchable','--psm','6','--number-pages'])==0
    assert 'SMARTSCAN' in PdfReader(tmp_path/'ocr.pdf').pages[0].extract_text()
    assert (tmp_path/'ocr.txt').exists()
