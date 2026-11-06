"""Additional native visual controls for SmartScan."""
import cv2,numpy as np
from PySide6.QtCore import Qt,Signal,QRectF
from PySide6.QtGui import QImage,QPixmap,QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget
from .image_processing import resize_longest


def preview_pixmap(image):
    image=resize_longest(image,1800)[0]
    rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB) if image.ndim==3 else cv2.cvtColor(image,cv2.COLOR_GRAY2RGB)
    rgb=np.ascontiguousarray(rgb)
    return QPixmap.fromImage(QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy())

class ComparisonCanvas(QWidget):
    """One registered page: corrected input on the left, enhancement on the right."""
    positionChanged=Signal(int)
    def __init__(self):
        super().__init__();self.setMinimumSize(300,280);self.before=None;self.after=None;self.position=50;self.shape=None;self.dragging=False
    def set_pair(self,before,after):
        self.before=preview_pixmap(before) if before is not None else None
        self.after=preview_pixmap(after) if after is not None else None
        self.shape=after.shape[:2] if after is not None else None;self.update()
    def set_position(self,value):self.position=int(np.clip(value,0,100));self.update()
    def rect_for_image(self):
        h,w=self.shape;scale=min((self.width()-30)/w,(self.height()-50)/h)
        return QRectF((self.width()-w*scale)/2,(self.height()-h*scale)/2,w*scale,h*scale)
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#0d1720'))
        if self.before is None or self.after is None:
            p.setPen(QColor('#96a9bb'));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Scan a page to compare its appearance');return
        rect=self.rect_for_image();divider=rect.left()+rect.width()*self.position/100
        p.drawPixmap(rect,self.before,QRectF(self.before.rect()))
        p.save();p.setClipRect(QRectF(divider,rect.top(),rect.right()-divider,rect.height()));p.drawPixmap(rect,self.after,QRectF(self.after.rect()));p.restore()
        p.setPen(QPen(QColor('#50d6b5'),3));p.drawLine(int(divider),int(rect.top()),int(divider),int(rect.bottom()))
        p.setPen(QColor('#c4d6df'));p.drawText(int(rect.left()),int(rect.top()-10),'CORRECTED INPUT');p.drawText(int(rect.right()-145),int(rect.top()-10),'ENHANCED OUTPUT')
    def update_position(self,event):
        if self.shape is None:return
        rect=self.rect_for_image();value=int(np.clip(100*(event.position().x()-rect.left())/rect.width(),0,100))
        self.set_position(value);self.positionChanged.emit(value)
    def mousePressEvent(self,event):self.dragging=True;self.update_position(event)
    def mouseMoveEvent(self,event):
        if self.dragging:self.update_position(event)
    def mouseReleaseEvent(self,event):self.dragging=False;self.update_position(event)
