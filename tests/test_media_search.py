import math
import pytest
from atlas import media_search as search


def hit(key,text,channel='visual',name='flower.mp4',doc='video'):
    prefix=next(p for p,c in search.PREFIXES.items() if c==channel)
    return {'id':key,'document_id':doc,'name':name,'text':prefix+text,'location':'time 00:00:03.000'}


def vectors(monkeypatch,candidates,scores):
    monkeypatch.setattr(search.retrieval,'retrieve',lambda *a,**k:candidates)
    def embed(texts,query=False):
        if query:return [[1.,0.]]
        return [[scores[t],math.sqrt(1-scores[t]**2)] for t in texts]
    monkeypatch.setattr(search,'embed',embed)


def test_telescope_does_not_match_flower_video_by_its_speech(monkeypatch):
    candidates=[hit('flower','A glowing blue flower.'),hit('speech','The telescope recorded 18 sessions.','speech'),
        hit('audio','The telescope recorded 18 sessions.','speech','observatory.wav','audio')]
    vectors(monkeypatch,candidates,{'A glowing blue flower.':.57,'The telescope recorded 18 sessions.':.78})
    assert [r['id'] for r in search.search('telescope',['video','audio'])]==['audio']
    assert search.search('telescope',['video'],content_mode='visual')==[]
    assert {r['id'] for r in search.search('telescope',['video','audio'],'speech')}=={'speech','audio'}


def test_synonyms_work_without_exact_word_overlap(monkeypatch):
    vectors(monkeypatch,[hit('flower','A glowing blue flower.')],{'A glowing blue flower.':.71})
    assert search.search('blossom',['video'])[0]['match_type']=='visual'


def test_unrelated_nearest_neighbor_and_generic_speech_are_rejected(monkeypatch):
    candidates=[hit('flower','A glowing flower.'),hit('code','The project code is amber.','speech','sound.wav','audio')]
    vectors(monkeypatch,candidates,{'A glowing flower.':.57,'The project code is amber.':.68})
    assert search.search('submarine',['video','audio'],'all')==[]


def test_best_timestamp_per_file_and_channel(monkeypatch):
    candidates=[hit('near','Telescope sessions.','speech'),hit('best','The telescope recorded 18 sessions.','speech')]
    vectors(monkeypatch,candidates,{'Telescope sessions.':.75,'The telescope recorded 18 sessions.':.85})
    assert [r['id'] for r in search.search('telescope',['video'],'speech')]==['best']


def test_plural_words_and_filename_do_not_override_scene(monkeypatch):
    candidates=[hit('flower','A blue flower.',name='telescope.mp4')]
    vectors(monkeypatch,candidates,{'A blue flower.':.60})
    assert search.search('telescope',['video'])==[]
    assert search.search('flowers',['video'])[0]['id']=='flower'


def test_unknown_source_and_empty_scope_never_get_fabricated_matches(monkeypatch):
    vectors(monkeypatch,[hit('unknown','No media description.')|{'text':'unrecognized data'}],{})
    assert search.search('flower',['video'])==[]
    assert search.search('flower',[])==[]
    with pytest.raises(ValueError):search.search('flower',['video'],'invalid')
