"""Small exact, repository-native SVG diagrams, independent of online rendering."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'docs'

def diagram(name,boxes,links,width=1000,height=660):
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#31596b"/></marker></defs>',f'<rect width="{width}" height="{height}" fill="#f4f8fa"/>']
    for a,b,label in links:
        x,y,w,h,_=boxes[a];xx,yy,ww,hh,_=boxes[b]
        if yy>y+h:p=(x+w/2,y+h,xx+ww/2,yy)
        elif xx>x+w:p=(x+w,y+h/2,xx,yy+hh/2)
        else:p=(x,y+h/2,xx+ww,yy+hh/2)
        svg.append(f'<line x1="{p[0]}" y1="{p[1]}" x2="{p[2]}" y2="{p[3]}" stroke="#31596b" stroke-width="2" marker-end="url(#arrow)"/>')
        if label:svg.append(f'<text x="{(p[0]+p[2])/2+6}" y="{(p[1]+p[3])/2-8}" font-family="sans-serif" font-size="13" fill="#31596b">{label}</text>')
    for x,y,w,h,lines in boxes:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="#188c79" stroke-width="2"/>')
        for i,line in enumerate(lines):svg.append(f'<text x="{x+w/2}" y="{y+27+i*21}" text-anchor="middle" font-family="sans-serif" font-size="{16 if i==0 else 13}" fill="#153345">{line}</text>')
    svg.append('</svg>');(ROOT/name).write_text('\n'.join(svg),encoding='utf-8')

def main():
    diagram('architecture.svg',[
        (60,30,350,75,['Desktop workspace','PySide6 views, controls, corner editing']),
        (590,30,350,75,['Command-line interface','Headless, same CV pipeline']),
        (285,175,430,80,['Shared processing modules','Scan pipeline / OCR / document workflows']),
        (60,330,260,90,['CV and quality modules','Contours + homography','Five modes and diagnostics']),
        (370,330,260,90,['Local OCR engine','Tesseract TXT / TSV / PDF','Installed language data']),
        (680,330,260,90,['Export','Images / TXT / searchable PDF','Aligned text and page numbers']),
        (285,525,430,80,['Local history and document pages','SQLite + image / OCR snapshots','Persistent order; no network API'])],[(0,2,'Qt workers'),(1,2,''),(2,3,''),(2,4,''),(2,5,''),(3,6,''),(4,6,''),(5,6,'')])
    diagram('pipeline.svg',[
        (70,25,390,76,['Acquire + validate','EXIF, bounds, original-pixel coordinates']),
        (70,145,390,76,['Detect + rank quadrilaterals','Canny / Otsu / HSV + Hough']),
        (570,145,350,76,['Manual corners','Fallback or boundary adjustment']),
        (70,275,390,76,['Validate + perspective warp','Ordered corners, 3 x 3 homography']),
        (70,405,390,76,['Enhance + compare','Five modes and user parameters']),
        (570,405,350,76,['Quality + stage inspection','Input/output diagnostics and real images']),
        (70,535,390,76,['Export document','Images / OCR text / searchable PDF'])],[(0,1,''),(1,2,'inspect / fail'),(1,3,'accepted'),(2,3,'apply'),(3,4,''),(4,5,''),(4,6,'')])
if __name__=='__main__':main()
