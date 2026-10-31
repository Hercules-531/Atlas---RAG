import json
import numpy as np
from atlas import store,contextual,retrieval
from atlas.privacy import minimize

def test_prefix_is_bounded_and_extractive():
    text=contextual.context_prefix('Orion_renewal-policy.pdf','Orion renewal terms\nThe notice is 14 days.','The notice is 14 days.','page 2')
    assert 'Orion' in text and 'Section opening:' in text
    assert len(text.split())<=80
    assert 'Generated' not in text

def test_record_context_uses_schema_not_unrelated_values():
    text=contextual.context_prefix('records.csv','{"name":"SENSITIVE_NAME","salary":12345}','{"name":"SENSITIVE_NAME","salary":12345}','row 2')
    assert 'name' in text and 'salary' in text
    assert 'SENSITIVE_NAME' not in text and '12345' not in text

def test_fts_indexes_context_and_deletion_cleans_it(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    with store.db() as c:
        c.execute('INSERT INTO documents(id,name,status) VALUES (?,?,?)',('d','policy.pdf','ready'))
        c.execute('INSERT INTO chunk_contexts VALUES (?,?,?)',('c','Document: Orion spacecraft agreement',contextual.VERSION))
        c.execute('INSERT INTO chunks VALUES (?,?,?,?)',('c','d','Notice is 14 days.','page 2'))
    assert retrieval.lexical('Orion')==['c']
    assert store.rows('SELECT text FROM chunks')[0]['text']=='Notice is 14 days.'
    with store.db() as c:c.execute('DELETE FROM chunks WHERE id="c"')
    assert store.rows('SELECT * FROM chunk_contexts')==[]
    assert retrieval.lexical('Orion')==[]

def test_index_context_never_becomes_answer_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    with store.db() as c:
        c.execute('INSERT INTO documents(id,name,status) VALUES (?,?,?)',('d','PRIVATE_FILENAME.pdf','ready'))
        c.execute('INSERT INTO chunk_contexts VALUES (?,?,?)',('c','PRIVATE_INDEX_ONLY_CONTEXT',contextual.VERSION))
        c.execute('INSERT INTO chunks VALUES (?,?,?,?)',('c','d','The warranty lasts 24 months.','page 2'))
    class Index:
        def query(self,**kwargs):return {'ids':[['c']]}
    monkeypatch.setattr(retrieval,'collection',lambda:Index())
    monkeypatch.setattr(retrieval,'embed',lambda *a,**k:np.ones((1,768)).tolist())
    hits=retrieval.retrieve('What is the warranty?',compress=False)
    plan=minimize('What is the warranty?',hits,use_ner=False)
    assert 'PRIVATE_INDEX_ONLY_CONTEXT' not in plan['context']
    assert 'PRIVATE_FILENAME' not in plan['context']
    assert '24 months' in plan['context']

def test_existing_index_rebuild_preserves_evidence_and_ids(tmp_path,monkeypatch):
    from atlas import embeddings,llm
    from unittest.mock import MagicMock
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    with store.db() as c:
        c.execute('INSERT INTO documents(id,name,status) VALUES (?,?,?)',('d','Orion agreement.pdf','ready'))
        c.execute('INSERT INTO chunks VALUES (?,?,?,?)',('stable-id','d','Notice is 14 days.','page 2'))
    writes=[];inputs=[]
    class Index:
        def upsert(self,**kwargs):writes.append(kwargs)
    def encode(texts):inputs.extend(texts);return np.ones((len(texts),768)).tolist()
    monkeypatch.setattr(embeddings,'collection',lambda:Index());monkeypatch.setattr(embeddings,'embed',encode)
    generate=MagicMock();monkeypatch.setattr(llm,'generate',generate)
    result=contextual.rebuild()
    assert result['indexed_chunks']==1 and result['extra_llm_calls']==0
    assert writes[0]['ids']==['stable-id'] and 'Orion agreement' in inputs[0]
    assert store.rows('SELECT id,text FROM chunks')==[{'id':'stable-id','text':'Notice is 14 days.'}]
    assert retrieval.lexical('Orion')==['stable-id']
    generate.assert_not_called()
