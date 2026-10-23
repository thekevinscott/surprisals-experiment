import json,re,sys,os
R=sys.argv[1]; A=R+'/attempts'
J=lambda p:json.load(open(p))
atts=sorted(int(x) for x in os.listdir(A))
best=None;tw=0;prev=None;first=None;rows=[]
for a in atts:
    d=f'{A}/{a}'
    cands=[J(f'{d}/advices/{c}/metadata.json') for c in sorted(os.listdir(d+'/advices'),key=int)]
    acc=[c for c in cands if not c['rejected']]
    ln=acc[-1]['measurement'] if acc else None
    ts=[]
    for k in sorted(os.listdir(d+'/t_samples'),key=int):
        p=f'{d}/t_samples/{k}/tests.json'
        if os.path.exists(p):
            t=J(p);ts.append((t['passed'],t['total'],t['all_passed']))
    ap=len(ts)==5 and all(x[2] for x in ts)
    if ap and (best is None or ln<best):
        best=ln;tw=0
        if first is None:first=(a,ln)
    else: tw+=1 if (first is not None or True) else 0
    fb=open(d+'/feedback.txt').read()
    m=re.search(r'Turns without improvement: (\d+) of (\d+)',fb)
    b=re.search(r'Shortest successful advice so far: (\d+)',fb)
    fbtw=int(m.group(1)) if m else None; thr=m.group(2) if m else None
    fbb=int(b.group(1)) if b else None
    rows.append((a,ln,len(cands),len(cands)-len(acc),sum(x[2] for x in ts),len(ts),'/'.join(f'{x[0]}/{x[1]}' if not x[2] else 'P' for x in ts),ap,best,tw,fbtw,fbb,None if prev is None or ln is None else ln-prev,None if best is None or ln is None else ln-best))
    if ln is not None:prev=ln
print('att|chars|cand|rej|kpass|per-sample|allpass|best|tw|fb_tw|fb_best|dprev|dbest')
for r in rows:
    print(f'{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}/{r[5]}|{r[6]}|{int(r[7])}|{r[8]}|{r[9]}|{r[10]}|{r[11]}|{r[12]}|{r[13]}')
print('thr',thr,'first',first,'best',best,'n',len(rows))
print('mismatch tw',[r[0] for r in rows if r[9]!=r[10]],'best',[r[0] for r in rows if r[8]!=r[11]])
