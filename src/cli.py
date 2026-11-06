"""Headless scanner and batch tool, including local OCR and searchable PDF export."""
import argparse,json
from pathlib import Path
from .image_processing import load_image
from .pipeline import scan
from .enhancement import MODES
from .export import save_image,save_pdf,save_text
from .ocr import recognize
from .batch import process_batch


def main(argv=None):
    parser=argparse.ArgumentParser(description='SmartScan offline document and OCR scanner')
    parser.add_argument('input');parser.add_argument('output');parser.add_argument('--mode',choices=MODES,default='Enhanced document')
    parser.add_argument('--corners',help='JSON four (x,y) corners in input pixels')
    parser.add_argument('--stages',type=Path,help='Directory for preview stages and metrics JSON')
    parser.add_argument('--ocr',action='store_true',help='Save recognized text beside the output')
    parser.add_argument('--searchable',action='store_true',help='Export a searchable PDF; implies OCR')
    parser.add_argument('--language',default='eng');parser.add_argument('--psm',type=int,choices=[3,6,11],default=3)
    parser.add_argument('--tesseract',help='Optional full path to the local Tesseract executable')
    parser.add_argument('--number-pages',action='store_true')
    parser.add_argument('--batch',action='store_true',help='Input is an image directory, output is a new batch directory')
    args=parser.parse_args(argv)
    try:
        if args.batch:
            paths=sorted(p for p in Path(args.input).iterdir() if p.suffix.lower() in ['.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'])
            if not paths:raise ValueError('No supported image files in this batch directory.')
            if Path(args.output).exists() and any(Path(args.output).iterdir()):raise ValueError('Choose an empty output directory for a new batch.')
            rows=process_batch(paths,args.output,args.mode,ocr=args.ocr or args.searchable,language=args.language,psm=args.psm,binary=args.tesseract)
            print(json.dumps(rows,indent=2));return 0 if all(r['status']=='saved' for r in rows) else 2
        path=Path(args.output)
        if args.searchable and path.suffix.lower()!='.pdf':raise ValueError('--searchable requires a .pdf output filename.')
        result=scan(load_image(args.input),args.mode,corners=json.loads(args.corners) if args.corners else None)
        if result.output is None:print(result.detection.message);return 2
        recognized=recognize(result.output,args.language,args.psm,args.tesseract) if args.ocr or args.searchable else None
        if path.suffix.lower()=='.pdf':save_pdf([result.output],path,args.number_pages,[recognized] if args.searchable else None)
        else:save_image(result.output,path)
        if recognized:save_text(recognized.text,path.with_suffix('.txt'))
        if args.stages:
            args.stages.mkdir(parents=True,exist_ok=True)
            for i,(name,im) in enumerate(result.stages.items()):save_image(im,args.stages/f'{i:02d}_{name.replace(" / ","_").replace(" ","_")}.png')
            (args.stages/'quality.json').write_text(json.dumps({'input':result.input_quality,'output':result.output_quality,'corners':result.detection.corners.tolist(),'homography':result.homography.tolist(),'strategy':result.detection.strategy,'ocr':recognized.metadata() if recognized else None},indent=2),encoding='utf-8')
        print(f'Saved {path} ({result.output.shape[1]}x{result.output.shape[0]}) in {result.elapsed_ms:.0f} ms (CV time; OCR/export excluded)');return 0
    except (ValueError,OSError) as exc:print(f'SmartScan: {exc}');return 1
