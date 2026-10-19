#!/usr/bin/env python3
"""Check review completeness and version binding, not scientific truth.
Gate keys: claims[{id,text,critical,status,evidence[{url,locator,family,accessed}],conditions,simplification}],
coverage[{surface,claim_ids,nonfactual_reason?}], issues[{id,status,resolution}],
reviews[{stage,reviewer,kind,independent,verdict,artifact_hashes}], checks{}, assets{relative_path:sha256}.
Review stage is script/final; kind is agent/human. Hashes bind each review to inspected assets.
"""
import argparse,hashlib,json,pathlib,sys

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def check(root,stage):
    g=json.loads((root/'science-gate.json').read_text());lesson=json.loads((root/'lesson.json').read_text());errors=[]
    def need(ok,msg):
        if not ok: errors.append(msg)
    content=json.loads((root/'science-claims.json').read_text());need(all(g.get(k)==content.get(k) for k in ['claims','coverage','issues']),'Claim ledger differs from reviewed science-claims.json');claims=g.get('claims',[]);by={c.get('id'):c for c in claims};need(len(by)==len(claims) and bool(claims),'Missing/duplicate claims')
    for c in claims:
        cid=c.get('id');need(c.get('status')=='verified',f'{cid}: unresolved claim')
        need(bool(c.get('text')),f'{cid}: missing statement')
        ev=c.get('evidence',[]);need(bool(ev),f'{cid}: no evidence')
        for e in ev:
            need(all(e.get(k) for k in ['url','locator','family','accessed']),f'{cid}: incomplete evidence location')
        if c.get('critical'):
            need(len({e.get('family') for e in ev})>=2 or (c.get('reason_type')=='unique_product_parameter' and c.get('claim_type')=='parameter' and bool(c.get('single_source_rationale'))),f'{cid}: core mechanism needs independent evidence')
        need('conditions' in c and 'simplification' in c,f'{cid}: missing boundaries')
    cov=g.get('coverage',[]);surfaces=[x.get('surface') for x in cov]
    need(len(surfaces)==len(set(surfaces)),'Duplicate coverage surface')
    for x in cov:
        ids=x.get('claim_ids',[]);need(bool(ids) or bool(x.get('nonfactual_reason')),f'{x.get("surface")}: uncovered')
        need(all(i in by for i in ids),f'{x.get("surface")}: unknown claim')
    shots=json.loads((root/'shots.json').read_text());required=['title','cover','visuals']+[f'shot:{s["id"]}' for s in shots]+[f'label:{v["id"]}' for v in g.get('visual_items',[])]+[f'lesson:{s["id"]}' for s in lesson['segments']]
    if (root/'description.txt').is_file(): required.append('description')
    for k in required: need(k in surfaces,f'Missing coverage {k}')
    for issue in g.get('issues',[]): need(issue.get('status')=='resolved' and bool(issue.get('resolution')),f'Open issue {issue.get("id")}')
    for st in (['script'] if stage=='script' else ['script','final']):
        reviews=[r for r in g.get('reviews',[]) if r.get('stage')==st and r.get('independent') and r.get('verdict')=='pass' and r.get('reviewer') and r.get('kind') in ['agent','human']]
        need(bool(reviews),f'No independent {st} review')
        for r in reviews:
            hs=r.get('artifact_hashes',{});need(bool(hs),f'{st}: missing reviewed version hashes');minimum=['lesson.json','sources.json','shots.json','science-claims.json'] if st=='script' else ['final.mp4','src/model.mjs','src/director.mjs','src/film.mjs','preview.html','assets/opening.png','assets/cover-3x4.png','build/timeline.json','build/captions.srt','build/narration.wav'];need(all(k in hs for k in minimum),f'{st}: incomplete reviewed assets')
            if (root/'description.txt').is_file(): need('description.txt' in hs,f'{st}: description not bound')
            for name,h in hs.items():
                f=(root/name).resolve();need(f.is_relative_to(root.resolve()) and f.is_file() and digest(f)==h,f'{st}: changed reviewed asset {name}')
    if stage=='final':
        for k in ['model','visual_science','audio_semantics','captions_match','cover_science']:
            need(g.get('checks',{}).get(k,{}).get('status')=='pass',f'Final check not passed: {k}')
        assets=g.get('assets',{});need(all(k in assets for k in ['final.mp4','lesson.json','sources.json','shots.json','science-claims.json','src/model.mjs','src/director.mjs','src/film.mjs','preview.html','assets/opening.png','assets/cover-3x4.png','build/timeline.json','build/captions.srt','build/narration.wav']),'Final assets incompletely locked')
        if (root/'description.txt').is_file(): need('description.txt' in assets,'Description not locked')
        for name,h in assets.items():
            f=(root/name).resolve();need(f.is_relative_to(root.resolve()) and f.is_file() and digest(f)==h,f'Changed/missing final asset {name}')
        need(g.get('status')=='pass','Final gate status not pass')
    return errors

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('project',type=pathlib.Path);a.add_argument('--stage',choices=['script','final'],default='final');n=a.parse_args()
    try: errors=check(n.project,n.stage)
    except (OSError,ValueError,KeyError,TypeError) as e: errors=[str(e)]
    print(json.dumps({'stage':n.stage,'passed':not errors,'errors':errors,'limitation':'Schema and asset binding only; does not verify scientific truth'},ensure_ascii=False,indent=2));return bool(errors)
if __name__=='__main__': sys.exit(main())
