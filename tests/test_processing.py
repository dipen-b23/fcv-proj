from pathlib import Path
import cv2,numpy as np,pytest
from pypdf import PdfReader
from src.enhancement import MODES,enhance,EnhancementSettings
from src.image_processing import load_image,TECHNIQUES,demonstrate,crop,resize_longest
from src.export import save_image,save_pdf
from src.pipeline import scan

@pytest.mark.parametrize('mode',MODES)
def test_modes(image,mode):
    out=enhance(image,mode)
    assert out.shape[:2]==image.shape[:2] and out.dtype==np.uint8
    if mode=='Black-and-white':assert set(np.unique(out))<={0,255}
    if mode=='Original scan':assert np.array_equal(out,image)

@pytest.mark.parametrize('technique',TECHNIQUES)
def test_technique_lab(image,technique):
    out=demonstrate(image,technique)
    assert out.dtype==np.uint8 and out.size>0

@pytest.mark.parametrize('extension',['.png','.jpg'])
def test_image_roundtrip(image,tmp_path,extension):
    path=save_image(image,tmp_path/('扫描'+extension));out=load_image(path)
    assert out.shape==image.shape
    if extension=='.png':assert np.array_equal(out,image)

def test_pdf(image,tmp_path):
    path=save_pdf([image,cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)],tmp_path/'scan.pdf')
    reader=PdfReader(path);assert len(reader.pages)==2
    assert all(len(page.images)>=1 for page in reader.pages)

def test_invalid_input(tmp_path):
    path=tmp_path/'invalid.jpg';path.write_text('not an image')
    with pytest.raises(ValueError):load_image(path)
    with pytest.raises(ValueError):load_image(tmp_path/'missing.png')

def test_exif(tmp_path):
    from PIL import Image
    im=Image.new('RGB',(100,200),'white');exif=im.getexif();exif[274]=6
    path=tmp_path/'rotated.jpg';im.save(path,exif=exif)
    assert load_image(path).shape[:2]==(100,200)

def test_manual_fallback():
    blank=np.full((500,700,3),125,np.uint8)
    assert scan(blank).output is None
    result=scan(blank,corners=[[20,20],[600,20],[600,450],[20,450]])
    assert result.output is not None and result.detection.confidence is None

def test_invalid_parameters(image):
    with pytest.raises(ValueError):enhance(image,'bad')
    with pytest.raises(ValueError):enhance(image,settings=EnhancementSettings(gamma=0))
    with pytest.raises(ValueError):crop(image,-1,0,100,100)

def test_empty_pdf(tmp_path):
    with pytest.raises(ValueError):save_pdf([],tmp_path/'bad.pdf')

def test_cli(image,tmp_path):
    from src.cli import main
    source=tmp_path/'input.png';save_image(image,source)
    assert main([str(source),str(tmp_path/'scan.pdf'),'--stages',str(tmp_path/'stages')])==0
    assert (tmp_path/'stages'/'quality.json').exists()
    blank=tmp_path/'blank.png';save_image(np.full((300,400,3),100,np.uint8),blank)
    assert main([str(blank),str(tmp_path/'no.png')])==2
    assert main([str(tmp_path/'missing.png'),str(tmp_path/'no.png')])==1
