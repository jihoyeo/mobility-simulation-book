import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const html=fs.readFileSync(path.join(root,'_static/ch08_demand.html'),'utf8');
const script=fs.readFileSync(path.join(root,'tools/templates/ch08_demand.js'),'utf8').replace(/^\uFEFF/,'');
const template=fs.readFileSync(path.join(root,'tools/templates/ch08_demand.html'),'utf8').replace(/^\uFEFF/,'');
const dataText=html.match(/<script id="demand-data" type="application\/json">(.*?)<\/script>/s)[1];
assert.equal(html.replace(/\r\n/g,'\n'),template.replace('__DEMAND_DATA__',dataText).replace('__DEMAND_SCRIPT__',script).replace(/\r\n/g,'\n'));
// 브라우저 없이 계산과 이벤트 연결을 검사합니다. 화면 배치 검사를 대신하지 않습니다.
const elements=new Map();
for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)){
 const tag=match[0],id=match[1];
 elements.set(id,{id,value:tag.match(/value="([^"]+)"/)?.[1]??'',hidden:/\shidden/.test(tag),textContent:'',innerHTML:'',handlers:{},
  addEventListener(event,fn){this.handlers[event]=fn;},
  querySelector(){return this.body??={innerHTML:''};},checkValidity(){return this.valid!==false;}});
}
elements.get('demand-data').textContent=dataText;
const buttons=[1,2,3].map(n=>({dataset:{step:String(n)},handlers:{},addEventListener(e,f){this.handlers[e]=f;},setAttribute(k,v){this[k]=v;}}));
const sandbox={window:{},document:{getElementById:id=>{assert(elements.has(id),`Missing element ${id}`);return elements.get(id);},querySelectorAll:q=>q==='[data-step]'?buttons:[1,2,3].map(n=>elements.get('step'+n))}};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
const lab=sandbox.window.DemandLab;
for(const n of [1,1000,2000,5000]){
 const a=lab.timeExperiment(n,42);
 for(const values of [a.uniform,a.od])assert.equal(values.reduce((a,b)=>a+b,0),n);
 assert.equal(JSON.stringify(a),JSON.stringify(lab.timeExperiment(n,42)));
 const r=lab.countExperiment(n,42);
 assert.equal(r.poisson.length,500);assert(r.fixed.every(v=>v===n));
 assert(r.poisson.every(Number.isInteger));assert(r.poisson.every(v=>v>=0));
}
assert(lab.countExperiment(0,42).poisson.every(v=>v===0));
const r=lab.countExperiment(1000,42),s=lab.summary(r.poisson);
assert(Math.abs(s.mean-1000)<6);assert(Math.abs(s.sd-Math.sqrt(1000))<5);
assert.notEqual(JSON.stringify(r.poisson),JSON.stringify(lab.countExperiment(1000,43).poisson));
for(let seed=0;seed<30;seed++){
 const rows=lab.resample(seed);assert.equal(rows.length,4);
 const source={A:['18:02','주거지 → 역'],B:['18:10','역 → 주거지'],C:['18:35','상가 → 주거지'],D:['19:05','주거지 → 상가']};
 for(const row of rows)assert.deepEqual([row.time,row.od],source[row.id]);
}
assert.match(elements.get('boot-answer').textContent,/B 2회/);assert.match(elements.get('boot-answer').textContent,/누락: C/);
buttons[1].handlers.click();assert(elements.get('step1').hidden);assert(!elements.get('step2').hidden);assert(elements.get('step3').hidden);
elements.get('time-count').value='2000';elements.get('time-form').handlers.input();assert.match(elements.get('time-answer').textContent,/2,000/);assert.match(elements.get('count-answer').textContent,/1,000/);
const saved=elements.get('time-chart').innerHTML;
elements.get('time-form').valid=false;elements.get('time-form').handlers.input();assert.equal(elements.get('time-chart').innerHTML,saved);assert(elements.get('time-error').textContent);
elements.get('boot-next').handlers.click();elements.get('boot-example').handlers.click();assert.match(elements.get('boot-answer').textContent,/B 2회/);
for(const id of ['time-chart','count-chart'])assert(!/NaN|Infinity/.test(elements.get(id).innerHTML));
console.log(`PASS: template sync, totals, seeds, Poisson moments (${s.mean.toFixed(1)}, ${s.sd.toFixed(1)}), zero demand, row preservation, step switching, independent controls, invalid input, example reset.`);
