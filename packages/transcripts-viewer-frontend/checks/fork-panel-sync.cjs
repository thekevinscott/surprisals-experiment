const {chromium}=require('playwright'),assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  await page.goto(`${process.env.VIEWER_URL||'http://localhost:5173'}/#run/20261113-034702-still-bar`)
  const toggles=(p,window,phase='fork')=>p.locator(`.run-window[data-window="${window}"] .${phase}-phase .fork-chart > .p-panel-header .accordion-toggle`)
  async function state(p,window,expected,phase='fork'){
   await toggles(p,window,phase).first().waitFor()
   const values=await toggles(p,window,phase).evaluateAll(es=>es.map(e=>e.getAttribute('aria-expanded')))
   assert.deepEqual(values,Array(phase==='fork'?4:1).fill(String(expected)))
  }
  await state(page,0,true);await state(page,1,true);await state(page,0,true,'solo')
  await toggles(page,0).first().click()
  await state(page,0,false);await state(page,1,true);await state(page,0,true,'solo')
  const url=page.url(),keys=[...new URLSearchParams(url.split('?')[1]).keys()].filter(k=>k.includes('fork-chart'))
  assert.equal(keys.length,1);assert.ok(keys[0].endsWith('/fork-chart-0-parallel'))
  await page.reload();await state(page,0,false);await state(page,1,true);await state(page,0,true,'solo')
  const tab=await browser.newPage();await tab.goto(url);await state(tab,0,false);await tab.close()
  await toggles(page,0).nth(2).click()
  await state(page,0,true);await state(page,1,true);await state(page,0,true,'solo')
  assert.ok(!page.url().includes('fork-chart'))
  console.log('Four sibling graphs collapse/expand together; other window and solo stay independent; one URL key restores after reload/fresh tab.')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
