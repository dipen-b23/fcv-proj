"""Image I/O, bounded resizing and independent FCV demonstrations. Arrays are BGR."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 40_000_000

def validate(image):
    if not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8:
        raise ValueError("Expected a nonempty uint8 image.")
    if image.ndim not in (2, 3) or (image.ndim == 3 and image.shape[2] != 3):
        raise ValueError("Expected grayscale or three-channel BGR.")
    if min(image.shape[:2]) < 8:
        raise ValueError("Image must be at least 8 x 8 pixels.")
    return image

def load_image(path):
    """Unicode paths and EXIF orientation supported; refuse decompression-sized input."""
    try:
        with Image.open(Path(path)) as im:
            if im.width * im.height > MAX_PIXELS:
                raise ValueError("Image exceeds 40 megapixels. Resize it before opening.")
            im = ImageOps.exif_transpose(im).convert("RGB")
            return validate(cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR))
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Cannot read this image: {exc}") from exc

def gray(image):
    return image.copy() if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

def resize_longest(image, maximum=1200):
    validate(image)
    scale = min(1., maximum / max(image.shape[:2]))
    if scale == 1:
        return image.copy(), scale
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), scale

def crop(image, x, y, width, height):
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image.shape[1] or y + height > image.shape[0]:
        raise ValueError("Crop must lie inside the image.")
    return image[y:y+height, x:x+width].copy()

def gamma_correct(image, gamma=1.):
    if gamma <= 0:
        raise ValueError("Gamma must be positive.")
    lut = np.round(255 * (np.arange(256) / 255.) ** (1. / gamma)).astype(np.uint8)
    return cv2.LUT(image, lut)

def histogram_image(image):
    canvas = np.full((240, 512, 3), (30, 39, 49), np.uint8)
    hist = cv2.calcHist([gray(image)], [0], None, [256], [0, 256]).ravel()
    hist = hist / max(float(hist.max()), 1) * 205
    pts = np.array([(i*2, 225-int(v)) for i, v in enumerate(hist)], np.int32)
    cv2.polylines(canvas, [pts], False, (190, 220, 55), 2)
    cv2.putText(canvas, "0                  Grayscale levels                  255", (8, 238), 0, .35, (220,220,220), 1)
    return canvas

TECHNIQUES = ["Grayscale", "Normalize", "Histogram", "Equalize", "CLAHE", "Gaussian", "Median", "Bilateral", "Sharpen", "Gamma", "Binary", "Adaptive", "Morphology", "Canny", "HSV paper mask", "K-means", "Hough lines", "Center crop"]

def demonstrate(image, technique):
    """Independent experiments; intentionally bounded to 1200 px for responsiveness."""
    image, _ = resize_longest(image, 1200)
    g = gray(image)
    if technique == "Grayscale": return g
    if technique == "Normalize": return cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX)
    if technique == "Histogram": return histogram_image(image)
    if technique == "Equalize": return cv2.equalizeHist(g)
    if technique == "CLAHE": return cv2.createCLAHE(2., (8,8)).apply(g)
    if technique == "Gaussian": return cv2.GaussianBlur(image, (5,5), 1.2)
    if technique == "Median": return cv2.medianBlur(image, 5)
    if technique == "Bilateral": return cv2.bilateralFilter(image, 7, 45, 45)
    if technique == "Sharpen": return cv2.filter2D(image, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]], np.float32))
    if technique == "Gamma": return gamma_correct(image, 1.4)
    if technique == "Binary": return cv2.threshold(g, 127, 255, cv2.THRESH_BINARY)[1]
    if technique == "Adaptive": return cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    if technique == "Morphology":
        mask = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7,7), np.uint8))
    if technique == "Canny": return cv2.Canny(cv2.GaussianBlur(g,(5,5),0),50,150)
    if technique == "HSV paper mask": return cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV), (0,0,115), (179,110,255))
    if technique == "K-means":
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        # Fixed seed makes educational demonstrations reproducible.
        cv2.setRNGSeed(42)
        _, labels, centers = cv2.kmeans(lab.reshape(-1,3).astype(np.float32),3,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,20,.5),1,cv2.KMEANS_PP_CENTERS)
        return cv2.cvtColor(centers.astype(np.uint8)[labels.ravel()].reshape(lab.shape), cv2.COLOR_LAB2BGR)
    if technique == "Hough lines":
        result = image.copy()
        lines = cv2.HoughLinesP(cv2.Canny(g,50,150),1,np.pi/180,70,minLineLength=min(g.shape)//5,maxLineGap=30)
        if lines is not None:
            for x1,y1,x2,y2 in lines[:,0]: cv2.line(result,(x1,y1),(x2,y2),(70,210,110),2)
        return result
    if technique == "Center crop":
        h,w = g.shape
        return crop(image,w//10,h//10,w*8//10,h*8//10)
    raise ValueError(f"Unknown technique: {technique}")
