"use strict";
const DATA=JSON.parse(document.getElementById('demand-data').textContent);
const $=id=>document.getElementById(id);
const fmt=(n,d=0)=>n.toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
const BLUE='#426aaa',GREEN='#087f73';
function random(seed){let state=seed>>>0;return()=>{state=(state+0x6D2B79F5)>>>0;let t=Math.imul(state^state>>>15,1|state);t^=t+Math.imul(t^t>>>7,61|t);return((t^t>>>14)>>>0)/4294967296;};}
function poisson(mu,rng){let count=0;while(mu>0){const part=Math.min(mu,20),limit=Math.exp(-part);let product=1,k=0;do{k++;product*=rng();}while(product>limit);count+=k-1;mu-=part;}return count;}
function weights(){const raw=DATA.odHourly.slice(18,24),sum=raw.reduce((a,b)=>a+b,0);return raw.map(x=>x/sum);}
function counts(n,p,rng){const out=Array(p.length).fill(0);for(let j=0;j<n;j++){const u=rng();let c=0;for(let i=0;i<p.length;i++){c+=p[i];if(u<c||i===p.length-1){out[i]++;break;}}}return out;}
function timeExperiment(n,seed){return{uniform:counts(n,Array(6).fill(1/6),random(seed)),od:counts(n,weights(),random(seed))};}
function countExperiment(n,seed){const rng=random(seed);return{fixed:Array(500).fill(n),poisson:Array.from({length:500},()=>poisson(n,rng))};}
function summary(a){const mean=a.reduce((x,y)=>x+y,0)/a.length;return{mean,sd:Math.sqrt(a.reduce((s,v)=>s+(v-mean)**2,0)/(a.length-1)),min:Math.min(...a),max:Math.max(...a)};}
const ROWS=[{id:'A',time:'18:02',od:'주거지 → 역'},{id:'B',time:'18:10',od:'역 → 주거지'},{id:'C',time:'18:35',od:'상가 → 주거지'},{id:'D',time:'19:05',od:'주거지 → 상가'}];
function resample(seed){const rng=random(seed);return Array.from({length:4},()=>({...ROWS[Math.floor(rng()*4)]}));}
// 화면을 이동해도 같은 저녁을 유지하도록 시각과 O-D 생성 난수열을 분리합니다.
const OD_POOLS=DATA.odPairs.map(pairs=>{
 let total=0;
 const cumulative=pairs.map(pair=>total+=pair[2]);
 return {pairs,cumulative,total};
});
function chooseOD(hour,rng){
 const pool=OD_POOLS[hour],u=rng(),target=u*pool.total;
 let lo=0,hi=pool.pairs.length-1;
 while(lo<hi){const mid=(lo+hi)>>>1;if(target<pool.cumulative[mid])hi=mid;else lo=mid+1;}
 const [origin,destination,weight]=pool.pairs[lo];
 return {origin,destination,probability:weight/pool.total,u,
  lower:(lo?pool.cumulative[lo-1]:0)/pool.total,upper:pool.cumulative[lo]/pool.total};
}
function processExperiment(expected,seed){
 const rng=random(seed),odRng=random((seed^0x9e3779b9)>>>0),rows=[];
 const hours=weights().map((p,h)=>{
  const mu=expected*p,n=poisson(mu,rng);
  for(let i=0;i<n;i++)rows.push({hour:h,time:1080+h*60+rng()*60});
  return {p,mu,rate:mu/60,n};
 });
 rows.sort((a,b)=>a.time-b.time);
 rows.forEach((row,i)=>Object.assign(row,{id:i+1,gap:i?row.time-rows[i-1].time:null},chooseOD(row.hour,odRng)));
 return {hours,rows};
}
function clockTime(minute){
 const sec=Math.floor(minute*60+1e-7);
 return [Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(x=>String(x).padStart(2,'0')).join(':');
}
let processState=null;
function renderProcess(){
 const n=+$('process-n').value,seed=+$('process-seed').value;
 if(!$('process-form').checkValidity()||!Number.isInteger(n)||n<0||n>5000||!Number.isInteger(seed)||seed<0||seed>4294967295){
  $('process-error').textContent='기대 건수와 시드를 허용 범위의 정수로 입력합니다. 마지막 유효 결과를 유지합니다.';return;
 }
 $('process-error').textContent='';
 processState=processExperiment(n,seed);
 $('process-rates').querySelector('tbody').innerHTML=processState.hours.map((h,i)=>`<tr><td>${18+i}시대</td><td>${fmt(h.p*100,2)}%</td><td>${fmt(h.mu,2)}</td><td>${fmt(h.rate,3)}</td><td>${h.n}</td></tr>`).join('');
 $('process-all').querySelector('tbody').innerHTML=processState.rows.map(r=>`<tr><td>${r.id}</td><td>${clockTime(r.time)}</td><td>${r.origin}</td><td>${r.destination}</td></tr>`).join('')||'<tr><td colspan="4">이번 저녁에는 요청이 없습니다.</td></tr>';
 $('process-clock').value=processState.rows[0]?.time??1080;
 renderProcessCursor();
}
function renderProcessCursor(){
 if(!processState)return;
 const now=+$('process-clock').value,all=processState.rows,visible=all.filter(r=>r.time<=now+1e-8),last=visible[visible.length-1];
 $('process-next').disabled=visible.length===all.length;
 $('process-status').textContent=`관찰 시각 ${clockTime(now)} · 누적 ${visible.length}건 / 이번 저녁 전체 ${all.length}건. ${last?`최근 요청 #${last.id}: ${last.origin} → ${last.destination}`:'아직 발생한 요청이 없습니다.'}`;
 const x=t=>58+(t-1080)/360*820, y=n=>238-n/Math.max(1,all.length)*104;
 let svg=text(58,18,'개별 호출 시각 · 선 하나 = 요청 한 건');
 for(let h=0;h<=6;h++){
  const xx=x(1080+h*60);
  svg+=`<line x1="${xx}" y1="30" x2="${xx}" y2="238" stroke="#e1e8e5"/>`;
  svg+=text(xx,263,`${18+h}:00`,h===0?'text-anchor="start"':h===6?'text-anchor="end"':'text-anchor="middle"');
 }
 for(const r of all){svg+=`<line x1="${x(r.time)}" x2="${x(r.time)}" y1="38" y2="68" stroke="${r.time<=now+1e-8?GREEN:'#c9d2d0'}" stroke-width="${r===last?3:1.5}"/>`;}
 svg+=text(58,105,'누적 요청 수 (건)');
 for(const n of [...new Set([0,Math.round(all.length/2),all.length])])svg+=text(48,y(n)+4,n,'text-anchor="end"');
 function path(rows,end){let d=`M58,${y(0)}`;rows.forEach((r,i)=>d+=`H${x(r.time)}V${y(i+1)}`);return d+`H${x(end)}`;}
 svg+=`<path d="${path(all,1440)}" fill="none" stroke="#c9d2d0" stroke-width="2"/><path d="${path(visible,now)}" fill="none" stroke="${GREEN}" stroke-width="2.5"/>`;
 svg+=`<line x1="${x(now)}" x2="${x(now)}" y1="28" y2="240" stroke="#985b19" stroke-dasharray="4 3"/>`;
 if(last)svg+=`<circle cx="${x(last.time)}" cy="${y(visible.length)}" r="4" fill="${GREEN}"/>`;
 $('process-timeline').innerHTML=svg;
 $('process-od').innerHTML=last?`<div>호출 #${last.id}<strong>${clockTime(last.time)}</strong></div><div>출발 행정동 O<strong>${last.origin}</strong></div><span class="od-arrow" aria-hidden="true">→</span><div>도착 행정동 D<strong>${last.destination}</strong></div>`:'다음 요청으로 이동하면 그 요청의 시각과 O-D 쌍이 나타납니다.';
 $('process-choice').textContent=last?`${18+last.hour}시대 집계표에서 이 O-D 쌍을 뽑을 확률은 ${fmt(last.probability*100,4)}%입니다. O-D 쌍을 코드순으로 놓고 통행 비중을 누적하면, 난수 u = ${fmt(last.u,6)}가 이 쌍의 구간 [${fmt(last.lower,6)}, ${fmt(last.upper,6)})에 들어갑니다.`:'O-D 선택은 호출 발생 시각을 정한 다음 수행합니다.';
 $('process-requests').querySelector('tbody').innerHTML=visible.slice(-8).map(r=>`<tr${r===last?' class="current-request"':''}><td>${r.id}</td><td>${clockTime(r.time)}</td><td>${r.gap===null?'첫 요청':fmt(r.gap,3)}</td><td>${r.origin}</td><td>${r.destination}</td></tr>`).join('')||'<tr><td colspan="5">관찰 시각까지 요청이 없습니다.</td></tr>';
}
const text=(x,y,t,extra='')=>`<text x="${x}" y="${y}" ${extra}>${t}</text>`;
function axes(max,label){let s=text(58,18,label);for(let i=0;i<=4;i++){const y=278-i*60;s+=`<line x1="58" y1="${y}" x2="878" y2="${y}" stroke="#dce5e2"/>`+text(48,y+5,fmt(max*i/4),'text-anchor="end"');}return s;}
function timeChart(a){const max=Math.ceil(Math.max(...a.uniform,...a.od)/50)*50||1;let s=axes(max,'호출 수 (건)');for(let i=0;i<6;i++){const x=58+i*820/6;[a.uniform[i],a.od[i]].forEach((v,j)=>{const h=v/max*240;s+=`<rect x="${x+20+j*48}" y="${278-h}" width="40" height="${h}" fill="${j?GREEN:BLUE}"><title>${18+i}시 ${j?'O-D':'균등'}: ${v}건</title></rect>`+text(x+40+j*48,270-h,v,'text-anchor="middle"');});s+=text(x+68,306,`${18+i}시대`,'text-anchor="middle"');}$('time-chart').innerHTML=s;}
function countChart(a,n){const low=Math.min(n,...a),high=Math.max(n,...a);const bw=Math.max(1,Math.ceil((high-low+1)/24));const bins=Array(Math.floor((high-low)/bw)+1).fill(0);a.forEach(v=>bins[Math.floor((v-low)/bw)]++);const max=Math.max(...bins);let s=axes(max,'포아송 빈도 (회)');const domain=bins.length*bw;bins.forEach((v,i)=>{const h=v/max*240;s+=`<rect x="${58+i*820/bins.length+1}" y="${278-h}" width="${Math.max(1,820/bins.length-2)}" height="${h}" fill="${GREEN}"><title>${low+i*bw}~${low+(i+1)*bw-1}건: ${v}회</title></rect>`;});const x=58+(n-low+.5)/domain*820;s+=`<line x1="${x}" y1="30" x2="${x}" y2="278" stroke="${BLUE}" stroke-width="3" stroke-dasharray="7 4"/>`;s+=text(x>620?x-8:x+8,32,`고정: ${fmt(n)}건에 500회`,x>620?'text-anchor="end"':'');const ticks=[...new Set(Array.from({length:5},(_,i)=>Math.round(low+(high-low)*i/4)))];for(const v of ticks){s+=text(58+(v-low+.5)/domain*820,301,fmt(v),'text-anchor="middle"');}s+=text(468,325,'18~24시 총 호출 건수 (건)','text-anchor="middle"');$('count-chart').innerHTML=s;}
function read(prefix,min){const form=$(prefix+'-form'),input=$(prefix==='time'?'time-count':'count-n'),seed=$(prefix+'-seed');if(!form.checkValidity()||!Number.isInteger(+input.value)||!Number.isInteger(+seed.value)||+input.value<min){$(prefix+'-error').textContent='건수와 시드를 허용 범위의 정수로 입력합니다. 그래프는 마지막 유효 설정의 결과입니다.';return null;}$(prefix+'-error').textContent='';return{n:+input.value,seed:+seed.value};}
function renderTime(){const c=read('time',1);if(!c)return;const a=timeExperiment(c.n,c.seed),p=weights();timeChart(a);$('time-answer').textContent=`두 조건 모두 합계는 ${fmt(c.n)}건입니다. 이번 O-D 조건에서는 ${18+a.od.indexOf(Math.max(...a.od))}시대가 ${fmt(Math.max(...a.od))}건으로 가장 많습니다. 두 색의 막대 차이가 큰 시간대를 찾아봅시다.`;$('time-table').querySelector('tbody').innerHTML=p.map((v,i)=>`<tr><td>${18+i}시대</td><td>${fmt(100/6,2)}%</td><td>${fmt(v*100,2)}%</td><td>${a.uniform[i]}</td><td>${a.od[i]}</td></tr>`).join('');}
function renderCount(){const c=read('count',0);if(!c)return;const a=countExperiment(c.n,c.seed);countChart(a.poisson,c.n);$('count-table').querySelector('tbody').innerHTML=Object.entries(a).map(([k,v])=>{const s=summary(v);return`<tr><td>${k==='fixed'?'총건수 고정':'포아송'}</td><td>${fmt(s.mean,1)}</td><td>${fmt(s.sd,1)}</td><td>${s.min}~${s.max}</td></tr>`;}).join('');$('count-answer').textContent=`파란 점선은 고정 방식의 500회가 모두 ${fmt(c.n)}건에 겹치는 위치입니다. 초록 막대는 포아송 총건수의 빈도입니다. 포아송 표준편차의 이론값은 √${fmt(c.n)} = ${fmt(Math.sqrt(c.n),1)}건입니다.`;}
function renderBoot(rows){const frequency=Object.fromEntries(ROWS.map(r=>[r.id,rows.filter(x=>x.id===r.id).length]));const cls=id=>frequency[id]>1?'duplicate':frequency[id]===0?'omitted':'';$('source-table').querySelector('tbody').innerHTML=ROWS.map(r=>`<tr class="${cls(r.id)}"><td>${r.id}${frequency[r.id]===0?' · 누락':frequency[r.id]>1?` · ${frequency[r.id]}회`:''}</td><td>${r.time}</td><td>${r.od}</td></tr>`).join('');$('draws').innerHTML=rows.map(r=>`<span class="chip ${cls(r.id)}">${r.id}</span>`).join('');$('boot-table').querySelector('tbody').innerHTML=rows.map((r,i)=>`<tr class="${cls(r.id)}"><td>${i+1}</td><td>${r.id}</td><td>${r.time}</td><td>${r.od}</td></tr>`).join('');const duplicates=ROWS.filter(r=>frequency[r.id]>1).map(r=>`${r.id} ${frequency[r.id]}회`).join(', '),missing=ROWS.filter(r=>!frequency[r.id]).map(r=>r.id).join(', ');$('boot-answer').textContent=`총 네 건입니다. ${duplicates?'중복: '+duplicates:'중복 없음'}. ${missing?'누락: '+missing:'누락 없음'}. 같은 행을 뽑을 때마다 시각과 O-D도 그대로 복사됩니다.`;}
for(const prefix of ['time','count']){const render=prefix==='time'?renderTime:renderCount;$(prefix+'-form').addEventListener('submit',e=>{e.preventDefault();render();});$(prefix+'-form').addEventListener('input',render);$(prefix+'-next').addEventListener('click',()=>{const c=read(prefix,prefix==='time'?1:0);if(c){$(prefix+'-seed').value=(c.seed+1)>>>0;render();}});}
document.querySelectorAll('[data-step]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-step]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('.step').forEach(s=>s.hidden=s.id!=='step'+button.dataset.step);}));
let bootSeed=42;$('boot-next').addEventListener('click',()=>{renderBoot(resample(bootSeed));$('boot-seed').textContent=`난수 시드 ${bootSeed}`;bootSeed=(bootSeed+1)>>>0;});$('boot-example').addEventListener('click',()=>{renderBoot([ROWS[1],ROWS[1],ROWS[3],ROWS[0]]);$('boot-seed').textContent='설명용 예제';});
$('sources').textContent=`od_2024.parquet · SHA-256 ${DATA.sources['od_2024.parquet']}`;
$('process-form').addEventListener('submit',e=>{e.preventDefault();renderProcess();});
$('process-new').addEventListener('click',()=>{
 if(!$('process-form').checkValidity()){renderProcess();return;}
 $('process-seed').value=(+$('process-seed').value+1)>>>0;renderProcess();
});
$('process-clock').addEventListener('input',renderProcessCursor);
$('process-start').addEventListener('click',()=>{$('process-clock').value=1080;renderProcessCursor();});
$('process-end').addEventListener('click',()=>{$('process-clock').value=1440;renderProcessCursor();});
$('process-next').addEventListener('click',()=>{
 const next=processState.rows.find(r=>r.time>+$('process-clock').value+1e-8);
 if(next){$('process-clock').value=next.time;renderProcessCursor();}
});
window.DemandLab={random,poisson,weights,timeExperiment,countExperiment,resample,summary,processExperiment,clockTime};
renderProcess();renderTime();renderCount();renderBoot([ROWS[1],ROWS[1],ROWS[3],ROWS[0]]);
