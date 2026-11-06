"""Orchestration shared by the Streamlit workspace, CLI and tests."""
from dataclasses import dataclass
import time
from .document_detection import detect_document,boundary_overlay
from .perspective_correction import validate_corners,warp_document
from .enhancement import enhance
from .quality_analysis import analyze_quality
from .image_processing import resize_longest

@dataclass
class ScanResult:
    detection: object
    warped: object
    output: object
    homography: object
    stages: dict
    input_quality: dict
    output_quality: object
    elapsed_ms: float

def scan(image,mode="Enhanced document",settings=None,corners=None):
    start=time.perf_counter()
    detection=detect_document(image)
    if corners is not None:
        detection.corners=validate_corners(corners,image.shape)
        detection.strategy="Manual corners";detection.confidence=None
        detection.message="Manual boundary applied. Confidence is not estimated for manual input."
    preview,_=resize_longest(image,1200)
    stages={"Original":preview,**detection.stages}
    overlay,_=resize_longest(boundary_overlay(image,detection.corners),1200)
    stages["Document boundary"]=overlay
    iq=analyze_quality(image,detection.confidence,detection.corners)
    if detection.corners is None:
        return ScanResult(detection,None,None,None,stages,iq,None,(time.perf_counter()-start)*1000)
    warped,homography=warp_document(image,detection.corners)
    output=enhance(warped,mode,settings)
    stages["Perspective correction"]=resize_longest(warped,1200)[0]
    stages["Enhancement / final"]=resize_longest(output,1200)[0]
    oq=analyze_quality(output)
    return ScanResult(detection,warped,output,homography,stages,iq,oq,(time.perf_counter()-start)*1000)
