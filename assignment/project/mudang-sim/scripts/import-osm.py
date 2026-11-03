import xml.etree.ElementTree as E,json,math,pathlib,sys,datetime
r=E.parse(sys.argv[1]).getroot(); nodes={n.get('id'):{'x':float(n.get('lon')),'y':float(n.get('lat'))} for n in r.findall('node')}
def dist(a,b):
 x=math.radians(b['x']-a['x'])*math.cos(math.radians((a['y']+b['y'])/2)); y=math.radians(b['y']-a['y']); return 6371000*math.hypot(x,y)
edges=[]; features=[]
for w in r.findall('way'):
 t={x.get('k'):x.get('v') for x in w.findall('tag')}; ids=[n.get('ref') for n in w.findall('nd')]; coords=[[nodes[i]['x'],nodes[i]['y']] for i in ids]
 if t.get('building') and ids[0]==ids[-1]: features.append({'type':'Feature','properties':{'name':t.get('name','')},'geometry':{'type':'Polygon','coordinates':[coords]}})
 if t.get('highway') not in ['service','residential','unclassified','tertiary','secondary','primary','living_street'] or t.get('access') in ['no','private'] or t.get('motor_vehicle')=='no': continue
 for a,b in zip(ids,ids[1:]):
  if a==b: continue
  m=dist(nodes[a],nodes[b]); e={'from':a,'to':b,'meters':m,'osmWay':w.get('id')}
  if t.get('oneway')!='-1': edges.append(e)
  if t.get('oneway') not in ['yes','1','true'] and t.get('junction')!='roundabout': edges.append({**e,'from':b,'to':a})
used={e[k] for e in edges for k in ['from','to']}; nodes={i:nodes[i] for i in used}
stops={k:min(nodes,key=lambda i:dist(nodes[i],p)) for k,p in {'S0':{'x':127.127079,'y':37.451099},'S1':{'x':127.133831,'y':37.455271}}.items()}
out=pathlib.Path(__file__).resolve().parents[1] / 'src'; data={'source':'https://www.openstreetmap.org/api/0.6/map?bbox=127.126,37.449,127.136,37.456','license':'ODbL-1.0, © OpenStreetMap contributors','retrieved':datetime.date.today().isoformat(),'nodes':nodes,'edges':edges,'stopNodes':stops}
(out/'campus-roads.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n'); (out/'campus-buildings.json').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(len(nodes),len(edges),stops,{k:nodes[v] for k,v in stops.items()})
