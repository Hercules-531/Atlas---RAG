"""Local source previews only. Images never enter embedding or LLM payloads."""
import hashlib
import io
import json
import posixpath
import re
import threading
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image,ImageOps
from .config import setting

MEDIA_VERSION=1
LOCK=threading.RLock()
SUPPORTED={'.pdf','.docx','.xlsx'}
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def folder(path):
    path=Path(path)
    return path.parent/'media'/path.stem

def clear(path):
    target=folder(path).resolve();base=(Path(path).parent/'media').resolve()
    if target.parent!=base:raise ValueError('Invalid local media directory')
    if target.exists():
        for child in target.iterdir():
            if child.is_file():child.unlink()
        target.rmdir()

def _rels(archive,part):
    name=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
    if name not in archive.namelist():return {}
    result={}
    for entry in ET.fromstring(archive.read(name)):
        if entry.attrib.get('TargetMode')=='External':continue
        target=entry.attrib.get('Target','')
        resolved=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(part),target))
        if not resolved.startswith('../'):result[entry.attrib.get('Id')]=resolved
    return result

def _images(path):
    if path.suffix.lower()=='.pdf':
        import pymupdf as fitz
        with fitz.open(path) as doc:
            if doc.is_encrypted:raise ValueError('Encrypted PDFs cannot provide previews')
            if len(doc)>setting('max_pdf_pages'):raise ValueError('PDF exceeds page limit')
            for index,page in enumerate(doc):
                images=page.get_images(full=True);seen=set()
                for info in images:
                    xref=info[0]
                    if xref in seen:continue
                    seen.add(xref)
                    if info[2]*info[3]>setting('max_source_image_pixels'):
                        raise ValueError('Embedded PDF image exceeds the preview pixel limit')
                    raw=doc.extract_image(xref)
                    if raw:yield raw['image'],f'page {index+1}','embedded'
                # Drawings/charts may be vector graphics rather than embedded bitmaps.
                if not images and page.get_drawings():
                    scale=min(1.5,2048/max(page.rect.width,page.rect.height))
                    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                    yield pix.tobytes('png'),f'page {index+1}','page_preview'
    elif path.suffix.lower()=='.docx':
        from docx import Document
        from docx.oxml.ns import qn
        doc=Document(path)
        def paragraph_images(paragraph,location):
            for blip in paragraph._p.iter(qn('a:blip')):
                rid=blip.get(qn('r:embed'))
                if rid in doc.part.related_parts:yield doc.part.related_parts[rid].blob,location,'embedded'
        for index,paragraph in enumerate(doc.paragraphs):yield from paragraph_images(paragraph,f'paragraph {index+1}')
        for ti,table in enumerate(doc.tables):
            for ri,row in enumerate(table.rows):
                for cell in row.cells:
                    for paragraph in cell.paragraphs:yield from paragraph_images(paragraph,f'table {ti+1}, row {ri+1}')
    elif path.suffix.lower()=='.xlsx':
        with zipfile.ZipFile(path) as archive:
            workbook='xl/workbook.xml';relations=_rels(archive,workbook)
            for sheet in ET.fromstring(archive.read(workbook)).iter():
                if sheet.tag.rsplit('}',1)[-1]!='sheet':continue
                part=relations.get(sheet.get('{'+REL+'}id'))
                if not part or part not in archive.namelist():continue
                worksheet_rels=_rels(archive,part)
                for drawing in ET.fromstring(archive.read(part)).iter():
                    if drawing.tag.rsplit('}',1)[-1]!='drawing':continue
                    drawing_part=worksheet_rels.get(drawing.get('{'+REL+'}id'))
                    if not drawing_part or drawing_part not in archive.namelist():continue
                    image_rels=_rels(archive,drawing_part)
                    for anchor in ET.fromstring(archive.read(drawing_part)):
                        row=next((int(e.text)+1 for e in anchor.iter() if e.tag.rsplit('}',1)[-1]=='row'),1)
                        for blip in anchor.iter():
                            if blip.tag.rsplit('}',1)[-1]!='blip':continue
                            image_part=image_rels.get(blip.get('{'+REL+'}embed'))
                            if image_part and image_part in archive.namelist():
                                yield archive.read(image_part),f'{sheet.get("name")}, row {row}','embedded'

