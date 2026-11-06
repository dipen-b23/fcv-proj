"""Multi-mask quadrilateral proposal + geometric and photometric evidence ranking."""
from dataclasses import dataclass, field
import cv2
import numpy as np
from .image_processing import gray, resize_longest, validate
from .perspective_correction import order_corners

@dataclass
class Detection:
    corners: object = None
    confidence: float = 0.
    strategy: str = "none"
    message: str = "No reliable document. Select four corners manually."
    stages: dict = field(default_factory=dict)

def _hough_proposals(edges):
    """Intersect separated, roughly horizontal and vertical long line pairs."""
    h,w = edges.shape
    lines = cv2.HoughLinesP(edges,1,np.pi/180,60,minLineLength=min(h,w)*.23,maxLineGap=40)
    if lines is None: return []
    horizontal,vertical = [],[]
    for x1,y1,x2,y2 in lines[:,0]:
        dx,dy = x2-x1,y2-y1
        entry = (np.hypot(dx,dy),np.array([y1-y2,x2-x1,x1*y2-x2*y1],float))
        (horizontal if abs(dx)>abs(dy) else vertical).append(entry)
    horizontal = sorted(horizontal,key=lambda t:-t[0])[:7]
    vertical = sorted(vertical,key=lambda t:-t[0])[:7]
    out=[]
    for i,(_,a) in enumerate(horizontal):
        for _,b in horizontal[i+1:]:
            for j,(_,c) in enumerate(vertical):
                for _,d in vertical[j+1:]:
                    points=[]
                    for u,v in [(a,c),(a,d),(b,d),(b,c)]:
                        p=np.cross(u,v)
                        if abs(p[2])<1e-8: break
                        points.append(p[:2]/p[2])
                    if len(points)==4:
                        p=np.float32(points)
                        if (p>=0).all() and (p[:,0]<w).all() and (p[:,1]<h).all(): out.append(p)
    return out

def detect_document(image):
    validate(image)
    small,scale=resize_longest(image,1000)
    g=gray(small); h,w=g.shape; total=h*w
    smooth=cv2.bilateralFilter(g,7,45,45)
    edges=cv2.Canny(smooth,40,130)
    closed=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    otsu=cv2.threshold(cv2.GaussianBlur(g,(5,5),0),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    hsv=cv2.inRange(cv2.cvtColor(small,cv2.COLOR_BGR2HSV) if small.ndim==3 else cv2.cvtColor(small,cv2.COLOR_GRAY2BGR), (0,0,110),(179,110,255)) if small.ndim==3 else otsu
    stages={"Grayscale":g,"Filtering":smooth,"Edge detection":edges,"Morphological close":closed,"Paper segmentation":otsu}
    if g.std()<3:
        return Detection(stages=stages)
    proposals=[]; contour_view=small.copy()
    if contour_view.ndim==2: contour_view=cv2.cvtColor(contour_view,cv2.COLOR_GRAY2BGR)
    for name,mask in [("Canny",closed),("Otsu",otsu),("Inverted Otsu",255-otsu),("HSV",hsv)]:
        contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:20]:
            if cv2.contourArea(contour)<total*.07: continue
            cv2.drawContours(contour_view,[contour],-1,(100,170,70),1)
            hull=cv2.convexHull(contour)
            for epsilon in [.015,.025,.04,.06]:
                poly=cv2.approxPolyDP(hull,epsilon*cv2.arcLength(hull,True),True)
                if len(poly)==4: proposals.append((name,poly.reshape(4,2)))
    # Hough is a supporting path when contours do not supply a strong boundary.
    proposals.extend(("Hough intersections",p) for p in _hough_proposals(edges))
    distance=cv2.distanceTransform(255-edges,cv2.DIST_L2,3)
    best=None
    for strategy,points in proposals:
        try: p=order_corners(points)
        except ValueError: continue
        area=cv2.contourArea(p)/total
        if not .07<area<.97: continue
        # Reject candidates that merely trace the frame.
        touches=(p[:,0]<3)|(p[:,1]<3)|(p[:,0]>w-4)|(p[:,1]>h-4)
        if touches.sum()>=2: continue
        sides=np.linalg.norm(p-np.roll(p,1,axis=0),axis=1)
        if sides.min()<min(h,w)*.10: continue
        line_support=[]
        for a,b in zip(p,np.roll(p,-1,axis=0)):
            samples=np.linspace(a,b,100).astype(int)
            samples[:,0]=samples[:,0].clip(0,w-1);samples[:,1]=samples[:,1].clip(0,h-1)
            line_support.append(float(np.mean(distance[samples[:,1],samples[:,0]]<4)))
        support=float(np.mean(line_support))
        mask=np.zeros_like(g);cv2.fillConvexPoly(mask,p.astype(int),255)
        inner=cv2.erode(mask,np.ones((11,11),np.uint8))>0
        ring=(cv2.dilate(mask,np.ones((21,21),np.uint8))>0)&(mask==0)
        if not inner.any() or not ring.any(): continue
        separation=min(1.,abs(float(np.median(g[inner]))-float(np.median(g[ring])))/55)
        angles=[]
        for k in range(4):
            a=p[(k-1)%4]-p[k];b=p[(k+1)%4]-p[k]
            angles.append(abs(float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))))
        geometry=1-float(np.mean(angles))
        score=.42*support+.28*separation+.18*min(area/.6,1)+.12*geometry
        if support<.35 or (separation<.12 and support<.8): continue
        if best is None or score>best[0]: best=(score,p,strategy)
    stages["Contour candidates"]=contour_view
    if best is None or best[0]<.57: return Detection(stages=stages)
    score,p,strategy=best
    points=p/scale
    points[:,0]=points[:,0].clip(0,image.shape[1]-1);points[:,1]=points[:,1].clip(0,image.shape[0]-1)
    return Detection(points,round(score,3),strategy,"Boundary found. Check the overlay before exporting.",stages)

def boundary_overlay(image,corners):
    result=image.copy()
    if result.ndim==2: result=cv2.cvtColor(result,cv2.COLOR_GRAY2BGR)
    if corners is not None:
        p=order_corners(corners).astype(int)
        thickness=max(2,max(image.shape[:2])//350)
        cv2.polylines(result,[p],True,(96,220,70),thickness)
        for i,(x,y) in enumerate(p):
            cv2.circle(result,(x,y),thickness*3,(40,180,255),-1)
            cv2.putText(result,str(i+1),(x+8,y+20),0,max(.5,thickness*.25),(20,40,80),thickness)
    return result
