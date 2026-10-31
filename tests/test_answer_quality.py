import numpy as np
from atlas.chunking import sentences
from atlas.privacy import terms
from atlas import retrieval

def test_soft_wrapped_definition_is_one_complete_sentence():
    text='SignalMapper constructs\nadaptive visual supervision from\nmultiple representations.'
    units=sentences(text)
    assert len(units)==1 and units[0][0]==text

def test_paragraph_boundaries_still_separate_units():
    text='A heading\n\nA method learns useful\nrepresentations.'
    assert len(sentences(text))==2

def test_search_terms_normalize_camel_case_and_ligatures():
    assert terms('SignalMapper')==terms('signal mapper')
    assert terms('Diﬀusion')==terms('diffusion')

def test_title_fragments_do_not_replace_real_definition(monkeypatch):
    def encode(texts,query=False):
        values=[]
        for text in texts:
            v=np.zeros(768);v[0]=1;values.append(v)
        return values
    monkeypatch.setattr(retrieval,'embed',encode)
    chunks=[{'text':'Signal\n\nMapper\n\nSignalMapper is a framework for mapping neural signals into images.','index_context':'Document: SignalMapper'}]
    retrieval.compress_sentences('What is signal mapper?',chunks)
    selected=[chunks[0]['sentence_units'][i] for i in chunks[0]['selected_sentences']]
    assert any('mapping neural signals into images' in text for text in selected)
    assert 'Signal' not in selected and 'Mapper' not in selected
