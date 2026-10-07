"use strict";
const DATA = JSON.parse(document.getElementById("demand-data").textContent);
const $ = id => document.getElementById(id);
const fmt = (x, digits=0) => x.toLocaleString("ko-KR", {maximumFractionDigits:digits, minimumFractionDigits:digits});
const NAMES = {fixed:"총건수 고정", bootstrap:"행 재표집", poisson:"포아송 발생"};
const COLORS = {fixed:"#426aaa", bootstrap:"#aa6728", poisson:"#117e75"};
const REFERENCE = DATA.requests;
const POOLS = Array.from({length:6}, (_, i) => REFERENCE.filter(r => Math.floor(r[1]/60) === 18+i));
let current = null;

function random(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6D2B79F5) >>> 0;
    let t = Math.imul(state ^ state >>> 15, 1 | state);
    t ^= t + Math.imul(t ^ t >>> 7, 61 | t);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function weights(source) {
  const raw = source === "uniform" ? Array(6).fill(1)
    : (source === "od" ? DATA.odHourly : DATA.referenceHourly).slice(18);
  const total = raw.reduce((a,b) => a+b,0);
  return raw.map(x => x/total);
}
function category(p, rng) {
  const u = rng(); let cumulative = 0;
  for (let i=0;i<p.length;i++) {cumulative += p[i]; if (u<cumulative) return i;}
  return p.length-1;
}
function poisson(mu, rng) {
  // 작은 평균으로 나누어 곱셈이 0으로 내려가는 것을 피합니다.
  let count = 0;
  while (mu>0) {
    const part = Math.min(mu,20), limit = Math.exp(-part);
    let product=1, k=0;
    do {k++; product *= rng();} while (product>limit);
    count += k-1; mu -= part;
  }
  return count;
}
function countsFor(method,n,p,rng) {
  if (method === "poisson") return p.map(w => poisson(n*w,rng));
  const counts=Array(6).fill(0);
  for (let i=0;i<n;i++) counts[category(p,rng)]++;
  return counts;
}
function generate(config) {
  const {method,seed}=config, rng=random(seed);
  const n=method === "bootstrap" ? REFERENCE.length : config.n;
  const p=weights(method === "bootstrap" ? "reference" : config.profile);
  const rows=[];
  const make = (source,time) => ({time,olat:source[2],olon:source[3],dlat:source[4],dlon:source[5],source:source[0]});
  if (method === "bootstrap") {
    for (let i=0;i<n;i++) {const row=REFERENCE[Math.floor(rng()*REFERENCE.length)];rows.push(make(row,row[1]));}
  } else {
    const counts=countsFor(method,n,p,rng);
    for (let h=0;h<6;h++) for (let i=0;i<counts[h];i++) {
      const pool=POOLS[h], source=pool[Math.floor(rng()*pool.length)];
      rows.push(make(source,(18+h)*60+Math.floor(rng()*60)));
    }
  }
  rows.sort((a,b)=>a.time-b.time);
  rows.forEach((r,i)=>r.id=i);
  return {rows,p,n,config};
}
function summary(values) {
  const mean=values.reduce((a,b)=>a+b,0)/values.length;
  return {mean,sd:Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/(values.length-1))};
}
function repetitions(config) {
  const out={};
  Object.keys(NAMES).forEach((method,index)=>{
    const n=method === "bootstrap" ? REFERENCE.length : config.n;
    const p=weights(method === "bootstrap" ? "reference" : config.profile);
    const rng=random((config.seed ^ (0x9e3779b9+index)) >>> 0), totals=[], peaks=[];
    for (let b=0;b<500;b++) {
      const counts=countsFor(method,n,p,rng);
      totals.push(counts.reduce((a,x)=>a+x,0));peaks.push(counts[0]);
    }
    out[method]={totals,total:summary(totals),peak:summary(peaks),n};
  });
  return out;
}
const textSvg = (x,y,text,extra="") => `<text x="${x}" y="${y}" ${extra}>${text}</text>`;
function bars(id,values,expected,labels,{width=540,height=270,percent=false,colors=null}={}) {
  const left=48,right=15,top=22,bottom=34,w=width-left-right,h=height-top-bottom;
  const max=Math.max(1,...values,...(expected||[]))*1.12;
  let s="";
  for(let i=0;i<=4;i++) {
    const y=top+h-h*i/4;
    s+=`<line x1="${left}" y1="${y}" x2="${width-right}" y2="${y}" stroke="#e0e8e4"/>`;
    s+=textSvg(left-7,y+4,fmt(max*i/4,percent?1:0),'text-anchor="end"');
  }
  s+=textSvg(left,13,percent?"비중 (%)":"호출 수 (건)");
  values.forEach((v,i)=>{
    const step=w/values.length,x=left+i*step,bw=step*(expected ? .55 : .7);
    if(expected) s+=`<rect x="${x+step*.1}" y="${top+h-h*expected[i]/max}" width="${step*.8}" height="${h*expected[i]/max}" fill="#dbe5df"><title>기댓값 ${fmt(expected[i],1)}건</title></rect>`;
    s+=`<rect x="${x+(step-bw)/2}" y="${top+h-h*v/max}" width="${bw}" height="${h*v/max}" fill="${colors?colors[i]:"#117e75"}"><title>${labels[i]}: ${fmt(v,percent?2:0)}${percent?"%":"건"}</title></rect>`;
    if(labels[i]) s+=textSvg(x+step/2,height-11,labels[i],'text-anchor="middle"');
  });
  $(id).innerHTML=s;
}
function histogram(id,values,color,domainValues=values) {
  const W=540,H=230,left=48,top=24,h=162,w=477;
  const vmin=Math.min(...domainValues),vmax=Math.max(...domainValues);
  const binWidth=Math.max(1,Math.ceil((vmax-vmin+1)/20));
  const min=vmin-.5,bins=Array(Math.floor((vmax-vmin)/binWidth)+1).fill(0);
  values.forEach(v=>bins[Math.floor((v-vmin)/binWidth)]++);
  const max=Math.max(...bins),domain=bins.length*binWidth;
  let s=textSvg(left,14,"반복 횟수");
  for(let i=0;i<=4;i++) {
    const y=top+h-h*i/4;
    s+=`<line x1="${left}" y1="${y}" x2="525" y2="${y}" stroke="#e0e8e4"/>`+textSvg(left-8,y+4,fmt(max*i/4),'text-anchor="end"');
  }
  bins.forEach((v,i)=>{
    s+=`<rect x="${left+w*i/bins.length+1}" y="${top+h-h*v/max}" width="${Math.max(1,w/bins.length-2)}" height="${h*v/max}" fill="${color}"><title>${vmin+i*binWidth}~${vmin+(i+1)*binWidth-1}건: ${v}회</title></rect>`;
  });
  const labels=bins.length===1?[{x:left+w/2,t:fmt(vmin)}]:[0,.25,.5,.75,1].map(t=>({x:left+w*t,t:fmt(min+domain*t)}));
  labels.forEach(a=>s+=textSvg(a.x,207,a.t,'text-anchor="middle"'));
  s+=textSvg(left+w/2,226,"18~24시 총 호출 건수",'text-anchor="middle"');
  $(id).innerHTML=s;
}
function map() {
  if(!current)return;
  const canvas=$("map"), ratio=window.devicePixelRatio||1, W=canvas.clientWidth,H=canvas.clientHeight;
  canvas.width=W*ratio;canvas.height=H*ratio;
  const ctx=canvas.getContext("2d");ctx.scale(ratio,ratio);
  const points=DATA.boundary.concat(REFERENCE.flatMap(r=>[[r[3],r[2]],[r[5],r[4]]]));
  const xs=points.map(p=>p[0]*Math.cos(37.54*Math.PI/180)),ys=points.map(p=>p[1]);
  const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const scale=Math.min((W-36)/(xmax-xmin),(H-40)/(ymax-ymin));
  const project=(lon,lat)=>[W/2+(lon*Math.cos(37.54*Math.PI/180)-(xmin+xmax)/2)*scale,H/2-(lat-(ymin+ymax)/2)*scale];
  ctx.beginPath();DATA.boundary.forEach((p,i)=>{const q=project(...p);i?ctx.lineTo(...q):ctx.moveTo(...q);});
  ctx.closePath();ctx.fillStyle="#edf3ef";ctx.fill();ctx.strokeStyle="#8ca99b";ctx.lineWidth=1;ctx.stroke();
  ctx.beginPath();DATA.edges.forEach(([a,b])=>{ctx.moveTo(...project(...DATA.nodes[a]));ctx.lineTo(...project(...DATA.nodes[b]));});
  ctx.strokeStyle="#c7d3cc";ctx.lineWidth=.55;ctx.stroke();
  const hour=$("hour").value,filtered=current.rows.filter(r=>hour==="all"||Math.floor(r.time/60)===Number(hour));
  const shown=filtered.length<=400?filtered:Array.from({length:400},(_,i)=>filtered[Math.floor(i*filtered.length/400)]);
  if($("connections").checked){ctx.beginPath();shown.forEach(r=>{ctx.moveTo(...project(r.olon,r.olat));ctx.lineTo(...project(r.dlon,r.dlat));});ctx.strokeStyle="#749e9330";ctx.lineWidth=.7;ctx.stroke();}
  shown.forEach(r=>{const [x,y]=project(r.dlon,r.dlat);ctx.beginPath();ctx.arc(x,y,2.7,0,2*Math.PI);ctx.strokeStyle="#aa6728aa";ctx.lineWidth=1;ctx.stroke();});
  shown.forEach(r=>{const [x,y]=project(r.olon,r.olat);ctx.beginPath();ctx.arc(x,y,2.3,0,2*Math.PI);ctx.fillStyle="#087a70b0";ctx.fill();});
  $("map-count").textContent=`${fmt(filtered.length)}건 중 ${fmt(shown.length)}건 표시`;
  $("map-note").textContent=filtered.length?"겹친 점은 같은 위치의 요청입니다. 지도는 시간순 목록에서 최대 400건을 고른 표시이며, 그래프·표·CSV에는 전체 요청을 사용합니다.":"선택한 시간대에 생성된 요청이 없습니다.";
}
function render(config) {
  current=generate(config);
  const {rows,p,n}=current, counts=Array(6).fill(0),quarters=Array(24).fill(0);
  rows.forEach(r=>{counts[Math.floor(r.time/60)-18]++;quarters[Math.floor((r.time-1080)/15)]++;});
  $("actual-count").textContent=fmt(rows.length);$("expected-count").textContent=fmt(n);
  $("peak-hour").textContent=rows.length?`${18+counts.indexOf(Math.max(...counts))}시대`:"없음";
  $("unique-count").textContent=fmt(new Set(rows.map(r=>r.source)).size);
  const notes={
    fixed:["Σ Nₕ = N",`총건수 ${fmt(n)}건을 먼저 정합니다. 시간대별 건수는 달라져도 합계는 항상 같습니다. 시간대별 기댓값은 N × pₕ입니다.`],
    bootstrap:["(시각, 출발지, 목적지) 행 전체를 복원추출", "기준 1,000행에서 같은 크기의 목록을 다시 만듭니다. 동일한 행이 여러 번 뽑히며, 빠지는 행도 있습니다. 원래 행의 분 단위 시각을 유지합니다."],
    poisson:["Nₕ ∼ Poisson(μ × pₕ)",`여섯 시간의 기대 총건수는 ${fmt(n)}건입니다. 시간대별 호출 수를 독립적으로 뽑으므로 합계도 달라집니다. 총건수 표준편차의 이론값은 √μ = ${fmt(Math.sqrt(n),1)}건입니다.`]
  };
  $("formula").textContent=notes[config.method][0];$("method-note").textContent=notes[config.method][1];
  bars("hour-chart",counts,p.map(w=>w*n),Array.from({length:6},(_,i)=>`${i+18}시`));
  bars("minute-chart",quarters,null,Array.from({length:24},(_,i)=>i%4===0?`${18+i/4}시`:""),{height:170});
  $("hour-note").textContent=config.method==="bootstrap"?"기댓값은 기준 요청의 시간대 비중 × 1,000입니다. 재표집으로 시간대별 건수는 달라져도 총건수는 1,000건입니다.":`비중 pₕ는 ‘${$("profile").selectedOptions[0].textContent}’입니다. 시간대 안에서는 호출 시각을 균등하게 뽑습니다.`;
  const reps=repetitions(config);current.reps=reps;
  histogram("repeat-chart",reps[config.method].totals,COLORS[config.method],Object.values(reps).flatMap(r=>r.totals));
  $("repeat-note").textContent=`${NAMES[config.method]} · 500회 총건수 평균 ${fmt(reps[config.method].total.mean,1)}건, 표준편차 ${fmt(reps[config.method].total.sd,1)}건입니다. 이 분포는 지정한 모형에서의 변동입니다.`;
  $("comparison").querySelector("tbody").innerHTML=Object.entries(reps).map(([k,r])=>`<tr class="${k===config.method?"selected-row":""}"><td>${NAMES[k]}</td><td>${fmt(r.total.mean,1)}</td><td>${fmt(r.total.sd,1)}</td><td>${fmt(r.peak.sd,1)}</td></tr>`).join("");
  $("comparison-note").textContent="고정·포아송은 선택한 건수와 시간대 비중을 사용합니다. 행 재표집은 항상 기준 요청의 1,000건·시간대 비중을 사용합니다. 같은 기댓값으로 비교하려면 1,000건과 ‘예제 요청’ 비중을 선택합니다.";
  $("request-table").querySelector("tbody").innerHTML=rows.length?rows.slice(0,8).map(r=>`<tr><td>${r.id}</td><td>${Math.floor(r.time/60)}:${String(r.time%60).padStart(2,"0")}</td><td>${r.olat.toFixed(5)}, ${r.olon.toFixed(5)}</td><td>${r.dlat.toFixed(5)}, ${r.dlon.toFixed(5)}</td><td>${r.source}</td></tr>`).join(""):'<tr><td colspan="5" class="empty">생성된 요청이 없습니다. 0건도 포아송 모형에서 가능한 결과입니다.</td></tr>';
  $("hour-table").querySelector("tbody").innerHTML=Array.from({length:6},(_,i)=>`<tr><td>${18+i}시대</td><td>${fmt(DATA.odHourly[18+i],1)}명</td><td>${DATA.referenceHourly[18+i]}건</td><td>${fmt(n*p[i],1)}건</td><td>${counts[i]}건</td></tr>`).join("");
  $("status").className="";$("status").textContent=`${NAMES[config.method]} · 씨앗 ${config.seed} · ${fmt(rows.length)}건을 생성했습니다. 조건을 바꾸면 결과가 갱신됩니다.`;
  map();
}
function readConfig() {
  const method=document.querySelector('input[name="method"]:checked').value;
  const n=method==="bootstrap"?REFERENCE.length:Number($("count").value),seed=Number($("seed").value);
  if(!$("settings").checkValidity()||!Number.isInteger(n)||!Number.isInteger(seed)) {
    $("status").className="error";$("status").textContent="건수는 0~5,000, 씨앗은 0~4,294,967,295의 정수로 입력합니다. 아래에는 마지막으로 생성한 결과가 표시됩니다.";
    return null;
  }
  return {method,n,seed,profile:$("profile").value};
}
function update() {const c=readConfig();if(c)render(c);}
function setMethod() {
  const method=document.querySelector('input[name="method"]:checked').value, boot=method==="bootstrap";
  $("count").disabled=boot;$("profile").disabled=boot;
  $("count-label").textContent=boot?"재표집 건수 · 기준과 동일":method==="poisson"?"기대 총건수 μ":"총 호출 건수 N";
  if(boot){$("count").value=1000;$("profile").value="reference";}
  update();
}
function csv() {
  const head="id,request_time,origin_lat,origin_lon,dest_lat,dest_lon,mode,source_id";
  return head+"\n"+current.rows.map(r=>[r.id,r.time,r.olat,r.olon,r.dlat,r.dlon,"taxi",r.source].join(",")).join("\n")+"\n";
}
$("settings").addEventListener("submit",e=>{e.preventDefault();update();});
document.querySelectorAll('input[name="method"]').forEach(el=>el.addEventListener("change",setMethod));
["count","profile","seed"].forEach(id=>$(id).addEventListener("change",update));
$("next").addEventListener("click",()=>{const c=readConfig();if(c){$("seed").value=(c.seed+1)>>>0;update();}});
$("reset").addEventListener("click",()=>{HTMLFormElement.prototype.reset.call($("settings"));$("hour").value="all";$("connections").checked=false;setMethod();});
$("hour").addEventListener("change",map);$("connections").addEventListener("change",map);
$("download").addEventListener("click",()=>{const blob=new Blob([csv()],{type:"text/csv;charset=utf-8"}),url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=`hanam_${current.config.method}_seed${current.config.seed}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
window.addEventListener("resize",map);
const totalOd=DATA.odHourly.reduce((a,b)=>a+b,0);
bars("od-chart",DATA.odHourly.map(x=>100*x/totalOd),null,Array.from({length:24},(_,h)=>`${h}시`),{width:1100,height:220,percent:true,colors:Array.from({length:24},(_,h)=>h<18?"#7fada0":"#aa6728")});
$("od-note").textContent=`집계값 합계 ${fmt(totalOd,1)}명 · 8시대 비중 ${fmt(DATA.odHourly[8]/totalOd*100,2)}%. 파일에 날짜 열이 없어 날짜별 변동은 이 자료로 계산하지 않습니다.`;
$("sources").innerHTML=Object.entries(DATA.sources).map(([name,hash])=>`<p>data/hanam/${name}<br>${hash}</p>`).join("");
window.DemandLab={generate,repetitions,poisson,random,weights,csv,get current(){return current;}};
update();
