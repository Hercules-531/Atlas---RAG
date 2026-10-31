import io
import json
import zipfile
from pathlib import Path
from PIL import Image
from atlas import media

def picture(path):
    Image.new('RGB',(120,70),(72,108,164)).save(path)
    return path

def test_pdf_embedded_image_and_page_matching(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    image=picture(tmp_path/'plot.png');path=tmp_path/'source.pdf'
    canvas=Canvas(str(path));canvas.drawString(40,750,'Synthetic plot: revenue is 12 credits.')
    canvas.drawImage(str(image),40,600,width=240,height=140);canvas.showPage();canvas.drawString(40,750,'No figure on page two.');canvas.save()
    result=media.index(path)
    assert len(result['images'])==1,result
    previews=media.for_location(path,'page 1','doc')
    assert len(previews)==1 and previews[0]['url'].startswith('/api/files/doc/images/')
    assert media.for_location(path,'page 2','doc')==[]
    assert media.index(path)==result
    assert 'filename' not in previews[0]

def test_vector_pdf_page_preview(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    path=tmp_path/'chart.pdf';canvas=Canvas(str(path));canvas.drawString(40,750,'Synthetic vector chart')
    canvas.rect(40,500,100,180,fill=True);canvas.save()
    result=media.index(path)
    assert result['images'][0]['kind']=='page_preview'

def test_word_image_location_and_bounded_parent_match(tmp_path):
    from docx import Document
    image=picture(tmp_path/'plot.png');path=tmp_path/'source.docx'
    doc=Document();doc.add_paragraph('First paragraph');doc.add_picture(str(image));doc.add_paragraph('Third paragraph');doc.save(path)
    result=media.index(path)
    assert len(result['images'])==1
    assert result['images'][0]['location']=='paragraph 2'
    assert len(media.for_location(path,'paragraph 1 – paragraph 3','d'))==1
    assert media.for_location(path,'paragraph 3','d')==[]

def test_excel_image_anchor(tmp_path):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as SheetImage
    image=picture(tmp_path/'plot.png');path=tmp_path/'source.xlsx'
    workbook=Workbook();sheet=workbook.active;sheet.title='Customers';sheet.append(['plan']);sheet.append(['Gold']);sheet.add_image(SheetImage(str(image)),'B2');workbook.save(path)
    result=media.index(path)
    assert len(result['images'])==1,result
    assert result['images'][0]['location']=='Customers, row 2'

def test_preview_pixel_limit_and_cleanup(tmp_path,monkeypatch):
    from docx import Document
    image=picture(tmp_path/'plot.png');path=tmp_path/'source.docx';doc=Document();doc.add_picture(str(image));doc.save(path)
    original=media.setting;monkeypatch.setattr(media,'setting',lambda key:1 if key=='max_source_image_pixels' else original(key))
    result=media.index(path)
    assert result['images']==[] and result['warnings']
    media.clear(path);assert not media.folder(path).exists();assert path.exists()

def test_external_office_relationships_are_not_fetched(tmp_path):
    path=tmp_path/'external.zip'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('word/_rels/document.xml.rels','<Relationships><Relationship Id="r1" Target="https://example.invalid/image.png" TargetMode="External"/></Relationships>')
    with zipfile.ZipFile(path) as archive:assert media._rels(archive,'word/document.xml')=={}

def test_media_extraction_requires_no_network(tmp_path,monkeypatch):
    import socket
    from reportlab.pdfgen.canvas import Canvas
    image=picture(tmp_path/'plot.png');path=tmp_path/'offline.pdf';canvas=Canvas(str(path));canvas.drawImage(str(image),40,500);canvas.save()
    attempts=[]
    def blocked(*args,**kwargs):attempts.append(args);raise AssertionError('External network attempted')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    result=media.index(path)
    assert len(result['images'])==1 and attempts==[]

def test_image_count_limit(tmp_path,monkeypatch):
    from docx import Document
    image=picture(tmp_path/'plot.png');path=tmp_path/'limited.docx';doc=Document();doc.add_picture(str(image));doc.add_picture(str(image));doc.save(path)
    original=media.setting;monkeypatch.setattr(media,'setting',lambda key:1 if key=='max_source_images' else original(key))
    result=media.index(path)
    assert len(result['images'])==1 and any('count limit' in warning for warning in result['warnings'])

def test_image_only_pdf_indexes_without_claiming_ocr(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    from atlas.ingest import parse_worker
    image=picture(tmp_path/'plot.png');path=tmp_path/'scan.pdf';canvas=Canvas(str(path));canvas.drawImage(str(image),40,500);canvas.save()
    output=tmp_path/'parsed';error=tmp_path/'error'
    parse_worker(str(path),str(output),str(error))
    assert not error.exists()
    assert 'Image contents have not been interpreted' in output.read_text()

def test_changed_media_limits_invalidate_cache(tmp_path,monkeypatch):
    from docx import Document
    image=picture(tmp_path/'plot.png');path=tmp_path/'limits.docx';doc=Document();doc.add_picture(str(image));doc.add_picture(str(image));doc.save(path)
    assert len(media.index(path)['images'])==2
    original=media.setting;monkeypatch.setattr(media,'setting',lambda key:1 if key=='max_source_images' else original(key))
    assert len(media.index(path)['images'])==1
