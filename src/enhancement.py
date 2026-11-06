"""Five explicit presets plus shared, non-destructive user adjustments."""
from dataclasses import dataclass
import cv2
import numpy as np
from .image_processing import gray,gamma_correct,validate

MODES=["Original scan","Colour document","Grayscale document","Black-and-white","Enhanced document"]

@dataclass
class EnhancementSettings:
    brightness: int = 0
    contrast: float = 1.
    gamma: float = 1.
    sharpening: float = .25
    denoise: int = 1
    threshold_block: int = 31
    threshold_c: int = 11
    threshold_method: str = "Adaptive"

def enhance(image,mode="Enhanced document",settings=None):
    validate(image);s=settings or EnhancementSettings()
    if mode not in MODES: raise ValueError("Unknown enhancement mode.")
    if mode=="Original scan": return image.copy()
    if not (-100<=s.brightness<=100 and .2<=s.contrast<=3 and .2<=s.gamma<=3 and 0<=s.denoise<=3 and 0<=s.sharpening<=2):
        raise ValueError("Enhancement parameters are outside the supported range.")
    work=image.copy()
    if s.denoise:
        work=cv2.bilateralFilter(work,3+2*s.denoise,15+15*s.denoise,15+15*s.denoise)
    if mode in ["Grayscale document","Black-and-white"]: work=gray(work)
    elif work.ndim==2: work=cv2.cvtColor(work,cv2.COLOR_GRAY2BGR)
    if mode in ["Colour document","Enhanced document"]:
        lab=cv2.cvtColor(work,cv2.COLOR_BGR2LAB)
        lab[:,:,0]=cv2.createCLAHE(1.6 if mode=="Colour document" else 2.,(8,8)).apply(lab[:,:,0])
        work=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
    elif mode=="Grayscale document": work=cv2.createCLAHE(2.,(8,8)).apply(work)
    work=np.clip((work.astype(np.float32)-127.5)*s.contrast+127.5+s.brightness,0,255).astype(np.uint8)
    work=gamma_correct(work,s.gamma)
    if mode=="Black-and-white":
        if s.threshold_method=="Otsu": return cv2.threshold(work,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        if s.threshold_method!="Adaptive": raise ValueError("Threshold method must be Adaptive or Otsu.")
        block=max(3,min(int(s.threshold_block)|1,151))
        return cv2.adaptiveThreshold(work,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,block,s.threshold_c)
    if s.sharpening:
        kernel=np.array([[0,-s.sharpening,0],[-s.sharpening,1+4*s.sharpening,-s.sharpening],[0,-s.sharpening,0]],np.float32)
        work=cv2.filter2D(work,-1,kernel)
    return work
