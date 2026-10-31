"""Sentence-preserving semantic children with bounded, local parent context."""
import json
import re
import numpy as np

VERSION='sentence-parent-v1'

def sentences(text):
    matches=list(re.finditer(r'[^\n]+?(?:[.!?](?=\s|$)|$)|[^\n]+$',text,re.M))
    result=[]
    for m in matches:
        value=m.group().strip()
        if value:
            start=m.start()+len(m.group())-len(m.group().lstrip())
            result.append((value,start,start+len(value)))
    return result or [(text,0,len(text))]

def is_record(text):
    try:return isinstance(json.loads(text),dict)
    except (ValueError,TypeError):return False

def split_children(text,embedder=None,semantic=True):
    if is_record(text):return [(text,0,len(text))]
    units=[]
    for value,start,end in sentences(text):
        words=list(re.finditer(r'\S+',value))
        if len(words)<=220:units.append((value,start,end));continue
        for i in range(0,len(words),200):
            group=words[i:i+220];a=start+group[0].start();b=start+group[-1].end()
            units.append((text[a:b],a,b))
    vectors=None
    if semantic and embedder and len(units)>1:
        vectors=np.asarray(embedder([u[0] for u in units]),dtype=np.float32)
    result=[];begin=0;words=0
    for i,(value,a,b) in enumerate(units):
        n=len(value.split())
        boundary=i>begin and (words+n>240 or (words>=80 and vectors is not None and float(vectors[i-1]@vectors[i])<.40))
        if boundary:
            end=units[i-1][2];start=units[begin][1];result.append((text[start:end],start,end))
            # One intact sentence of overlap, only when it fits the next child.
            begin=i-1 if len(units[i-1][0].split())<=40 and i-1>begin else i
            words=sum(len(u[0].split()) for u in units[begin:i])
        words+=n
    if units:
        a=units[begin][1];b=units[-1][2];result.append((text[a:b],a,b))
    return result

def parents(records):
    """Never join table rows. Group short prose units without crossing PDF pages."""
    buffer=[];locations=[];count=0
    def flush():
        distinct=list(dict.fromkeys(locations))
        return '\n'.join(buffer), ' – '.join(distinct if len(distinct)<3 else [distinct[0],distinct[-1]])
    for text,location in records:
        record=is_record(text)
        independent=record or location.startswith(('page ','time ','image '))
        if buffer and (independent or count+len(text.split())>900):
            yield flush();buffer=[];locations=[];count=0
        if independent:
            if len(text.split())>1200 and not record:
                words=list(re.finditer(r'\S+',text))
                for i in range(0,len(words),900):
                    group=words[i:i+1000];yield text[group[0].start():group[-1].end()],location
            else:yield text,location
        else:
            buffer.append(text);locations.append(location);count+=len(text.split())
    if buffer:yield flush()
