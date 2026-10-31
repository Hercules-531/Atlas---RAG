import hashlib
import json
import re
import time
from .config import ROOT, DATA
from .demo import build
from .ingest import extract, retrieve
from .privacy import minimize, estimate, restore
from .llm import generate
from .store import init

def run(live=False,full=False,resume=False):
    init(); gold=build()
    reportdir=ROOT/'reports'; reportdir.mkdir(exist_ok=True)
    path=reportdir/'evaluation.json'
    fingerprint=hashlib.sha256(json.dumps(gold,sort_keys=True).encode()).hexdigest()
    previous=json.loads(path.read_text()) if resume and path.exists() else {}
    if previous and previous.get('fingerprint')!=fingerprint: raise ValueError('Gold dataset changed; cannot resume')
    results=previous.get('results',[]) if live else []
    report={'status':'running','fingerprint':fingerprint,'live':live,'results':results,'offline_checks':[],
        'token_estimates':'UTF-8 bytes / 3; not Gemini tokenizer counts','billing':'Free tier user configured; invoice unverified',
        'pricing_source':'https://ai.google.dev/gemini-api/docs/pricing','pricing_usd_per_million':{'input':.30,'output':2.50}}
    sources={}
    for q in gold:
        if q['dataset'] not in sources:
            sources[q['dataset']]=[{'id':str(i),'document_id':q['dataset'],'name':q['dataset'],'text':text,'location':location} for i,(text,location) in enumerate(extract(ROOT/'demo/sources'/q['dataset']))]
    def save():
        completed=[r for r in results if r.get('status')=='completed']
        report['summary']={'completed_requests':len(completed),'failed_requests':len([r for r in results if r.get('status')=='failed']),
            'expected_paired_requests':len(gold)*2,'offline_cases':len(report['offline_checks']),
            'pipeline_unrelated_canary_occurrences':sum(r.get('canary_leaks',0) for r in completed if r['arm']=='pipeline') if any(r['arm']=='pipeline' for r in completed) else None,
            'accuracy':{arm: {'correct':sum(r.get('correct',False) for r in completed if r['arm']==arm),'completed':sum(r['arm']==arm for r in completed)} for arm in ('baseline','pipeline')}}
        checks=report['offline_checks']
        report['summary']['average_context_tokens_withheld_percent_estimate']=round(sum(max(0,1-c['minimized_tokens_estimate']/max(1,c['full_tokens_estimate']))*100 for c in checks)/len(checks),2) if checks else None
        report['summary']['observed_usage_totals']={arm:{'input_tokens':sum(r['input_tokens'] or 0 for r in completed if r['arm']==arm),'output_tokens':sum(r['output_tokens'] or 0 for r in completed if r['arm']==arm)} for arm in ('baseline','pipeline')}
        report['summary']['prune_reported_savings_usd']=sum(r.get('prune_metadata',{}).get('cost_saved',0) or 0 for r in completed)
        report['summary']['verified_signatures']=sum(r.get('signature',{}).get('status')=='verified' for r in completed)
        temporary=path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report,indent=2),encoding='utf-8')
        temporary.replace(path)
        lines=['# Evaluation report',f"Status: {report['status']}",f"Live model calls: {live}",
            'Offline minimization checks are not an outbound leak test or LLM accuracy measurement.',
            'Actual billing is unverified. Dollar columns are paid-list-price equivalents, not billed savings.',
            '','| Question | Arm | Correct | Input tokens observed | Output tokens observed | List-price equivalent USD | Canary occurrences |',
            '| --- | --- | --- | --- | --- | --- | --- |']
        for r in results:
            lines.append(f"| {r['id']} | {r['arm']} | {r.get('correct','unverified')} | {r.get('input_tokens','unavailable')} | {r.get('output_tokens','unavailable')} | {r.get('list_price_usd','unavailable')} | {r.get('canary_leaks','unverified')} |")
        lines.extend(['','```json',json.dumps(report['summary'],indent=2),'```'])
        (reportdir/'evaluation.md').write_text('\n'.join(lines),encoding='utf-8')
    for q in gold:
        chunks=sources[q['dataset']]
        # Offline checks exercise selection directly; live retrieval must be evaluated separately.
        selected_chunks=chunks
        if live:
            from .store import rows
            documents=rows('SELECT id FROM documents WHERE name=? AND status="ready"',(q['dataset'],))
            if not documents:
                report['status']='blocked: load and index demo documents before live retrieval evaluation'; save(); print(report['status']); return
            selected_chunks=retrieve(q['question'],[d['id'] for d in documents])
        plan=minimize(q['question'],selected_chunks)
        canaries=set(re.findall(r'CANARY_[A-Z0-9_]+','\n'.join(c['text'] for c in chunks)))
        report['offline_checks'].append({'id':q['id'],'unrelated_canaries_in_minimized_context':sum(c in plan['context'] for c in canaries),'consent_categories':plan['needed'],
            'full_tokens_estimate':estimate('\n'.join(c['text'] for c in chunks)),'minimized_tokens_estimate':estimate(plan['context'])})
        if not live: continue
        if not full: raise ValueError('Live baseline requires --synthetic-full-context')
        for arm in ('baseline','pipeline'):
            if any(r['id']==q['id'] and r['arm']==arm and r.get('status')=='completed' for r in results): continue
            if len(list((DATA/'audit').glob('*.json')))>=100:
                report['status']='attempt budget exhausted'; save(); print(json.dumps(report['summary'])); return
            try:
                request_start=time.monotonic()
                context='\n'.join(f'[S{i+1}] {c["text"]}' for i,c in enumerate(chunks)) if arm=='baseline' else plan['context']
                response=generate(q['question'] if arm=='baseline' else plan['question'],context,'privacy','evaluation-'+fingerprint[:10],feature='eval-'+arm,limit=1000000)
                answer=response['answer'] if arm=='baseline' else restore(response['answer'],plan['mapping'])
                usage=response['usage']; inp=usage.get('prompt_tokens',usage.get('promptTokenCount')); out=usage.get('completion_tokens',usage.get('candidatesTokenCount'))
                row={'id':q['id'],'arm':arm,'status':'completed','answer':answer,'correct':q['expected'].lower() in answer.lower(),
                    'sensitive_use_consent':'synthetic gold manifest authorization' if q['sensitive'] else 'not required',
                    'retrieval':'local Chroma and EmbeddingGemma 2' if arm=='pipeline' else 'full synthetic document',
                    'canary_leaks':sum(response['payload'].count(c) for c in canaries),'audit_id':response['audit_id'],
                    'prune_metadata':response['prune_metadata'],'signature':response['signature'],'usage':usage,
                    'input_tokens':inp,'output_tokens':out,'list_price_usd':(inp*.3+out*2.5)/1e6 if inp is not None and out is not None else None}
                results.append(row); save(); print(q['id'],arm,row['correct'],flush=True)
                time.sleep(max(0,15-(time.monotonic()-request_start)))
            except Exception as exc:
                results.append({'id':q['id'],'arm':arm,'status':'failed','error':str(exc)})
                report['status']='blocked: '+str(exc); save(); print(report['status']); return
    report['status']='completed' if live else 'offline only; cloud accuracy, outbound leak test, costs and signatures unverified'
    save(); print(json.dumps(report['summary'],indent=2))