def index(path):
    """Idempotent bounded extraction. Caller runs it inside the parsing worker."""
    path=Path(path)
    if path.suffix.lower() not in SUPPORTED:return {'images':[],'warnings':[]}
    destination=folder(path);manifest=destination/'manifest.json'
    with LOCK:
        signature=[path.stat().st_size,path.stat().st_mtime_ns,MEDIA_VERSION,
                   setting('max_source_images'),setting('max_source_image_pixels'),setting('max_source_image_mib')]
        if manifest.exists():
            cached=json.loads(manifest.read_text(encoding='utf-8'))
            if cached.get('signature')==signature:return cached
        clear(path);destination.mkdir(parents=True,exist_ok=True)
        result={'signature':signature,'images':[],'warnings':[]};total=0;seen=set()
        try:
            if path.suffix.lower() in ('.docx','.xlsx'):
                with zipfile.ZipFile(path) as archive:
                    if sum(i.file_size for i in archive.infolist())>setting('max_archive_mib')*1048576:
                        raise ValueError('Archive exceeds uncompressed-size limit')
            for raw,location,kind in _images(path):
                if len(result['images'])>=setting('max_source_images'):
                    result['warnings'].append('Additional images omitted: preview count limit reached.');break
                digest=hashlib.sha256(raw+location.encode()).hexdigest()[:24]
                if digest in seen:continue
                seen.add(digest)
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error',Image.DecompressionBombWarning)
                        with Image.open(io.BytesIO(raw)) as original:
                            if original.width*original.height>setting('max_source_image_pixels'):
                                result['warnings'].append('An image exceeded the preview pixel limit.');continue
                            oriented=ImageOps.exif_transpose(original).convert('RGBA')
                            canvas=Image.new('RGBA',oriented.size,'white');canvas.alpha_composite(oriented)
                            image=canvas.convert('RGB')
                            image.thumbnail((2048,2048))
                            output=io.BytesIO();image.save(output,format='JPEG',quality=90)
                            encoded=output.getvalue()
                    if total+len(encoded)>setting('max_source_image_mib')*1048576:
                        result['warnings'].append('Additional images omitted: preview storage limit reached.');break
                    filename=digest+'.jpg';(destination/filename).write_bytes(encoded);total+=len(encoded)
                    result['images'].append({'id':digest,'filename':filename,'location':location,'kind':kind,'width':image.width,'height':image.height})
                except Exception:
                    result['warnings'].append('An embedded image could not be decoded safely.')
        except Exception as exc:
            result['warnings'].append('Image previews unavailable: '+str(exc))
        temporary=manifest.with_suffix('.tmp');temporary.write_text(json.dumps(result),encoding='utf-8');temporary.replace(manifest)
        return result

def read(path):
    manifest=folder(path)/'manifest.json'
    if not manifest.exists():return {'images':[],'warnings':[]}
    return json.loads(manifest.read_text(encoding='utf-8'))

def for_location(path,location,document_id):
    result=[]
    page=re.search(r'page (\d+)',location)
    paragraph_numbers=[int(n) for n in re.findall(r'paragraph (\d+)',location)]
    for item in read(path)['images']:
        match=item['location']==location
        if page:match=item['location']=='page '+page[1]
        elif paragraph_numbers:
            p=re.search(r'paragraph (\d+)',item['location'])
            match=bool(p and min(paragraph_numbers)<=int(p[1])<=max(paragraph_numbers))
        if match:result.append({k:v for k,v in item.items() if k!='filename'}|{'url':f'/api/files/{document_id}/images/{item["id"]}'})
    return result
