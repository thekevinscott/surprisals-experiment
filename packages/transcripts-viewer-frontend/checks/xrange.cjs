// NODE_PATH, CHROMIUM_PATH and VIEWER_URL follow chart-points.cjs.
const {chromium}=require('playwright')
const assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[]
  page.on('pageerror',e=>errors.push(String(e)))
  const base=process.env.VIEWER_URL||'http://localhost:5173'
  await page.goto(`${base}/#run/20261113-034702-wild-recipe`)
  const top=page.locator('.run-graphs .cell-chart')
  await top.locator('.x-slider').waitFor()
  async function drag(chart,knob,fraction) {
   const handle=chart.locator(`.x-slider [data-knob="${knob}"]`)
   await handle.scrollIntoViewIfNeeded()
   const box=await handle.boundingBox(),track=await chart.locator('.x-slider .track').boundingBox()
   await page.mouse.move(box.x+box.width/2,box.y+box.height/2)
   await page.mouse.down()
   await page.mouse.move(track.x+track.width*fraction,box.y+box.height/2,{steps:10})
   await page.mouse.up()
  }
  const before=await top.locator('.chart-point').count()
  const pathBefore=await top.locator('[data-cell] > path').first().getAttribute('d')
  await drag(top,'lo',.2);await drag(top,'hi',.8)
  assert.ok(await top.locator('.chart-point').count()<before)
  assert.notEqual(await top.locator('[data-cell] > path').first().getAttribute('d'),pathBefore)
  const ticks=await top.locator('text[y="255"]').allTextContents()
  assert.deepEqual(ticks,['10','20','30'])
  assert.equal(await top.locator('.window-boundary[data-window="0"]').count(),0)
  if(process.env.ARTIFACT_DIR)await page.screenshot({path:`${process.env.ARTIFACT_DIR}/xrange-zoom.png`})
  const labels=await top.locator('.chart-point').evaluateAll(points=>points.map(p=>p.getAttribute('aria-label')))
  assert.ok(!labels.some(label=>label.startsWith('Window 0 · Fork 0 · Turn 0:')))
  const point=top.locator('.chart-point').last()
  const label=await point.getAttribute('aria-label')
  const expected=label.split(':')[0]
  await point.click()
  await page.getByText(new RegExp(`U transcript · ${expected}`)).waitFor()
  await page.getByRole('button',{name:'Close',exact:true}).click()
  const forks=page.locator('.fork-chart .cell-chart')
  await forks.first().waitFor()
  assert.equal(await forks.locator('.x-slider').count(),0)
  assert.ok(await forks.locator('.y-slider').count()>=4)
  await page.goto(`${base}/#run/20261113-034702-still-bar`)
  await page.waitForFunction(()=>{
   const selected=document.querySelector('.run-graphs .x-slider .selected')
   return selected&&Number(selected.getAttribute('x1'))===0
  })
  assert.deepEqual(errors,[])
  console.log('X knobs rescale and clip top graph; click opens correct U turn; fork charts keep y sliders only; run switch resets zoom.')
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
