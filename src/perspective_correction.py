"""Convex four-point validation, stable cyclic ordering, projective rectification."""
import cv2
import numpy as np

def order_corners(points):
    pts = np.asarray(points, np.float32)
    if pts.shape != (4,2) or not np.isfinite(pts).all():
        raise ValueError("Exactly four finite (x,y) corners are required.")
    if len(np.unique(pts,axis=0)) != 4:
        raise ValueError("Corners must be distinct.")
    center = pts.mean(axis=0)
    pts = pts[np.argsort(np.arctan2(pts[:,1]-center[1],pts[:,0]-center[0]))]
    pts = np.roll(pts,-int(np.argmin(pts.sum(axis=1))),axis=0)
    # Image y points downward: TL, TR, BR, BL gives positive signed area.
    if cv2.contourArea(pts,oriented=True) < 0: pts = pts[[0,3,2,1]]
    if not cv2.isContourConvex(pts) or cv2.contourArea(pts) < 16:
        raise ValueError("Corners must form a convex document with a nonzero area.")
    if np.min(np.linalg.norm(pts-np.roll(pts,1,axis=0),axis=1)) < 4:
        raise ValueError("Document edges are too short.")
    return pts

def validate_corners(points, shape):
    pts = order_corners(points)
    h,w = shape[:2]
    if (pts < 0).any() or (pts[:,0] > w-1).any() or (pts[:,1] > h-1).any():
        raise ValueError("All corners must be inside the image.")
    return pts

def warp_document(image, points, max_side=2600):
    pts = validate_corners(points,image.shape)
    tl,tr,br,bl = pts
    width = max(np.linalg.norm(tr-tl),np.linalg.norm(br-bl))
    height = max(np.linalg.norm(bl-tl),np.linalg.norm(br-tr))
    scale = min(1.,max_side/max(width,height))
    w,h = max(8,int(round(width*scale))),max(8,int(round(height*scale)))
    target = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    homography = cv2.getPerspectiveTransform(pts,target)
    if not np.isfinite(homography).all() or abs(np.linalg.det(homography)) < 1e-12:
        raise ValueError("Degenerate perspective transform. Move the corners apart.")
    return cv2.warpPerspective(image,homography,(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE), homography
