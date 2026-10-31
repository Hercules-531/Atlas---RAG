import json
import zipfile
from pathlib import Path
import pytest
from atlas import ingest
from atlas.calculations import calculate

def test_archive_bomb_rejected(tmp_path,monkeypatch):
    path=tmp_path/'large.docx'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('huge.xml','x'*1048577)
    original=ingest.setting
    monkeypatch.setattr(ingest,'setting',lambda key:1 if key=='max_archive_mib' else original(key))
    with pytest.raises(ValueError,match='uncompressed'):list(ingest.extract(path))

def test_extracted_text_byte_limit(tmp_path,monkeypatch):
    source=tmp_path/'a.txt';source.write_text('é'*600000,encoding='utf-8')
    original=ingest.setting
    monkeypatch.setattr(ingest,'setting',lambda key:1 if key=='max_extracted_text_mib' else original(key))
    output=tmp_path/'out';error=tmp_path/'error'
    ingest.parse_worker(str(source),str(output),str(error))
    assert 'Extracted text exceeds' in error.read_text()

def test_calculations():
    chunks=[{'text':json.dumps({'salary':n})} for n in ['100','200','300']]
    assert calculate('What is the total salary?',chunks)['value']=='600'
    assert calculate('What is the average salary?',chunks)['value']=='200'
    assert calculate('What is the highest salary?',chunks)['value']=='300'
    assert calculate('How many records?',chunks)['value']=='3'

def test_incomplete_calculation_refused():
    with pytest.raises(ValueError,match='plain numeric'):
        calculate('total salary',[{'text':'{"salary":"unknown"}'}])
