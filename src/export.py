"""Atomic image / PDF writes; no GUI or external services required."""
from pathlib import Path
import io
import os
import tempfile
import cv2
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4,landscape
from .image_processing import validate

def _atomic(path,writer):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".smartscan-",suffix=path.suffix,dir=path.parent)
    os.close(fd)
    try:
        writer(tmp)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return path

def save_image(image,path):
    validate(image);suffix=Path(path).suffix.lower()
    if suffix not in [".png",".jpg",".jpeg"]: raise ValueError("Choose PNG or JPEG.")
    ok,encoded=cv2.imencode(suffix,image,[cv2.IMWRITE_JPEG_QUALITY,95] if suffix!=".png" else [])
    if not ok: raise ValueError("Could not encode the image.")
    return _atomic(path,lambda tmp:Path(tmp).write_bytes(encoded.tobytes()))

def save_text(text,path):
    return _atomic(path,lambda tmp:Path(tmp).write_text(text,encoding='utf-8'))


def _number_overlay(width,height,index,total):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='SmartScanSans'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font,str(Path(__file__).resolve().parents[1]/'assets'/'fonts'/'DejaVuSans.ttf')))
    buffer=io.BytesIO();pdf=canvas.Canvas(buffer,pagesize=(width,height))
    pdf.setFont(font,9);pdf.setFillColorRGB(.25,.31,.36)
    pdf.drawCentredString(width/2,15,f'Page {index} of {total}');pdf.save()
    return buffer.getvalue()


def save_pdf(images,path,page_numbers=False,ocr_pages=None):
    """A4 page images, optionally with Tesseract's aligned invisible text layer.

    ocr_pages must contain one matching OCRResult per page; recognition is explicit
    so a missing engine never silently downgrades a searchable export.
    """
    from pypdf import PdfReader,PdfWriter,Transformation,PageObject
    images=list(images)
    if not images:raise ValueError('PDF needs at least one scanned page.')
    for im in images:validate(im)
    if ocr_pages is not None:
        ocr_pages=list(ocr_pages)
        if len(ocr_pages)!=len(images):raise ValueError('Each PDF page needs its own OCR result.')
        for im,ocr in zip(images,ocr_pages):
            if ocr is None or not ocr.pdf_bytes:raise ValueError('Run OCR on every page before exporting a searchable PDF.')
            if (ocr.height,ocr.width)!=im.shape[:2]:raise ValueError('OCR is stale after an image change. Run OCR again.')
    def write(tmp):
        writer=PdfWriter()
        for index,im in enumerate(images):
            h,w=im.shape[:2];size=landscape(A4) if w>h else A4;pw,ph=size
            page=PageObject.create_blank_page(width=pw,height=ph)
            bottom=34 if page_numbers else 18
            if ocr_pages is not None:
                source=PdfReader(io.BytesIO(ocr_pages[index].pdf_bytes)).pages[0]
                sw,sh=float(source.mediabox.width),float(source.mediabox.height)
                scale=min((pw-36)/sw,(ph-bottom-18)/sh)
                transform=Transformation().scale(scale).translate((pw-sw*scale)/2,bottom+(ph-bottom-18-sh*scale)/2)
                page.merge_transformed_page(source,transform)
            else:
                buffer=io.BytesIO();pdf=canvas.Canvas(buffer,pagesize=size)
                scale=min((pw-36)/w,(ph-bottom-18)/h)
                rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB) if im.ndim==3 else im
                pdf.drawImage(ImageReader(Image.fromarray(rgb)),(pw-w*scale)/2,bottom+(ph-bottom-18-h*scale)/2,width=w*scale,height=h*scale)
                pdf.save();page.merge_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
            if page_numbers:page.merge_page(PdfReader(io.BytesIO(_number_overlay(pw,ph,index+1,len(images)))).pages[0])
            writer.add_page(page)
        writer.add_metadata({'/Title':'SmartScan searchable document' if ocr_pages is not None else 'SmartScan document'})
        with open(tmp,'wb') as stream:writer.write(stream)
    return _atomic(path,write)
