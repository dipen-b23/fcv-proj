"""Create deterministic test scenes with known geometric truth. No downloaded images."""
from pathlib import Path
import json,sys
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.export import save_image

ROOT=Path(__file__).resolve().parents[1]/'sample_images'

def page_image():
    page=np.full((900,640,3),244,np.uint8)
    cv2.rectangle(page,(38,36),(600,132),(211,86,38),-1)
    cv2.putText(page,'SMARTSCAN',(60,82),cv2.FONT_HERSHEY_SIMPLEX,1.05,(255,255,255),2,cv2.LINE_AA)
    cv2.putText(page,'DOCUMENT PROCESSING LAB',(61,111),0,.45,(250,250,250),1,cv2.LINE_AA)
    lines=['CSE 3176 | Foundations of Computer Vision','A practical guide to document enhancement','','01  Acquire an image','Keep all four page corners inside the frame.','Use even lighting and avoid reflections.','','02  Detect the document boundary','Edges, contours and geometry locate a page.','Manual points provide a useful fallback.','','03  Correct perspective','A homography maps the page to a rectangle.','','04  Enhance and export','Compare colour, grayscale and binary scans.','Check small text before saving your output.']
    y=180
    for line in lines:
        cv2.putText(page,line,(45,y),0,.52,(45,50,58),1,cv2.LINE_AA);y+=33
    cv2.line(page,(45,775),(595,775),(175,180,185),2)
    for i in range(4):cv2.rectangle(page,(45+i*140,801),(157+i*140,848),(210-i*25,190-i*20,170-i*15),-1)
    cv2.putText(page,'Synthetic evaluation page | 2026',(45,877),0,.45,(90,90,90),1,cv2.LINE_AA)
    return page

def make_scene(corners,bg=60,page_value=None):
    rng=np.random.default_rng(21);h,w=1100,1400
    base=np.clip(np.full((h,w,3),bg,dtype=float)+rng.normal(0,1,(h,w,1)),0,255).astype(np.uint8)
    page=page_image()
    if page_value is not None:page=np.clip(page.astype(float)*.25+page_value,0,255).astype(np.uint8)
    H=cv2.getPerspectiveTransform(np.float32([[0,0],[639,0],[639,899],[0,899]]),np.float32(corners))
    warped=cv2.warpPerspective(page,H,(w,h));mask=cv2.warpPerspective(np.full(page.shape[:2],255,np.uint8),H,(w,h))>0
    base[mask]=warped[mask]
    return base

def main():
    ROOT.mkdir(exist_ok=True)
    normal=[[370,90],[1030,90],[1030,1020],[370,1020]]
    tilted=[[430,70],[1100,250],[870,1030],[220,840]]
    perspective=[[390,150],[1030,65],[1140,980],[230,1030]]
    cases={};meta={}
    for name,corners,bg in [('normal',normal,65),('tilted',tilted,65),('perspective',perspective,60),('bright_background',perspective,215),('dark_background',perspective,18)]:
        cases[name]=make_scene(corners,bg);meta[name]={'corners':corners,'kind':'synthetic'}
    cases['low_contrast']=make_scene(perspective,165,page_value=135);meta['low_contrast']={'corners':perspective,'kind':'synthetic'}
    rng=np.random.default_rng(32)
    cases['noisy']=np.clip(cases['perspective'].astype(float)+rng.normal(0,14,cases['perspective'].shape),0,255).astype(np.uint8);meta['noisy']={'corners':perspective,'kind':'synthetic'}
    cases['blurred']=cv2.GaussianBlur(cases['perspective'],(19,19),5);meta['blurred']={'corners':perspective,'kind':'synthetic'}
    x=np.linspace(0,1,1400)[None,:,None];shade=.52+.48*np.minimum(1,abs(x-.48)*3)
    cases['shadows']=np.clip(cases['perspective']*shade,0,255).astype(np.uint8);meta['shadows']={'corners':perspective,'kind':'synthetic'}
    cases['multiple_objects']=cases['perspective'].copy();cv2.circle(cases['multiple_objects'],(110,190),75,(100,140,170),-1);cv2.rectangle(cases['multiple_objects'],(1200,250),(1320,550),(80,110,140),-1);meta['multiple_objects']={'corners':perspective,'kind':'synthetic'}
    cases['partial_page']=make_scene([[-80,90],[840,70],[1000,980],[-100,1090]],65);meta['partial_page']={'corners':None,'kind':'partial: manual inspection required'}
    blank=np.full((1100,1400,3),85,np.uint8);cv2.circle(blank,(700,550),200,(130,110,90),-1)
    cases['no_document']=blank;meta['no_document']={'corners':None,'kind':'synthetic negative'}
    for name,image in cases.items():save_image(image,ROOT/f'{name}.png')
    (ROOT/'ground_truth.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    save_image(page_image(),ROOT/'reference_page.png')
    (ROOT/'README.md').write_text('These are generated, deterministic geometric test fixtures, not real camera photographs. ground_truth.json contains page corners. Run python tools/generate_samples.py to reproduce. A partial-page image is a stress case; missing text cannot be recovered. Large input is generated in tests rather than stored. Also test your own phone photographs before evaluation.\n')
    print(f'Generated {len(cases)} test scenes and reference page in {ROOT}')
if __name__=='__main__':main()
