import ast, json, re, time, statistics
from pathlib import Path
root=Path(__file__).parent
tree=ast.parse((root/'app.py').read_text(encoding='utf-8'))
nodes=[n for n in tree.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['KNOWLEDGE','QUIZ'] for t in n.targets)) or (isinstance(n,ast.FunctionDef) and n.name in ['tokenize','retrieve','format_answer'])]
env={'re':re}
exec(compile(ast.Module(body=nodes,type_ignores=[]),'app.py','exec'),env)
direct=[('Explain Round Robin scheduling','OS-01'),('What is FCFS scheduling','OS-02'),('Explain shortest job first','OS-03'),('Explain priority scheduling','OS-04'),('What is paging','OS-05'),('What is segmentation','OS-06'),('Explain virtual memory','OS-07'),('Explain page replacement','OS-08'),('Explain process states','OS-10'),('Explain context switching','OS-12'),('Explain deadlock conditions','OS-14'),('Explain file allocation methods','OS-18')]
paraphrase=[('How does each task get a fixed slice of CPU time','OS-01'),('Why do short tasks wait behind a long task in arrival order','OS-02'),('Which policy runs the smallest CPU burst next','OS-03'),('How can aging prevent starvation','OS-04'),('How are fixed size logical blocks mapped to physical blocks','OS-05'),('How are code data and stack divided into variable sized units','OS-06'),('Why can a program use more memory than physical RAM','OS-07'),('Which page should be removed when no free frame remains','OS-08'),('What happens when an executing task waits for input output','OS-10'),('Why must CPU registers be saved before another task runs','OS-12'),('Why can tasks wait forever for resources held by each other','OS-14'),('Compare storing disk blocks consecutively with using pointers','OS-18')]
unsupported=['What is the capital of France','How do I bake bread','What is the weather today','Explain photosynthesis','Who won the football match','How do I create a spreadsheet']
results=[]
for group,cases in [('Direct',direct),('Paraphrase',paraphrase),('Unsupported',[(q,None) for q in unsupported])]:
 for q,expected in cases:
  docs=env['retrieve'](q); accepted=bool(docs and docs[0]['score']>=.35)
  results.append({'group':group,'question':q,'expected':expected,'top':docs[0]['id'] if docs else None,'score':docs[0]['score'] if docs else 0,'accepted':accepted,'correct': accepted and docs[0]['id']==expected if expected else not accepted,'hit3':bool(expected and any(d['id']==expected for d in docs))})
lat=[]
for _ in range(10):
 for q,_ in direct: env['retrieve'](q)
for _ in range(100):
 for q,_ in direct:
  start=time.perf_counter(); env['retrieve'](q); lat.append((time.perf_counter()-start)*1000)
out={'results':results,'latency_n':len(lat),'median_ms':statistics.median(lat),'p95_ms':sorted(lat)[int(.95*len(lat))-1]}
qa=root/'.report_qa';qa.mkdir(exist_ok=True)
(qa/'evaluation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for group in ['Direct','Paraphrase','Unsupported']:
 rows=[r for r in results if r['group']==group];print(group, sum(r['correct'] for r in rows),'/',len(rows),'hit3',sum(r['hit3'] for r in rows))
print('latency',out['median_ms'],out['p95_ms'])
print(json.dumps([r for r in results if not r['correct']],indent=2))
