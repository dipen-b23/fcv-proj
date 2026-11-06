"""Write measured fixture evidence, qualitative contact sheets and an offscreen UI capture."""
import os,sys,json,time,platform,tempfile
from datetime import date
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from src.image_processing import load_image,resize_longest
from src.pipeline import scan
from src.document_detection import boundary_overlay
from src.export import save_image
from importlib.metadata import version
ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/'docs'

def iou(a,b,shape):
    m=np.zeros(shape,np.uint8);n=m.copy();cv2.fillConvexPoly(m,np.int32(a),1);cv2.fillConvexPoly(n,np.int32(b),1)
    return np.count_nonzero(m&n)/max(1,np.count_nonzero(m|n))

def main():
    meta=json.loads((ROOT/'sample_images'/'ground_truth.json').read_text());rows=[];hero=None;panels=[]
    for name,truth in meta.items():
        image=load_image(ROOT/'sample_images'/f'{name}.png');result=scan(image)
        overlap=iou(result.detection.corners,truth['corners'],image.shape[:2]) if truth['corners'] is not None and result.detection.corners is not None else None
        rows.append({'case':name,'detected':result.detection.corners is not None,'strategy':result.detection.strategy,'confidence':result.detection.confidence,'polygon_iou':round(overlap,5) if overlap is not None else None,'elapsed_ms':round(result.elapsed_ms,2),'input_quality':result.input_quality['score'],'output_quality':result.output_quality['score'] if result.output_quality else None})
        if name=='perspective':hero=(image,result)
        if name in ['perspective','shadows','low_contrast','no_document']:
            a=boundary_overlay(image,result.detection.corners);b=result.output if result.output is not None else np.full_like(image,65)
            for im,title in [(a,name+' | input + boundary'),(b,name+' | output' if result.output is not None else name+' | manual selection required')]:
                canvas=np.full((430,480,3),245,np.uint8);thumb,_=resize_longest(im,380);h,w=thumb.shape[:2];canvas[45:45+h,(480-w)//2:(480-w)//2+w]=thumb
                cv2.putText(canvas,title,(12,26),0,.48,(40,50,60),1,cv2.LINE_AA);panels.append(canvas)
    sheet=np.vstack([np.hstack(panels[i:i+2]) for i in range(0,len(panels),2)]);save_image(sheet,DOCS/'results_contact_sheet.jpg')
    evidence={'date':date.today().isoformat(),'platform':platform.platform(),'python':platform.python_version(),'dependencies':{n:version(n) for n in ['numpy','opencv-python-headless','PySide6','Pillow','reportlab','pytest','pypdf']},'scope':'Deterministic synthetic fixtures only; timings are single observations including quality analysis, not a hardware benchmark. No real-camera detection accuracy is asserted.','cases':rows}
    (DOCS/'evaluation.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    from PySide6.QtWidgets import QApplication
    from src.advanced_gui import AdvancedWindow as MainWindow
    temporary=tempfile.TemporaryDirectory(prefix='smartscan-ui-eval-');os.environ['SMARTSCAN_DATA_DIR']=temporary.name
    app=QApplication.instance() or QApplication([]);window=MainWindow();window.set_source(hero[0],'perspective.png');window.accept_result(hero[1]);window.sync_actions();window.show();app.processEvents();window.grab().save(str(DOCS/'workspace.png'));window.close();app.processEvents();temporary.cleanup()
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
