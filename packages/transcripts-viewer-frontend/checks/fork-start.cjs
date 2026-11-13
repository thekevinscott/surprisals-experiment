const {chromium}=require('playwright'),assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[]
  page.on('pageerror',e=>errors.push(String(e)))
  await page.goto(`${process.env.VIEWER_URL||'http://localhost:5173'}/#run/20261113-034702-still-bar`)
  const chart=page.locator('.run-graphs .cell-chart')
  await chart.locator('.window-boundary[data-window="2"]').waitFor()
  async function check(){
   const results=await chart.evaluate(el=>[1,2].map(window=>{
    const boundary=Number(el.querySelector(`.window-boundary[data-window="${window}"] line`).getAttribute('x1'))
    const starts=[...el.querySelectorAll(`[data-cell*="/windows/${window}/"] > path`)].map(p=>p.getAttribute('d')).filter(Boolean).map(d=>Number(d.match(/^M\s*([\d.e+-]+)/)[1]))
    return {window,boundary,starts}
   }))
   for(const {window,boundary,starts} of results){
    assert.ok(starts.length>0,`window ${window} has scored forks`)
    for(const start of starts)assert.ok(start>=boundary-0.01,`window ${window}: ${start} precedes ${boundary}`)
    assert.ok(starts.some(start=>Math.abs(start-boundary)<0.01),`window ${window} begins at first turn`)
   }
   return results
  }
  console.log('Full range:',await check())
  const knob=chart.locator('.x-slider [data-knob="lo"]'),box=await knob.boundingBox(),track=await chart.locator('.x-slider .track').boundingBox()
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down()
  await page.mouse.move(track.x+track.width*.2,box.y+box.height/2,{steps:10});await page.mouse.up()
  console.log('Zoomed range:',await check())
  const ticks=await chart.locator('text[y="255"]').allTextContents()
  assert.ok(ticks.includes('20')&&ticks.includes('40'))
  assert.equal(await page.locator('.fork-chart .x-slider').count(),0)
  assert.deepEqual(errors,[])
  console.log('Still-bar windows 1 and 2 start within their own windows before and after x zoom; labels remain correct.')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
