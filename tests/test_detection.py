import json
from pathlib import Path
import cv2,numpy as np,pytest
from src.image_processing import load_image
from src.document_detection import detect_document
from src.perspective_correction import order_corners,warp_document,validate_corners
ROOT=Path(__file__).resolve().parents[1]

def polygon_iou(a,b,shape):
    mask1=np.zeros(shape,np.uint8);mask2=mask1.copy()
    cv2.fillConvexPoly(mask1,np.int32(a),1);cv2.fillConvexPoly(mask2,np.int32(b),1)
    return np.count_nonzero(mask1&mask2)/max(1,np.count_nonzero(mask1|mask2))

@pytest.mark.parametrize('name',['normal','tilted','perspective','low_contrast','noisy','blurred','shadows','dark_background','bright_background','multiple_objects'])
def test_synthetic_detection(name):
    image=load_image(ROOT/'sample_images'/f'{name}.png')
    expected=json.loads((ROOT/'sample_images'/'ground_truth.json').read_text())[name]['corners']
    result=detect_document(image)
    assert result.corners is not None,name
    assert polygon_iou(result.corners,expected,image.shape[:2])>.90

def test_no_document():
    result=detect_document(load_image(ROOT/'sample_images'/'no_document.png'))
    assert result.corners is None

def test_blank():assert detect_document(np.zeros((500,700,3),np.uint8)).corners is None

@pytest.mark.parametrize('points',[[[0,0]]*4,[[0,0],[10,10],[20,20],[30,30]],[[0,0],[100,0],[30,20],[0,100]]])
def test_invalid_corners(points):
    with pytest.raises(ValueError):order_corners(points)

def test_order_permutations():
    import itertools
    expected=np.float32([[10,10],[90,10],[90,100],[10,100]])
    for p in itertools.permutations(expected):assert np.array_equal(order_corners(p),expected)

def test_transform_projects_corners(image):
    points=np.float32([[390,150],[1030,65],[1140,980],[230,1030]])
    out,H=warp_document(image,points)
    projected=cv2.perspectiveTransform(points[None],H)[0];h,w=out.shape[:2]
    assert np.allclose(projected,[[0,0],[w-1,0],[w-1,h-1],[0,h-1]],atol=.001)

def test_large_input(image):
    large=cv2.resize(image,(6000,4200))
    result=detect_document(large)
    assert result.corners is not None
    corrected,_=warp_document(large,result.corners)
    assert max(corrected.shape[:2])<=2600

def test_out_of_bounds():
    with pytest.raises(ValueError):validate_corners([[-1,0],[50,0],[50,50],[0,50]],(100,100))


def test_partial_page_requests_manual():
    image=load_image(ROOT/'sample_images'/'partial_page.png')
    assert detect_document(image).corners is None
