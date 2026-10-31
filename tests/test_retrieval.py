import json
import numpy as np
from atlas import store
from atlas.chunking import sentences,split_children,parents
from atlas.retrieval import fuse,lexical

def test_rrf_rewards_agreement():
    assert fuse(['dense','both'],['lexical','both'])[0]=='both'

def test_sentence_boundaries_preserve_exact_offsets():
    text='First sentence.\nA second sentence contains a figure of 1.25 units! Final line'
    for value,a,b in sentences(text):assert text[a:b]==value

def test_semantic_boundaries_use_local_vectors():
    text=' '.join([' '.join(['topic']*45)+'.' for _ in range(6)])
    def vectors(texts):
        result=np.zeros((len(texts),768));result[:3,0]=1;result[3:,1]=1;return result
    parts=split_children(text,embedder=vectors)
    assert len(parts)>=2
    assert all(text[a:b]==part for part,a,b in parts)

def test_table_rows_never_merged_or_split():
    records=[('{"id":1,"value":"a"}','row 2'),('{"id":2,"value":"b"}','row 3')]
    assert list(parents(records))==records
    assert len(split_children(records[0][0]))==1

def test_parent_grouping_preserves_page_boundary():
    assert len(list(parents([('one','page 1'),('two','page 2')])))==2
    result=list(parents([('first','paragraph 1'),('second','paragraph 2')]))
    assert len(result)==1 and 'first\nsecond' in result[0][0]

def test_fts_scope_and_deletion(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    with store.db() as c:
        c.executemany('INSERT INTO documents(id,name,status) VALUES (?,?,?)',[('one','one.txt','ready'),('two','two.txt','ready'),('pending','p.txt','queued')])
        c.executemany('INSERT INTO chunks VALUES (?,?,?,?)',[('c1','one','SKU ZXQ-501 delivery 14 days','line 1'),('c2','two','SKU ZXQ-501 delivery 30 days','line 1'),('c3','pending','SKU ZXQ-501 secret','line 1')])
    assert lexical('ZXQ-501',['one'])==['c1']
    assert 'c3' not in lexical('ZXQ-501')
    with store.db() as c:c.execute('DELETE FROM chunks WHERE id="c1"')
    assert lexical('ZXQ-501',['one'])==[]

def test_fts_input_is_not_sql_or_match_syntax(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    assert lexical('" OR NEAR(*); DROP TABLE documents --')==[]
    assert store.rows('SELECT COUNT(*) n FROM documents')[0]['n']==0

def test_parent_mapping_cleanup(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path);store.init()
    with store.db() as c:
        c.execute('INSERT INTO parents VALUES (?,?,?,?)',('p','doc','text','line 1'))
        c.execute('INSERT INTO chunk_parents VALUES (?,?,?,?)',('unflushed-child','p',0,4))
        c.execute('DELETE FROM parents WHERE id="p"')
    assert store.rows('SELECT * FROM chunk_parents')==[]

def test_semantic_compressor_extracts_original_sentences(monkeypatch):
    from atlas import retrieval
    def embed(texts,query=False):
        vectors=[]
        for text in texts:
            v=np.zeros(768);v[0 if 'warranty' in text.lower() else 1]=1;vectors.append(v)
        return vectors
    monkeypatch.setattr(retrieval,'embed',embed)
    chunks=[{'text':'The warranty lasts 24 months. An unrelated note follows.'}]
    retrieval.compress_sentences('What is the warranty?',chunks)
    assert chunks[0]['selected_sentences']==[0]
    assert chunks[0]['sentence_units'][0]=='The warranty lasts 24 months.'
