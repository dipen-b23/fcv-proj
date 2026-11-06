"""Sequential, cancellable batch scanning; one bad page never discards other results."""
from pathlib import Path
import json
from .image_processing import load_image
from .pipeline import scan
from .enhancement import EnhancementSettings
from .ocr import recognize
from .export import save_image,save_pdf


def process_batch(paths,directory,mode='Enhanced document',settings=None,ocr=False,language='eng',psm=3,binary=None,store=None,progress=None,cancel=None):
    paths=list(paths);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);rows=[]
    for index,path in enumerate(paths):
        if cancel and cancel.is_set():break
        row={'source':str(path),'status':'error','message':'','history_id':None}
        try:
            image=load_image(path);result=scan(image,mode,settings or EnhancementSettings())
            if result.output is None:row.update(status='manual_required',message='No reliable boundary. Open this image and select corners manually.')
            else:
                # Index prefix avoids duplicate basenames within a batch. GUI selects a new run folder.
                base=directory/f'{index+1:03d}_{Path(path).stem}'
                save_image(result.output,base.with_suffix('.png'));row['image']=str(base.with_suffix('.png'))
                recognized=None
                if ocr:
                    try:
                        recognized=recognize(result.output,language,psm,binary)
                        save_pdf([result.output],base.with_suffix('.pdf'),ocr_pages=[recognized])
                        base.with_suffix('.txt').write_text(recognized.text,encoding='utf-8')
                        row['pdf']=str(base.with_suffix('.pdf'));row['text']=recognized.text
                    except ValueError as exc:row['message']='Scan saved; OCR failed: '+str(exc)
                row['status']='ocr_error' if ocr and recognized is None else 'saved'
                if store:
                    record=store.add(result.output,Path(path).name,mode,{'input_quality':result.input_quality,'output_quality':result.output_quality},recognized);row['history_id']=record['id']
        except (ValueError,OSError) as exc:row['message']=str(exc)
        rows.append(row)
        if progress:progress(index+1,len(paths),f'{Path(path).name}: {row["status"]}')
    # Every source receives a status, including cancellation before starting it.
    for path in paths[len(rows):]:rows.append({'source':str(path),'status':'cancelled','message':'Not processed; batch was cancelled.','history_id':None})
    (directory/'batch_report.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    return rows
