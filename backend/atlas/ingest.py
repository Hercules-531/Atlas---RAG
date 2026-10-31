import csv
import json
import multiprocessing as mp
import os
import re
import threading
import uuid
import zipfile
from pathlib import Path
from .config import DATA, setting
from .store import db, rows
from .embeddings import embed, collection
from .chunking import parents,split_children,VERSION

LOCK = threading.Lock()
CANCELLED = set()

def extract(path):
    ext = path.suffix.lower()
    from .multimodal import SUPPORTED,extract as extract_media
    if ext in SUPPORTED:
        yield from extract_media(path)
        return
    if ext in ('.xlsx', '.docx'):
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist()) > setting('max_archive_mib') * 1048576:
                raise ValueError('Archive exceeds uncompressed-size limit')
    if ext == '.pdf':
        from pypdf import PdfReader
        pdf = PdfReader(path)
        if pdf.is_encrypted:
            raise ValueError('Encrypted PDFs are unsupported')
        if len(pdf.pages) > setting('max_pdf_pages'):
            raise ValueError(f"PDF exceeds {setting('max_pdf_pages')} pages")
        for i, page in enumerate(pdf.pages):
            yield page.extract_text() or '', f'page {i+1}'
    elif ext == '.docx':
        from docx import Document
        doc = Document(path)
        for i, p in enumerate(doc.paragraphs):
            yield p.text, f'paragraph {i+1}'
        for ti, table in enumerate(doc.tables):
            headers = [c.text for c in table.rows[0].cells]
            for ri, row in enumerate(table.rows[1:]):
                yield json.dumps(dict(zip(headers, [c.text for c in row.cells])), ensure_ascii=False), f'table {ti+1}, row {ri+2}'
    elif ext == '.csv':
        with path.open(encoding='utf-8-sig', errors='strict', newline='') as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i >= setting('max_table_rows'):
                    raise ValueError('CSV exceeds row limit')
                yield json.dumps(row, ensure_ascii=False), f'row {i+2}'
    elif ext == '.xlsx':
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=True)
        count = 0
        try:
            for sheet in book:
                iterator = sheet.iter_rows(values_only=True)
                headers = [str(v or f'field_{i}') for i,v in enumerate(next(iterator, []))]
                for ri, row in enumerate(iterator):
                    count += 1
                    if count > setting('max_table_rows'):
                        raise ValueError('Workbook exceeds row limit across sheets')
                    yield json.dumps(dict(zip(headers, row)), default=str, ensure_ascii=False), f'{sheet.title}, row {ri+2}'
        finally:
            book.close()
    elif ext == '.json':
        import ijson
        with path.open('rb') as f:
            start = f.read(4096).lstrip()[:1]
            f.seek(0)
            if start == b'[':
                for i, item in enumerate(ijson.items(f, 'item')):
                    if i >= setting('max_table_rows'):
                        raise ValueError('JSON exceeds record limit')
                    yield json.dumps(item, default=str, ensure_ascii=False), f'item {i+1}'
            else:
                # Limit input before materializing non-array structures.
                if path.stat().st_size > setting('max_extracted_text_mib') * 1048576:
                    raise ValueError('JSON object exceeds text limit; use an array of records')
                yield json.dumps(json.load(f), ensure_ascii=False), 'object'
    elif ext in ('.txt', '.md'):
        with path.open(encoding='utf-8-sig') as f:
            for i, line in enumerate(f):
                yield line.rstrip(), f'line {i+1}'
    else:
        raise ValueError('Supported types: PDF, DOCX, TXT, MD, CSV, XLSX, JSON')

def parse_worker(path, output, error):
    try:
        from .media import index as index_images
        image_manifest=index_images(Path(path))
        total = 0
        with Path(output).open('w', encoding='utf-8') as f:
            for text, location in extract(Path(path)):
                total += len(text.encode('utf-8'))
                if total > setting('max_extracted_text_mib') * 1048576:
                    raise ValueError(f"Extracted text exceeds {setting('max_extracted_text_mib')} MiB")
                if text.strip():
                    f.write(json.dumps([text, location], ensure_ascii=False)+'\n')
        if total == 0:
            if image_manifest['images']:
                with Path(output).open('w',encoding='utf-8') as f:
                    for location in dict.fromkeys(i['location'] for i in image_manifest['images']):
                        f.write(json.dumps(['This source contains a local source image. Image contents have not been interpreted.',location])+'\n')
            else:raise ValueError('No text found. Scanned PDF OCR is not supported.')
    except Exception as exc:
        Path(error).write_text(str(exc), encoding='utf-8')

