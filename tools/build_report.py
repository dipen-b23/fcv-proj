"""Build submission PDF + editable Markdown from measured project evidence.
Run from project root after tools/evaluate.py and pytest with --junitxml.
"""
from pathlib import Path
import sys,json,re,html,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reportlab.platypus import (SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,KeepTogether)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/'docs'
for name,file in [('SS','DejaVuSans.ttf'),('SSBold','DejaVuSans-Bold.ttf'),('SSMono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(ROOT/'assets'/'fonts'/file)))

NAVY=colors.HexColor('#153345');TEAL=colors.HexColor('#128571');GRAY=colors.HexColor('#546677')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodySS',fontName='SS',fontSize=10.2,leading=15,spaceAfter=8,textColor=NAVY))
styles.add(ParagraphStyle(name='HeadSS',fontName='SSBold',fontSize=19,leading=24,spaceAfter=13,textColor=NAVY))
styles.add(ParagraphStyle(name='SubSS',fontName='SSBold',fontSize=12,leading=16,spaceBefore=9,spaceAfter=7,textColor=TEAL))
styles.add(ParagraphStyle(name='CaptionSS',fontName='SS',fontSize=8.5,leading=12,textColor=GRAY,spaceAfter=9))
styles.add(ParagraphStyle(name='CellSS',fontName='SS',fontSize=8.0,leading=11,textColor=NAVY))
styles.add(ParagraphStyle(name='RefSS',fontName='SS',fontSize=9,leading=13,spaceAfter=6,textColor=NAVY))
styles.add(ParagraphStyle(name='EquationSS',fontName='SSMono',fontSize=8.5,leading=13,backColor=colors.HexColor('#eef5f6'),borderPadding=8,spaceBefore=5,spaceAfter=11))
PAGE_W,PAGE_H=A4;WIDTH=PAGE_W-96
story=[];markdown=[]

def clean(s):
    return s.replace('≥','>=').replace('≤','<=').replace('×','x').replace('–','-').replace('—','-').replace('→','->').replace('•','-').replace('σ','sigma').replace('Δ','Delta').replace('⊕','(+)').replace('⊖','(-)')
def p(s,style='BodySS'):
    s=clean(s);story.append(Paragraph(html.escape(s).replace('`','').replace('\n','<br/>'),styles[style]));markdown.append(s+'\n')
def head(s):p(s,'HeadSS');markdown[-1]='## '+clean(s)+'\n'
def sub(s):p(s,'SubSS');markdown[-1]='### '+clean(s)+'\n'
def page():story.append(PageBreak());markdown.append('\n<!-- page break -->\n')
def eq(s):p(s,'EquationSS');markdown[-1]='```text\n'+s+'\n```\n'
def fig(file,caption,max_height=350):
    from PIL import Image as PI
    with PI.open(DOCS/file) as im:w,h=im.size
    scale=min(WIDTH/w,max_height/h);story.append(Image(str(DOCS/file),width=w*scale,height=h*scale));p(caption,'CaptionSS');markdown.append(f'![{caption}]({file})\n')
def table(headers,rows,widths=None):
    data=[[Paragraph(html.escape(clean(str(c))),styles['CellSS']) for c in row] for row in [headers]+rows]
    t=Table(data,colWidths=widths or [WIDTH/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d9eee8')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f7f9')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,TEAL)]));story.append(t);story.append(Spacer(1,9))
    markdown.append('| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(clean(str(c)) for c in r)+' |' for r in rows)+'\n')

def render_diagrams():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtCore import Qt
    app=QApplication.instance() or QApplication([])
    for name in ['architecture','pipeline']:
        renderer=QSvgRenderer(str(DOCS/f'{name}.svg'));im=QImage(1600,1056,QImage.Format.Format_ARGB32);im.fill(Qt.GlobalColor.white);painter=QPainter(im);renderer.render(painter);painter.end();im.save(str(DOCS/f'{name}.png'))

def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(TEAL);canvas.setLineWidth(.7);canvas.line(48,42,PAGE_W-48,42)
    canvas.setFont('SS',8);canvas.setFillColor(GRAY);canvas.drawString(48,29,'SMARTSCAN  |  CSE 3176  |  FCV MINI-PROJECT');canvas.drawRightString(PAGE_W-48,29,str(doc.page));canvas.restoreState()

def main():
    evidence=json.loads((DOCS/'evaluation.json').read_text());optional=json.loads((DOCS/'optional_evaluation.json').read_text());tests=ET.parse(DOCS/'test_results.xml').getroot();suites=list(tests.iter('testsuite'))
    count=sum(int(s.get('tests',0)) for s in suites);failed=sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites);seconds=sum(float(s.get('time',0)) for s in suites)
    render_diagrams()
    story.append(Spacer(1,22));p('CSE 3176 - FOUNDATIONS OF COMPUTER VISION','SubSS');story.append(Spacer(1,28))
    story.append(Paragraph('SmartScan',ParagraphStyle(name='CoverTitle',fontName='SSBold',fontSize=44,leading=50,textColor=NAVY)))
    story.append(Spacer(1,16));story.append(Paragraph('Intelligent Document Detection,<br/>Enhancement and Perspective Correction<br/>Using Computer Vision',ParagraphStyle(name='CoverSub',fontName='SS',fontSize=20,leading=28,textColor=TEAL)))
    markdown.append('# SmartScan\n\nIntelligent Document Detection, Enhancement and Perspective Correction Using Computer Vision\n')
    story.append(Spacer(1,40));p('MINI-PROJECT REPORT','SubSS');p('Academic Year 2026 | V Semester | Section A | Batch 2028')
    table(['Team member','Registration number'],[['Madaka Shreyaj Naidu','240962594'],['Advait Balachandar','240962600'],['Dipen Batharaju','240962574']],[WIDTH*.67,WIDTH*.33])
    story.append(Spacer(1,24));p('B.Tech. in Computer Science and Engineering (AI & ML)');p('School of Computer Engineering\nManipal Institute of Technology\nManipal Academy of Higher Education')
    story.append(Spacer(1,20));p('Implementation and test evidence dated 2 November 2026','CaptionSS')
    page();head('1. Abstract and project objectives')
    sub('Abstract')
    p('SmartScan is an offline document-scanning application that detects a visible page, corrects its perspective, improves its presentation and exposes the computer-vision operations behind the result. It uses Python and OpenCV for processing and PySide6 for a desktop workspace. A multi-strategy detector combines edge contours, threshold masks, colour evidence and supporting line intersections. Validated four-corner correspondences define a homography that rectifies the page into a rectangular crop. Five scan modes offer colour, grayscale, binary and enhanced output with user-controlled parameters. A manual corner editor provides a fallback when automatic inference is uncertain.')
    p('The application includes actual intermediate images, an independent FCV technique laboratory, transparent quality diagnostics, local OCR, searchable PDF export, a persistent multipage document manager, page numbering, rotation, batch processing, scan history and a registered before/after slider. Validation uses deterministic generated scenes with known geometric boundaries, unit checks and offscreen GUI integration tests. These results establish behavior on the supplied fixtures; they do not establish accuracy on an unrestricted real-camera dataset.')
    sub('Introduction and problem statement')
    p('Photographs of documents may contain a tilted page, perspective distortion, shadows, low contrast, noise or blur. Manual correction is repetitive, and aggressive image enhancement can reduce readability. The problem is to produce a usable scan while making the underlying FCV techniques understandable and allowing the user to correct errors.')
    sub('Objectives')
    for s in ['Acquire a local image or camera frame and identify a plausible document boundary.','Rectify a planar document using validated four-point geometry.','Offer readable, adjustable scan modes without forcing every algorithm into one chain.','Display original/output views, intermediate stages and interpretable quality metrics.','Export images and PDFs locally, handle failure safely and support an FCV lab demonstration.']:p('- '+s)
    page();head('2. Background and system architecture')
    p('The project follows classical image-processing methods rather than a trained document model. Edge and region methods supply complementary evidence: Canny can retain an edge across intensity changes, while threshold masks can recover a bright region even if its edge is locally weak. Contour simplification identifies geometric candidates, but geometric validity alone cannot prove that an object is paper. The manual editor is therefore a deliberate component of the design.')
    p('Histogram equalization and CLAHE redistribute contrast; Gaussian, median and bilateral filters suppress different noise patterns; thresholding separates foreground and background. A planar homography supplies the geometric correction. OpenCV documentation provides the operation semantics [1-4], while the Qt threading APIs support the responsive frontend [5]. This is background on the methods used, not a comparative literature benchmark.')
    fig('architecture.png','Figure 1. Modular application architecture. GUI and CLI share the same processing pipeline.',330)
    p('Pure processing modules operate on NumPy arrays. The GUI submits loading, CV and export operations to a Qt thread pool, then updates widgets through signals. Camera reading uses a dedicated thread. The source image is retained so that parameter changes do not compound previous enhancement.')
    page();head('3. Proposed methodology')
    fig('pipeline.png','Figure 2. Main processing flow with manual-boundary fallback and inspection.',315)
    sub('Acquisition and bounded processing')
    p('Images are decoded with EXIF orientation applied and converted to BGR. Unicode filenames are supported. Inputs above 40 megapixels are rejected with an actionable message. Detection operates at a longest side of at most 1000 pixels; coordinates are mapped back before warping. Independent technique experiments and stage previews are bounded to 1200 pixels. The final warp has a longest-side cap of 2600 pixels.')
    sub('Boundary proposals and validation')
    p('The detector applies bilateral smoothing, Canny and a 5x5 morphological closing. Otsu, inverted Otsu and low-saturation/bright HSV masks provide further contour sources. Convex hulls of the largest suitable contours are simplified with four perimeter-relative tolerances. Hough-line intersections add supporting quadrilateral proposals. Candidates must be finite, convex, sufficiently large, within the image and free of short edges. Candidates with two or more vertices touching the image frame are rejected to avoid treating a truncated page as complete.')
    page();head('4. Algorithms and enhancement')
    sub('Candidate ranking')
    p('Edge support E measures boundary samples near a Canny edge. P measures median intensity separation between the candidate interior and its surrounding ring. A is a clipped area preference, and R mildly favours rectangular geometry. Weak candidates are rejected; a score below 0.57 requests manual corners. The score is a heuristic evidence value, not a calibrated probability.')
    eq('S = 0.42 E + 0.28 P + 0.18 A + 0.12 R')
    sub('Perspective correction')
    p('The four corners are cyclically ordered around their centroid, rotated to an image-space top-left convention and validated. A projective matrix H maps them to the output rectangle. It has eight independent parameters after scale normalization, so four nondegenerate correspondences supply eight constraints. Width and height are estimated from the larger opposite-edge lengths. OpenCV solves the mapping and inverse-samples using cubic interpolation [1].')
    eq('lambda [u, v, 1]^T = H [x, y, 1]^T\nu = (h11 x + h12 y + h13) / (h31 x + h32 y + h33)')
    p('The method rectifies a visible plane, but it does not recover a true physical page ratio without extra information. It cannot correct curved pages, lens distortion or missing text. No RANSAC claim is made: the implemented warp uses exactly four geometric correspondences.')
    sub('Five scan modes')
    table(['Mode','Implemented behavior'],[['Original scan','Perspective correction only; all appearance controls bypassed.'],['Colour document','Bilateral denoise, gentle CLAHE on Lab lightness, user adjustments.'],['Grayscale document','Grayscale, bilateral denoise, CLAHE and user adjustments.'],['Black-and-white','Denoise and user mapping, then adaptive Gaussian or Otsu threshold.'],['Enhanced document','Colour pipeline with stronger local contrast and optional convolution sharpening.']],[WIDTH*.30,WIDTH*.70])
    page();head('5. Mathematical foundations and quality analysis')
    sub('Enhancement equations')
    eq('Equalization: T(k) = round(255 (CDF(k)-CDFmin)/(1-CDFmin))\nFiltering: J(x,y) = sum_u sum_v K(u,v) I(x+u,y+v)\nLinear mapping: J = clip(alpha (I-127.5) + 127.5 + beta)\nGamma: O = 255 (I/255)^(1/gamma)')
    p('CLAHE clips histogram peaks within tiles before interpolating local mappings; the presets use 8x8 tiles and clip limits 1.6 or 2.0 [2]. The sharpening kernel has axial weights -a and center 1+4a. Gamma above one brightens in this reciprocal convention. Threshold window, threshold offset, brightness, contrast, gamma, denoising and sharpening are adjustable.')
    sub('Edge and focus equations')
    eq('Canny gradient magnitude: G = sqrt(Gx^2 + Gy^2)\nAdaptive threshold: T(x,y) = weighted_local_mean - C\nLaplacian focus proxy: L = Var(Delta I)')
    p('Canny also performs non-maximum suppression and double-threshold hysteresis. Blur usually lowers Laplacian variance, while noise and sharpening can raise it. The noise proxy is 1.4826 times the residual median absolute deviation, preferably in low-gradient regions. These statistics are measured at a longest side of at most 1000 pixels for consistent processing scale.')
    sub('Transparent heuristic quality score')
    eq('Q = 100 (0.15r + 0.15b + 0.25c + 0.30s + 0.15n)\nr=min(1,min(W,H)/1000); b=max(0,1-|mean-180|/180)\nc=min(1,std/55); s=min(1,ln(1+L)/ln(501))\nn=max(0,1-noise/20)')
    p('Excellent is Q>=85, Good >=70, Fair >=50 and Poor below 50. Boundary confidence remains separate; manual selection has no automatic confidence value. Opposite-edge length asymmetry is a shape proxy, not a calibrated camera pose. The input includes the background and output is cropped, so their scores do not measure identical content. Binarization can improve this score while damaging small text. The model has not been scientifically calibrated or validated for readability.')
    page();head('6. FCV technique mapping')
    p('The independent technique laboratory demonstrates alternatives without changing the saved scan. The full function-level map, parameters, limitations and alternative approaches appear in docs/FCV_GUIDE.md.')
    table(['Technique','Module','Purpose / demonstration'],[
        ['Acquisition, resize, crop, gray, normalization','image_processing.py','Open / Webcam; bounded scale; Center crop, Grayscale and Normalize experiments.'],
        ['Histogram, equalization, CLAHE','image_processing.py; enhancement.py','Histogram / Equalize / CLAHE experiments; contrast in scan presets.'],
        ['Brightness, contrast, gamma','enhancement.py','Centered linear mapping and LUT; adjustable workspace controls.'],
        ['Gaussian, median, bilateral','image_processing.py; document_detection.py','Filter comparison in lab; bilateral preprocessing in scan pipeline.'],
        ['Convolution sharpening','enhancement.py','Adjustable symmetric kernel; independent Sharpen experiment.'],
        ['Canny and morphology','document_detection.py','Edge detection and closing stages; gap bridging.'],
        ['Binary, Otsu, adaptive','image_processing.py; enhancement.py','Segmentation and clean binary scan output.'],
        ['Colour segmentation, K-means','image_processing.py; document_detection.py','HSV proposal; HSV and 3-cluster Lab experiments.'],
        ['Contours and polygon approximation','document_detection.py','Contour candidate overlay; convex four-point proposals.'],
        ['Hough line detection','document_detection.py','Supporting line intersections; line overlay in technique lab.'],
        ['Corners, homography, warp','perspective_correction.py','Numbered manual/automatic corners; corrected page and saved H matrix.'],
        ['Quality metrics','quality_analysis.py','Input/output scores, metrics and acquisition suggestions.']],[WIDTH*.27,WIDTH*.27,WIDTH*.46])
    page();head('7. Implementation and user interface')
    fig('workspace.png','Figure 3. Actual offscreen capture of the implemented desktop workspace, showing the supplied perspective fixture.',320)
    p('The workspace provides original and processed views, a boundary overlay, drag-adjustable corner points and explicit processing actions. Tabs expose real intermediate images, independent FCV experiments, common-warp mode comparison and a quality report. Sliders take effect when Update enhancement is clicked. Automatic boundary failure leaves the output empty and image export disabled; the user can select corners manually.')
    p('PNG/JPEG/PDF exports use temporary files followed by atomic replacement. A selected directory can receive all processing previews and a quality JSON file including corner coordinates and H. The document queue retains up to 20 selected page references persistently through SQLite and local scan snapshots. Recent image paths are stored locally through QSettings; original images are not uploaded. The optional webcam dialog reads frames locally and reports unavailability gracefully.')
    sub('Project structure and reproducibility')
    p('The main.py entry point launches the GUI or routes --cli to the headless scanner. src contains focused modules for acquisition, detection, geometry, enhancement, quality, OCR, history, batch, export, orchestration and UI. tools contains fixture, evaluation, diagram and report builders. tests supplies unit and offscreen integration checks. Exact dependency versions and a Windows batch launcher are included. The core application requires no internet connection after installation.')
    page();head('8. OCR and extended document workflows')
    p('All optional features from the implementation brief are included. Text recognition is provided by the locally installed Tesseract engine, while document detection and image enhancement remain classical OpenCV. The application sends no document images to an external service. Engine and language data installation are checked explicitly [7].')
    table(['Requested optional feature','Implemented workflow'],[
        ['OCR and extracted text preview','Local Tesseract invocation returns TXT, TSV words/confidence and PDF. Preview, copy and UTF-8 text export are available.'],
        ['Searchable PDF','The image and Tesseract invisible text layer are transformed together to A4, preserving alignment [8,9].'],
        ['Multipage scanning and numbering','Processed snapshots form a persistent ordered document. Move/remove/preview controls and Page N of total footers follow final page order.'],
        ['Rotation and manual boundaries','90-degree left/right output rotation; corner drag and clear/reselect controls. Rotation composes with the homography.'],
        ['Drag-and-drop and batch processing','One dropped image scans directly; multiple images enter an independent-file batch with cancellation and a JSON report.'],
        ['Scan history','SQLite stores processed image snapshots, OCR text and document order. History supports text/title search, reopen, queue and delete.'],
        ['Comparison slider','A draggable divider compares rectified input and enhanced output in the same geometry. Original/photo comparison remains in Workspace.']],[WIDTH*.31,WIDTH*.69])
    p('Changing enhancement or rotation invalidates current OCR. A requested searchable export runs missing recognition and reports configuration/engine failures instead of silently becoming an image-only PDF. Batch OCR failure retains the successful PNG and reports ocr_error; a failed boundary is manual_required and can be opened for correction. Cancellation takes effect between pages.')
    p('The document queue contains at most 20 page references and persists across restarts. History stores processed PNG images and OCR PDF caches; original photographs are not copied. A restored snapshot is displayed as a processed page, without pretending to reconstruct the original photograph. The default storage directory follows the operating system, and SMARTSCAN_DATA_DIR can override it.')
    page();head('8.1 OCR verification and interface')
    fig('ocr_workspace.png','Figure 4. Actual OCR/text interface after recognition of the generated English test page.',300)
    p(f'The OCR evaluation used {optional["engine"]}, selected language eng and a single text-block layout. Its clean generated fixture contained {optional["reference_words"]} reference words ({optional["reference_characters"]} characters after normalization). Case, punctuation and whitespace were normalized before computing edit distance. No real-camera or multilingual performance is inferred from this fixture.')
    table(['Measured property','Observed result'],[
        ['Character edits / reference characters',f'{optional["character_edits"]} / {optional["reference_characters"]}'],
        ['Word edits / reference words',f'{optional["word_edits"]} / {optional["reference_words"]}'],
        ['Searchable PDF and numbering',f'{optional["pdf_pages"]} pages; text extraction on every page: {optional["searchable_text_on_all_pages"]}; numbering: {optional["numbering_verified"]}'],
        ['Queue restart and history text search',f'{optional["queue_restart_verified"]}; {optional["history_text_search_verified"]}'],
        ['Mixed batch outcome',', '.join(optional['batch_statuses'])]],[WIDTH*.52,WIDTH*.48])
    p('The observed zero edit counts apply only to this simple known-text fixture. Engine confidence is a separate, uncalibrated value and is not substituted for an accuracy measurement. The complete recognized text, metric methodology and PDF verification flags are recorded in optional_evaluation.json. The example searchable PDF and recognized TXT are included for direct inspection.')

    page();head('9. Results and discussion')
    p('Evaluation uses 12 deterministic synthetic scenes derived from a generated document. Ten complete-page scenes have geometric ground-truth corners; two stress/negative cases test fallback behavior. Polygon intersection-over-union (IoU) compares the selected quadrilateral with ground truth. IoU = intersection area / union area. These are fixture results, not an estimate of general document-detection accuracy.')
    rows=[]
    for r in evidence['cases']:
        rows.append([r['case'].replace('_',' '),'Yes' if r['detected'] else 'Manual fallback',f"{r['polygon_iou']:.4f}" if r['polygon_iou'] is not None else 'Not scored',f"{r['elapsed_ms']:.1f}"])
    table(['Generated scene','Boundary found','Polygon IoU','Pipeline ms'],rows,[WIDTH*.32,WIDTH*.26,WIDTH*.21,WIDTH*.21])
    scored=[r['polygon_iou'] for r in evidence['cases'] if r['polygon_iou'] is not None]
    p(f'The ten scored scenes produced IoU values from {min(scored):.4f} to {max(scored):.4f}. The negative scene and truncated-page fixture requested manual selection. Timing values are single observations of the shared pipeline, including quality analysis, on the current Linux execution environment. They exclude image decoding, GUI paint and export. They are not a hardware benchmark or a Windows performance claim.')
    p('The results show consistent corner geometry on controlled backgrounds and photometric changes. A high overlap does not prove that text quality improved. The blurred example remains limited by its missing spatial detail; processing cannot reverse information loss. The independent lab and quality warnings make these distinctions visible.')
    page();head('10. Qualitative outputs')
    fig('results_contact_sheet.jpg','Figure 5. Actual generated scenes and program outputs: perspective, shadows, low contrast and no-document fallback.',600)
    page();head('11. Testing and verification')
    p(f'The recorded pytest run executed {count} tests with {failed} failures/errors in {seconds:.2f} seconds. Machine-readable JUnit output is included as docs/test_results.xml. The evaluation measurements are saved separately as docs/evaluation.json. All results in this report derive from those files.')
    table(['Verification area','Executed checks'],[
        ['Boundary detection','Ten synthetic positive scenes; negative circular object; blank frame; truncated-page rejection.'],
        ['Geometry','All 24 permutations of a rectangle; invalid/concave/degenerate points; bounds; exact corner reprojection under H.'],
        ['Enhancement and experiments','All five presets; binary output values; 18 lab operations; invalid parameters.'],
        ['Image I/O and exports','Invalid/missing input; EXIF orientation; Unicode PNG/JPEG round-trip; two-page PDF with embedded images.'],
        ['Large input','6000x4200 BGR array; detection coordinate mapping and output-size cap.'],
        ['Quality','Blur reduces Laplacian proxy; added noise increases flat-field noise proxy; finite bounded scores.'],
        ['GUI and CLI','Actual shipping Qt interface; background timer; manual editing; rotation; mode/wipe comparison; OCR; persistent queue; batch import; CLI status codes.'],
        ['Real OCR and searchable PDFs','Actual Tesseract text/boxes, PDF text extraction on every page, numbering, stale-result rejection, missing language/executable errors.'],
        ['Persistence and batch failures','History and queue restored through fresh instances, OCR text search, mixed file failures, PNG retention on OCR error, cancellation between pages.']],[WIDTH*.27,WIDTH*.73])
    p('The final GUI integration run exercises event processing while scanning, confirming that a timer continues to fire. It does not prove responsiveness under all hardware or file-system conditions. Image/PDF exports are parsed back to verify structure, not merely checked for file existence.')
    sub('Environment and local validation scope')
    p(f'Execution: {evidence["platform"]}; Python {evidence["python"]}. Dependencies: '+', '.join(f'{k} {v}' for k,v in evidence['dependencies'].items())+'.')
    p('A physical webcam, native Windows windowing, camera permission behavior, and diverse real phone photographs were not tested in this environment. Before evaluation, install from requirements on the target laptop, open a phone photo, adjust corners, test every preset, verify image/PDF outputs, and try the webcam if available. Detailed steps are in docs/TESTING.md.')
    page();head('12. Limitations and future scope')
    sub('Known limitations')
    p('The detector is geometry-driven and selects one likely page. A rectangular non-document object can be mistaken for paper; no semantic classifier is present. Severe occlusion, background similarity, glare, heavy shadows and extreme perspective can require manual points. A page occupying almost the entire image or touching the frame may be conservatively rejected. Choosing corners cannot recover hidden content.')
    p('The planar warp cannot dewarp a curved book or infer true physical page dimensions. Enhancement cannot reconstruct severe blur or clipped highlights and can amplify artefacts if controls are pushed too far. The quality score and boundary confidence are heuristic. The persistent queue is capped at 20 pages. OCR supports installed language packs but only English printed-text recognition was evaluated here. Handwriting and complex reading order can fail. Rotation is manual; automatic orientation, PDF input parsing and nonplanar page correction are outside this version.')
    sub('Future improvements')
    p('Useful next steps are a diverse annotated real-camera test set, confidence calibration, larger OCR evaluation using character/word error rates, additional language validation, automatic orientation, camera calibration and curved-page correction. Learned segmentation should be considered only after collecting evidence that traditional methods are inadequate for the intended scenes.')
    sub('Conclusion')
    p('SmartScan implements a complete local workflow from image acquisition to an inspectable corrected scan. It combines classical FCV methods with manual control, clear fallback behavior and modular code. The included fixture and integration results provide reproducible evidence for geometry, processing, export and UI behavior. General real-camera performance remains a separate evaluation task, and the application presents its quality estimates with that limitation visible.')
    sub('Demonstration workflow')
    p('Open the bundled sample; inspect the boundary; show the Canny and contour stages; adjust a corner; compare colour and binary output; demonstrate histogram/K-means/Hough independently; explain the score; run OCR and search its PDF; reorder/number a multipage document; show the comparison slider and persistent history; batch-process mixed images; then show the no-document/manual fallback and a locally validated phone image.')
    page();head('13. References and submission resources')
    for ref in [
        '[1] OpenCV. Geometric Transformations of Images, version 4.11.0. https://docs.opencv.org/4.11.0/da/d6e/tutorial_py_geometric_transformations.html',
        '[2] OpenCV. Histograms - Histogram Equalization and CLAHE. https://docs.opencv.org/4.13.0/d5/daf/tutorial_py_histogram_equalization.html',
        '[3] OpenCV. Contours Hierarchy and contour retrieval modes. https://docs.opencv.org/4.13.0/d9/d8b/tutorial_py_contours_hierarchy.html',
        '[4] OpenCV. Image Thresholding. https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html',
        '[5] Qt for Python 6.8. QThread documentation. https://doc.qt.io/qtforpython-6.8/PySide6/QtCore/QThread.html',
        '[6] SmartScan mini-project synopsis supplied with this project, CSE 3176, V Semester, academic year 2026. Primary project-scope source.',
        '[7] Tesseract documentation. Installation and language data. https://tesseract-ocr.github.io/tessdoc/Installation.html',
        '[8] Tesseract documentation. Command Line Usage, text, TSV and PDF output. https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html',
        '[9] pypdf 6.10.0 documentation. Merging PDF files. https://pypdf.readthedocs.io/en/6.10.0/user/merging-pdfs.html'
    ]:p(ref,'RefSS')
    p('Online API references accessed 2 November 2026. The application itself performs no network requests. The OCR error measurements are restricted to the explicitly described generated English fixture; no external benchmark or general OCR accuracy claim is used.')
    sub('Companion resources')
    table(['Resource','Contents'],[['README.md','Installation, launch, feature guide, CLI and demonstration.'],['docs/FCV_GUIDE.md','Exact technique/function map, equations, parameters, limitations and alternatives.'],['docs/VIVA.md','Thirty-seven likely evaluation questions with answers.'],['docs/OCR_SETUP.md','Tesseract installation, language selection and searchable export.'],['docs/OPTIONAL_FEATURES.md','All optional features mapped to code and workflows.'],['docs/TESTING.md','Executed scope, measured outputs and target-laptop verification procedure.'],['docs/IMPLEMENTATION_PLAN.md','Requirements, architecture decisions, phases and acceptance mapping.'],['sample_images/ground_truth.json','Fixture generation truth and scene descriptions.'],['tools/ and tests/','Reproducible generators, evaluator and tests.']],[WIDTH*.43,WIDTH*.57])
    doc=SimpleDocTemplate(str(DOCS/'SmartScan_Project_Report.pdf'),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=44,bottomMargin=58,title='SmartScan - FCV Mini-Project Report',author='Madaka Shreyaj Naidu; Advait Balachandar; Dipen Batharaju')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (DOCS/'PROJECT_REPORT.md').write_text('\n'.join(markdown),encoding='utf-8')
    print('Built report and editable Markdown source.')
if __name__=='__main__':main()
