#!/usr/bin/env python3
from __future__ import annotations
import asyncio, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright

SZ_BASE='https://www.szse.cn/api/report/ShowReport/data'
SZ_PARAMS={'SHOWTYPE':'JSON','CATALOGID':'SGT_GGTBDQD','TABKEY':'tab1'}
SSE_PAGE='https://www.sse.com.cn/services/hkexsc/disclo/eligible/'
CODE_RE=re.compile(r'(?<!\d)(\d{5})(?!\d)')

async def main():
  out={'program_id':'HKCU-1-R2B-CONTRACT-PROBE','generated_at':datetime.now(timezone.utc).isoformat(),'sz':{},'sse':{},'trade_authority':'NONE'}
  async with async_playwright() as pw:
    browser=await pw.chromium.launch(headless=True)
    ctx=await browser.new_context(locale='zh-CN',user_agent='Mozilla/5.0 Chrome/131 Safari/537.36')
    page=await ctx.new_page()
    # Probe common SZ pagination parameters deterministically.
    variants=[]
    for extra in ({},{'PAGENO':'1'},{'PAGENO':'1','PAGESIZE':'2000'},{'PAGENO':'1','pageSize':'2000'},{'loading':'first'}):
      params={**SZ_PARAMS,**extra}
      url=SZ_BASE+'?'+urlencode(params)
      r=await ctx.request.get(url,headers={'Referer':'https://www.szse.cn/szhk/hkbussiness/underlylist/'})
      text=await r.text()
      item={'url':url,'status':r.status,'content_type':r.headers.get('content-type'),'bytes':len(text.encode()),'codes':len(set(CODE_RE.findall(text)))}
      try:
        data=json.loads(text)
        item['top_type']=type(data).__name__
        if isinstance(data,list):
          item['list_len']=len(data)
          item['sections']=[{'keys':sorted(x.keys()),'metadata':x.get('metadata'),'data_len':len(x.get('data',[])) if isinstance(x.get('data'),list) else None} for x in data if isinstance(x,dict)]
      except Exception as e: item['parse_error']=str(e)
      variants.append(item)
    out['sz']={'variants':variants}
    # Capture SSE DOM/script/network contract without guessing endpoint IDs.
    urls=[]
    page.on('request',lambda req: urls.append(req.url))
    errors=[]
    page.on('console',lambda msg: errors.append({'type':msg.type,'text':msg.text}) if msg.type in {'error','warning'} else None)
    await page.goto(SSE_PAGE,wait_until='networkidle',timeout=60000)
    await page.wait_for_timeout(5000)
    scripts=await page.eval_on_selector_all('script[src]','els=>els.map(e=>e.src)')
    hrefs=await page.eval_on_selector_all('a[href]','els=>els.map(e=>e.href).filter(x=>/download|eligible|query|api|csv|xls/i.test(x))')
    html=await page.content()
    out['sse']={'request_urls':sorted(set(urls)),'script_src':scripts,'candidate_hrefs':hrefs,'html_markers':sorted(set(re.findall(r'(?:https?:)?//[^\"\'<> ]+|[A-Z_]{6,}|sqlId[^\"\'<> ]*',html,re.I)))[:500],'console':errors[:100]}
    await browser.close()
  p=Path('outputs/hkcu1/discovery/HKCU1_ENDPOINT_CONTRACT_PROBE.json'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': asyncio.run(main())
