"""Search what media depicts separately from what its audio says, entirely locally."""
import numpy as np
from . import retrieval
from .embeddings import embed
from .privacy import terms

PREFIXES={
    'Local sampled-frame description (not verified): ':'visual',
    'Local machine-generated visual description (not verified): ':'visual',
    'Local speech transcript (may contain recognition errors): ':'speech',
}
QUERY_STOP={'show','find','search','image','images','video','videos','audio','clip','clips','picture','pictures','with','containing'}


def content(text):
    for prefix,channel in PREFIXES.items():
        if text.startswith(prefix):return channel,text[len(prefix):]
    return None,''


def keywords(text):
    # Small plural normalization, not a domain vocabulary or a synonym whitelist.
    return {t[:-1] if len(t)>4 and t.endswith('s') and not t.endswith('ss') else t
            for t in terms(text)-QUERY_STOP}


def search(question,document_ids,content_mode='auto'):
    if content_mode not in {'auto','visual','speech','all'}:raise ValueError('Invalid media content mode')
    if not document_ids:return []
    # Search unexpanded timestamp chunks; contextual filenames and rank alone
    # must not turn an unrelated scene into a visual match.
    candidates=retrieval.retrieve(question,document_ids,parent=False,compress=False,limit=64,focus_sources=False)
    eligible=[]
    from .multimodal import AUDIO
    from pathlib import Path
    for hit in candidates:
        channel,text=content(hit['text'])
        allowed=content_mode=='all' or channel==content_mode
        if content_mode=='auto':allowed=channel==('speech' if Path(hit['name']).suffix.lower() in AUDIO else 'visual')
        if channel and allowed:eligible.append((hit,channel,text))
    if not eligible:return []
    query=np.asarray(embed([question],query=True)[0]);query_terms=keywords(question)
    scored=[]
    for start in range(0,len(eligible),8):
        batch=eligible[start:start+8]
        vectors=embed([text for _,_,text in batch])
        for (hit,channel,text),vector in zip(batch,vectors):
            cosine=float(np.asarray(vector)@query)
            overlap=len(keywords(text)&query_terms)/max(1,len(query_terms))
            # These are heuristic cutoffs, not probabilities. Speech needs a
            # stronger semantic-only match to avoid generic short transcripts.
            floor=.64 if channel=='visual' else .74
            if cosine<.55 or (not overlap and cosine<floor):continue
            scored.append((cosine*.65+overlap*.35,hit|{'match_type':channel}))
    seen=set();result=[]
    for _,hit in sorted(scored,key=lambda item:-item[0]):
        key=(hit['document_id'],hit['match_type'])
        if key in seen:continue
        seen.add(key);result.append(hit)
        if len(result)==12:break
    return result
