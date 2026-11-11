"""Playwright와 Edge로 독립 HTML, 목적함수, 모바일 배치를 확인합니다."""
import json
import os
from pathlib import Path
import tempfile
import re
import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.gettempdir()) / 'ch10-preview'
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto((ROOT / '_static/ch10_optimization.html').as_uri())
    page.screenshot(path=str(OUT / 'taxi.png'), full_page=True)
    # 작은 입력의 완전탐색 결과를 독립적인 검산 기준으로 사용합니다.
    result = page.evaluate('''() => {
      function brute(n,m,limit,obj){let best=null;
        function visit(i,used,count,total,max){if(i===n){let score=[-count,obj==='sum'?total:max];if(!best||score[0]<best[0]||(score[0]===best[0]&&score[1]<best[1]))best=score;return;}
          visit(i+1,used,count,total,max);
          for(let j=0;j<m;j++){let c=data.taxi[i][j].seconds;if(!(used&(1<<j))&&c<=limit)visit(i+1,used|(1<<j),count+1,total+c,Math.max(max,c));}}
        visit(0,0,0,0,0);return best;}
      let count=0;
      for(let n=1;n<=5;n++)for(let m=1;m<=5;m++)for(const limit of [60,180,600])for(const obj of ['sum','max']){
        const pairs=matching(n,m,limit,obj),times=pairs.map(([i,j])=>data.taxi[i][j].seconds),actual=[-pairs.length,obj==='sum'?times.reduce((a,b)=>a+b,0):Math.max(0,...times)],expected=brute(n,m,limit,obj);
        if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error(JSON.stringify({n,m,limit,obj,actual,expected}));count++;}
      const roadPath = document.querySelector('#geography > path').getAttribute('d');
      return {cases:count,roads:(roadPath.match(/M/g)||[]).length};
    }''')
    assert result['roads'] > 100
    for n, m, limit, objective in [(12, 12, '600', 'sum'), (12, 6, '600', 'sum'),
                                   (12, 12, '180', 'sum'), (12, 12, '600', 'max')]:
        page.locator('#passengers').fill(str(n))
        page.locator('#vehicles').fill(str(m))
        page.locator('#limit').select_option(limit)
        page.locator('#objective').select_option(objective)
        print(page.locator('#summary').inner_text())
    page.locator('#truck').click()
    for trucks in range(2, 7):
        page.locator('#trucks').fill(str(trucks))
        for capacity in ('7', '10', '15'):
            page.locator('#capacity').select_option(capacity)
            for objective in ('sum', 'max'):
                page.locator('#truckObjective').select_option(objective)
                for method in ('delivery', 'exact'):
                    page.locator('#truckMethod').select_option(method)
                    actual = page.evaluate('''() => {
                      const r=data.fleet.solutions[`${$('trucks').value}:${$('capacity').value}:${$('truckObjective').value}`][$('truckMethod').value];
                      return {feasible:r.cost!==null, routes:selectedPaths.length, depot:projection.xy(data.fleet.stops[0]), center:[projection.w/2,projection.h/2]};
                    }''')
                    assert actual['routes'] == (trucks if actual['feasible'] else 0)
                    assert page.locator('#truckStatus').is_visible() != actual['feasible']
                    assert actual['depot'] == actual['center']
                    assert page.locator('#results [data-route]').count() == actual['routes']
                    if actual['feasible']:
                        page.locator('#results [data-route="0"]').click()
                        assert 'T0' in page.locator('#selection').inner_text()
                        page.locator('#showAll').click()
    page.locator('#trucks').fill('4')
    page.locator('#capacity').select_option('10')
    page.locator('#truckObjective').select_option('max')
    page.locator('#truckMethod').select_option('exact')
    page.screenshot(path=str(OUT / 'truck.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 900})
    page.screenshot(path=str(OUT / 'mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#taxi').click()
    assert page.locator('#taxiControls').is_visible()
    assert not page.locator('#truckControls').is_visible()
    assert not errors, errors
    chapter = (ROOT / 'ko/ch10_dispatch.md').read_text(encoding='utf-8')
    assert '```' not in chapter and 'jupytext:' not in chapter
    for target in re.findall(r'\]\(([^)]+)\)', chapter):
        if not target.startswith('http'):
            assert (ROOT / 'ko' / target).exists(), target
    preview = OUT / 'chapter.html'
    preview.write_text('<meta charset="utf-8"><base href="' + (ROOT / 'ko').as_uri() + '/">'
                       + '<style>body{font:18px/1.8 system-ui;max-width:950px;margin:40px auto}img{max-width:100%}td,th{padding:8px;border-bottom:1px solid #ccc}</style>'
                       + markdown.markdown(chapter, extensions=['tables']), encoding='utf-8')
    page.set_viewport_size({'width': 1200, 'height': 1000})
    page.goto(preview.as_uri())
    assert page.locator('h1').count() == 1
    assert page.locator('table').count() >= 4
    assert page.locator('img').evaluate_all('(imgs)=>imgs.every(i=>i.complete&&i.naturalWidth>0)')
    page.screenshot(path=str(OUT / 'chapter.png'))
    print(json.dumps(result), OUT)
    browser.close()
