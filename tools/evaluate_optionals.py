"""Measure real OCR on a known generated printed page and verify extended workflows."""
from pathlib import Path
import os,sys,json,tempfile,subprocess,re
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfReader
from src.ocr import recognize,find_tesseract
from src.export import save_image,save_pdf
from src.pipeline import scan
from src.history import HistoryStore
from src.batch import process_batch
ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/'docs'
EXPECTED='SMARTSCAN OCR TEST\nOffline document scanning\nInvoice number 2026\nTotal amount 1250'


def distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=row
    return prev[-1]

def normalized(text):return ' '.join(re.findall(r'[a-z0-9]+',text.lower()))

def main():
    im=Image.new('RGB',(1200,800),'white');draw=ImageDraw.Draw(im);font=ImageFont.truetype(str(ROOT/'assets'/'fonts'/'DejaVuSans.ttf'),42)
    for i,text in enumerate(EXPECTED.splitlines()):draw.text((70,90+i*145),text,font=font,fill='black')
    image=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR);save_image(image,ROOT/'sample_images'/'ocr_test_page.png');(ROOT/'sample_images'/'ocr_expected.txt').write_text(EXPECTED,encoding='utf-8')
    result=scan(image,'Original scan',corners=[[0,0],[1199,0],[1199,799],[0,799]])
    recognized=recognize(result.output,psm=6);save_pdf([result.output,result.output],DOCS/'Searchable_Demo.pdf',True,[recognized,recognized])
    reader=PdfReader(DOCS/'Searchable_Demo.pdf');a,b=normalized(EXPECTED),normalized(recognized.text)
    metrics={'date':date.today().isoformat(),'engine':subprocess.run([find_tesseract(),'--version'],capture_output=True,text=True,timeout=15).stdout.splitlines()[0],'scope':'One generated clean English printed-text fixture; not real-camera or multilingual accuracy. Whitespace, punctuation and case normalized before edit distance.','reference':EXPECTED,'recognized':recognized.text,'reference_characters':len(a),'character_edits':distance(a,b),'character_error_rate':distance(a,b)/len(a),'reference_words':len(a.split()),'word_edits':distance(a.split(),b.split()),'word_error_rate':distance(a.split(),b.split())/len(a.split()),'engine_mean_confidence':recognized.mean_confidence,'pdf_pages':len(reader.pages),'searchable_text_on_all_pages':all('SMARTSCAN' in p.extract_text() and '1250' in p.extract_text() for p in reader.pages),'numbering_verified':all(f'Page {i+1} of 2' in p.extract_text() for i,p in enumerate(reader.pages))}
    with tempfile.TemporaryDirectory(prefix='smartscan-extended-eval-') as folder:
        store=HistoryStore(Path(folder)/'history');record=store.add(result.output,'OCR fixture','Original scan',ocr=recognized);store.set_queue([record['id'],record['id']]);again=HistoryStore(Path(folder)/'history')
        metrics['queue_restart_verified']=again.queue_ids()==[record['id'],record['id']];metrics['history_text_search_verified']=len(again.list('1250'))==1
        rows=process_batch([ROOT/'sample_images'/'perspective.png',ROOT/'sample_images'/'no_document.png'],Path(folder)/'batch',ocr=True,store=store)
        metrics['batch_statuses']=[r['status'] for r in rows]
    (DOCS/'optional_evaluation.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8');(DOCS/'OCR_Demo.txt').write_text(recognized.text,encoding='utf-8');print(json.dumps(metrics,indent=2))
if __name__=='__main__':main()
