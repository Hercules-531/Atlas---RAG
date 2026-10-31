import hashlib
import json
import re
import secrets
from functools import lru_cache
import yaml
from .config import ROOT, setting

PATTERNS = {
 'email': r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',
 'phone': r'(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\d[ -]?){10,12}(?!\w)',
 'identity': r'\b(?:[A-Z]{5}\d{4}[A-Z]|\d{3}-\d{2}-\d{4}|\d{4}[ -]\d{4}[ -]\d{4})\b',
 'birth': r'(?i)\b(?:dob|date of birth|born)\s*[:=]?\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}',
 'address': r'(?i)\b\d{1,5}\s+(?:[\w]+\s+){1,5}(?:street|road|avenue|lane|drive|nagar)\b',
 'card': r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)',
}
STOP = set('what is the a an of for to in how much many does do are was and please tell me about'.split())

def terms(text):
    return set(re.findall(r'[\w]+',text.lower().replace('_',' ').replace('-',' '))) - STOP

def luhn(text):
    digits = [int(n) for n in re.sub(r'\D','',text)]
    if not 13 <= len(digits) <= 19 or len(set(digits)) < 2:
        return False
    return sum(n if i%2 else (2*n-9 if n>4 else 2*n) for i,n in enumerate(reversed(digits),1))%10 == 0

def policy():
    return yaml.safe_load((ROOT/'config/policy.yaml').read_text())

@lru_cache
def ner():
    import spacy
    try:
        return spacy.load('en_core_web_sm')
    except OSError:
        raise RuntimeError('Local NER model missing. Run uv run atlas setup-models.')

def detect(text, use_ner=True):
    spans = []
    patterns = list(PATTERNS.items()) + [(p['category'],p['pattern']) for p in policy().get('custom_patterns',[])]
    for category, pattern in patterns:
        for m in re.finditer(pattern,text):
            if category != 'card' or luhn(m.group()):
                spans.append((m.start(),m.end(),category))
    # Labelled prose fields are recognized independently of table parsing.
    for category,names in policy()['sensitive_fields'].items():
        for name in names:
            for m in re.finditer(r'(?i)\b'+re.escape(name)+r'\s*[:=]\s*([^;\n.!?]+)',text):
                spans.append((m.start(1),m.end(1),category))
    if use_ner:
        for e in ner()(text[:100000]).ents:
            if e.label_ in ('PERSON','GPE','LOC'):
                spans.append((e.start_char,e.end_char,'name' if e.label_=='PERSON' else 'location'))
    selected=[]
    for span in sorted(spans,key=lambda s: (s[0],-(s[1]-s[0]))):
        if not selected or span[0] >= selected[-1][1]:
            selected.append(span)
    return selected

def placeholder(value,mapping,source=''):
    existing=next((k for k,v in mapping.items() if v==value),None)
    if existing:return existing
    for _ in range(16):
        token='[[ATLAS_'+secrets.token_hex(16)+']]'
        if token not in mapping and token not in source:
            mapping[token]=value
            return token
    raise ValueError('Could not allocate a collision-free placeholder')

def tokenize(text, mapping, use_ner=True):
    spans = detect(text,use_ner)
    categories=[]
    for start,end,category in reversed(spans):
        token = placeholder(text[start:end],mapping,text)
        text=text[:start]+token+text[end:]
        categories.append(category)
    return text,categories

def restore(text,mapping):
    for token,original in mapping.items():
        text=text.replace(token,original)
    return text