def update(docid, status, error='', progress=0):
    with db() as c:
        c.execute('UPDATE documents SET status=?,error=?,progress=? WHERE id=?', (status,error,progress,docid))

def ingest(docid):
    with LOCK:
        records = rows('SELECT * FROM documents WHERE id=?', (docid,))
        if not records or docid in CANCELLED:
            return
        path = Path(records[0]['path'])
        output, error = path.with_suffix('.parsed'), path.with_suffix('.error')
        process = None
        try:
            update(docid, 'parsing')
            process = mp.get_context('spawn').Process(target=parse_worker,args=(str(path),str(output),str(error)))
            process.start()
            import time
            end = time.monotonic()+setting('parse_timeout_seconds')
            while process.is_alive():
                process.join(.25)
                if docid in CANCELLED or time.monotonic() > end:
                    process.terminate(); process.join()
                    raise ValueError('Parsing cancelled or exceeded 15-minute deadline')
            if error.exists():
                raise ValueError(error.read_text(encoding='utf-8'))
            if process.exitcode != 0:
                raise ValueError('Parser worker failed')
            update(docid, 'embedding')
            batch = []
            count = 0
            def flush():
                nonlocal count
                if not batch:
                    return
                if docid in CANCELLED:
                    raise ValueError('Indexing cancelled')
                vectors = embed([b[1] for b in batch])
                collection().add(ids=[b[0] for b in batch], embeddings=vectors,
                    metadatas=[{'document_id':docid} for b in batch])
                with db() as c:
                    c.executemany('INSERT INTO chunks VALUES (?,?,?,?)', [(b[0],docid,b[1],b[2]) for b in batch])
                count += len(batch)
                update(docid, 'embedding', progress=count)
                batch.clear()
            with output.open(encoding='utf-8') as f:
                records=(json.loads(line) for line in f)
                for text, location in parents(records):
                    parent_id=uuid.uuid4().hex
                    with db() as c:c.execute('INSERT INTO parents VALUES (?,?,?,?)',(parent_id,docid,text,location))
                    for part,start_offset,end_offset in split_children(text,embedder=embed,semantic=os.getenv('ATLAS_SEMANTIC_CHUNKING','false').lower()=='true'):
                        child_id=uuid.uuid4().hex
                        with db() as c:c.execute('INSERT INTO chunk_parents VALUES (?,?,?,?)',(child_id,parent_id,start_offset,end_offset))
                        batch.append((child_id,part,location))
                        if len(batch) >= 8:
                            flush()
            flush()
            update(docid, 'ready', progress=count)
        except Exception as exc:
            update(docid, 'error', str(exc))
            with db() as c:
                c.execute('DELETE FROM chunks WHERE document_id=?',(docid,))
                c.execute('DELETE FROM parents WHERE document_id=?',(docid,))
            try:
                collection().delete(where={'document_id':docid})
            except Exception:
                pass
        finally:
            output.unlink(missing_ok=True); error.unlink(missing_ok=True)

def retrieve_dense_legacy(question, document_ids=None):
    query = collection().query(query_embeddings=embed([question], query=True), n_results=8,
        **({'where':{'document_id':{'$in':document_ids}}} if document_ids else {}))
    result = []
    for chunkid in query['ids'][0]:
        found = rows('SELECT chunks.*, documents.name FROM chunks JOIN documents ON chunks.document_id=documents.id WHERE chunks.id=? AND documents.status="ready"',(chunkid,))
        if found:
            result.append(found[0])
    return result

def retrieve(question,document_ids=None):
    from .retrieval import retrieve as hybrid
    return hybrid(question,document_ids)

def reindex(document_ids=None):
    """Rebuild only the index; preserve uploaded originals and prior receipts/history."""
    documents=rows('SELECT id FROM documents WHERE status IN ("ready","error")')
    if document_ids is not None:documents=[d for d in documents if d['id'] in document_ids]
    for document in documents:
        docid=document['id'];CANCELLED.discard(docid)
        with LOCK:
            update(docid,'queued')
            collection().delete(where={'document_id':docid})
            with db() as c:
                c.execute('DELETE FROM chunks WHERE document_id=?',(docid,))
                c.execute('DELETE FROM parents WHERE document_id=?',(docid,))
        ingest(docid)
    with db() as c:c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('chunking_version',VERSION))
    return rows('SELECT name,status,error,progress FROM documents')
