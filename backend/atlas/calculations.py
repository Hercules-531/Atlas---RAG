"""Bounded deterministic table arithmetic; no generated SQL or code."""
import json
import re
from decimal import Decimal
from .privacy import terms

OPS={'sum':r'\b(total|sum)\b','average':r'\b(average|mean)\b','minimum':r'\b(minimum|lowest|smallest)\b','maximum':r'\b(maximum|highest|largest)\b','count':r'\b(how many|count)\b'}
def operation(question):
    return next((op for op,p in OPS.items() if re.search(p,question,re.I)),None)

def calculate(question,chunks):
    op=operation(question)
    if not op:return None
    records=[]
    for chunk in chunks:
        try:
            obj=json.loads(chunk['text'])
            if isinstance(obj,dict):records.append((chunk,obj))
        except ValueError:pass
    if not records:return None
    if len(records)>10000:raise ValueError('Calculation exceeds 10,000 records. Select fewer documents.')
    if op=='count':return {'operation':op,'field':'records','value':str(len(records)),'rows':len(records)}
    keys=set(k for _,r in records for k in r)
    matching=[k for k in keys if terms(k)&terms(question)]
    if len(matching)!=1:raise ValueError('Specify exactly one numeric field for this calculation.')
    field=matching[0]; values=[]
    for _,record in records:
        value=record.get(field)
        if value is None:raise ValueError('A record lacks the calculation field; cannot calculate a complete result.')
        cleaned=str(value).replace(',','').strip()
        if not re.fullmatch(r'-?\d+(?:\.\d+)?',cleaned):raise ValueError('Calculation requires plain numeric values in every record.')
        values.append(Decimal(cleaned))
    value={'sum':lambda:sum(values),'average':lambda:sum(values)/len(values),'minimum':lambda:min(values),'maximum':lambda:max(values)}[op]()
    return {'operation':op,'field':field,'value':format(value,'f'),'rows':len(records)}
