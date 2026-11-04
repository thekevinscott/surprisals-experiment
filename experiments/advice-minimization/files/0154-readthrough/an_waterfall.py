import json,os,difflib
rows=[]
for i in range(38):
    d=f'{i}/advices'
    js=sorted(os.listdir(d),key=int)
    acc=js
    j=acc[-1]
    a=open(f'{d}/{j}/advice.txt').read()
    ps=[json.load(open(f'{i}/t_samples/{t}/tests.json'))['all_passed'] for t in range(5)]
    rows.append((i,len(js),j,a,sum(ps)))
    print(i,len(js),j,len(a),sum(ps),[json.load(open(f'{i}/t_samples/{t}/tests.json'))['passed'] for t in range(5)])
json.dump(rows,open('/tmp/claude/wf.json','w'))