def estimate(text):
    # Conservative local estimate; not a Gemini tokenizer or observed usage.
    return max(1, (len(text.encode('utf-8'))+2)//3)

def minimize(question,chunks,use_ner=True):
    mapping={}; withheld=[]; sent=[]; citations=[]; needed=[]
    qterms=terms(question)
    masked_question,categories=tokenize(question,mapping,use_ner)
    needed.extend(categories)
    fields=policy()['sensitive_fields']
    total_fields=0; sent_fields=0
    anchors={}
    for chunk in chunks:
        try:
            obj=json.loads(chunk['text'])
            if isinstance(obj,dict):
                anchors[chunk['id']]=sum(len(str(v))>2 and bool(re.search(r'(?<!\w)'+re.escape(str(v))+r'(?!\w)',question,re.I)) for v in obj.values() if isinstance(v,(str,int)))
        except ValueError:
            pass
    best_anchor=max(anchors.values(),default=0)
    for index,chunk in enumerate(chunks):
        text=chunk['text']; selected=[]
        if best_anchor and chunk['id'] in anchors and anchors[chunk['id']]<best_anchor:
            withheld.append({'label':'different record','category':'not relevant','value':text,'source':chunk['document_id']})
            continue
        try:
            obj=json.loads(text)
        except (ValueError,TypeError):
            obj=None
        if isinstance(obj,dict):
            for key,value in obj.items():
                total_fields+=1
                category=next((cat for cat, names in fields.items() if any(n in key.lower() for n in names)),None)
                relevant=bool(terms(key)&qterms)
                anchor=isinstance(value,(str,int)) and len(str(value))>2 and bool(re.search(r'(?<!\w)'+re.escape(str(value))+r'(?!\w)',question,re.I))
                if anchor:
                    relevant=True;category=category or 'identity'
                if category and not relevant:
                    withheld.append({'label':str(key),'category':category,'value':str(value),'source':chunk['document_id']})
                    continue
                if not relevant:
                    withheld.append({'label':str(key),'category':'unselected field','value':str(value),'source':chunk['document_id']})
                    continue
                if category:
                    token=placeholder(str(value),mapping,text)
                    if anchor:
                        masked_question=re.sub(r'(?<!\w)'+re.escape(str(value))+r'(?!\w)',lambda _:token,masked_question,flags=re.I)
                    selected.append(f'{key}: {token}'); needed.append(category)
                else:
                    masked,cats=tokenize(str(value),mapping,use_ner)
                    selected.append(f'{key}: {masked}'); needed.extend(cats)
                sent_fields+=1
        else:
            sentences=chunk.get('sentence_units') or re.split(r'(?<=[.!?])\s+|\n',text)
            ranked=sorted(enumerate(sentences),key=lambda x:len(terms(x[1])&qterms),reverse=True)
            chosen=set(chunk['selected_sentences']) if 'selected_sentences' in chunk else {i for i,s in ranked[:3] if terms(s)&qterms}
            for i,sentence in enumerate(sentences):
                total_fields+=1
                if i not in chosen:
                    withheld.append({'label':'unselected sentence','category':'not relevant','value':sentence,'source':chunk['document_id']})
                    continue
                spans=detect(sentence,use_ner)
                # Withhold explicitly labelled unrelated fields within a relevant sentence.
                # Other entities in selected evidence require tokenized-use consent.
                for a,b,cat in reversed(spans):
                    prefix=sentence[max(0,a-60):a]
                    label=next((name for names in fields.values() for name in names if re.search(r'(?i)\b'+re.escape(name)+r'\s*[:=]\s*$',prefix)),None)
                    if label and not (terms(label)&qterms):
                        withheld.append({'label':label,'category':cat,'value':sentence[a:b],'source':chunk['document_id']})
                        sentence=sentence[:a]+'[withheld]'+sentence[b:]
                masked,cats=tokenize(sentence,mapping,use_ner)
                selected.append(masked); needed.extend(cats)
                sent_fields+=1
        if selected:
            ref='S'+str(index+1)
            evidence='['+ref+'] '+'; '.join(selected)
            if estimate('\n'.join(sent+[evidence])) <= setting('context_tokens'):
                sent.append(evidence)
                citations.append({'id':ref,'chunk_id':chunk['id'],'document_id':chunk['document_id'],'name':chunk.get('name',''),'location':chunk['location'],'text':chunk['text']})
            else:
                withheld.append({'label':'context budget','category':'budget','value':text,'source':chunk['document_id']})
    return {'question':masked_question,'context':'\n'.join(sent),'mapping':mapping,'needed':sorted(set(needed)),
        'withheld':withheld,'citations':citations,'total_fields':total_fields,'sent_fields':sent_fields,
        'policy_hash':hashlib.sha256((ROOT/'config/policy.yaml').read_bytes()).hexdigest()}
