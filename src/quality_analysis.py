"""Transparent heuristic diagnostics, not OCR accuracy or a validated quality model."""
import cv2
import numpy as np
from .image_processing import gray,resize_longest,validate

def analyze_quality(image,confidence=None,corners=None):
    validate(image)
    original_h,original_w=image.shape[:2]
    small,_=resize_longest(image,1000);g=gray(small)
    f=g.astype(np.float32)
    brightness=float(f.mean());contrast=float(f.std())
    blur=float(cv2.Laplacian(g,cv2.CV_64F).var())
    # Flat-region high-pass MAD; if insufficient flat pixels, use the full residual.
    residual=f-cv2.GaussianBlur(f,(3,3),0)
    gradient=cv2.magnitude(cv2.Sobel(f,cv2.CV_32F,1,0),cv2.Sobel(f,cv2.CV_32F,0,1))
    flat=residual[gradient<10]
    if flat.size<100: flat=residual.ravel()
    noise=float(1.4826*np.median(np.abs(flat-np.median(flat))))
    components={"resolution":min(1.,min(original_h,original_w)/1000),"brightness":max(0.,1-abs(brightness-180)/180),"contrast":min(1.,contrast/55),"sharpness":min(1.,np.log1p(blur)/np.log1p(500)),"noise":max(0.,1-noise/20)}
    weights={"resolution":.15,"brightness":.15,"contrast":.25,"sharpness":.30,"noise":.15}
    score=round(100*sum(weights[k]*v for k,v in components.items()),1)
    classification="Excellent" if score>=85 else "Good" if score>=70 else "Fair" if score>=50 else "Poor"
    suggestions=[]
    if blur<80: suggestions.append("Hold the camera steady and focus on the text; sharpening cannot restore missing detail.")
    if contrast<30: suggestions.append("Use even lighting or try CLAHE / black-and-white mode.")
    if brightness<90: suggestions.append("Increase illumination and avoid casting a shadow over the page.")
    if brightness>235: suggestions.append("Reduce glare and exposure; clipped text cannot be recovered.")
    if noise>5: suggestions.append("Increase light or use denoising at a moderate setting.")
    if min(original_h,original_w)<800: suggestions.append("Move closer or use a higher-resolution photograph.")
    distortion=None
    if corners is not None:
        from .perspective_correction import order_corners
        p=order_corners(corners);length=np.linalg.norm(p-np.roll(p,-1,axis=0),axis=1)
        distortion=float(max(abs(length[0]-length[2])/max(length[0],length[2]),abs(length[1]-length[3])/max(length[1],length[3])))
    if confidence is not None and confidence<.65: suggestions.append("Check the boundary or adjust the four corners manually.")
    return {"score":score,"classification":classification,"width":original_w,"height":original_h,"brightness":round(brightness,2),"contrast":round(contrast,2),"laplacian_variance":round(blur,2),"noise_mad":round(noise,2),"detection_confidence":confidence,"perspective_asymmetry":distortion,"components":components,"suggestions":suggestions,"methodology":"Heuristic: 15% resolution, 15% brightness, 25% contrast, 30% log sharpness, 15% low noise. Metrics measured at <=1000 px. Not a validated readability score. Thresholding can inflate contrast/sharpness; compare visually."}
