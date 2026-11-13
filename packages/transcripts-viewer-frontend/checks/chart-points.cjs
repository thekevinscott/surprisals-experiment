// Run against the live viewer with Playwright available on NODE_PATH.
const {chromium}=require('playwright')
const assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[]
  page.on('pageerror',error=>errors.push(String(error)))
  const base=process.env.VIEWER_URL || 'http://localhost:5173'
  for(const id of ['20261113-034702-wild-recipe','20261113-034702-still-bar']){
   await page.goto(`${base}/#run/${id}`)
   const {diagram}=await (await page.request.get(`${base}/api/runs/${id}`)).json()
   async function check(window,fork,turn){
    const branch=diagram.find(w=>w.id===window).forks.find(f=>f.id===fork)
    const record=[...branch.parallel,...branch.solo].find(t=>t.id===turn)
    await page.getByText(new RegExp(`U transcript · Window ${window} · Fork ${fork} · Turn ${turn}`)).waitFor({timeout:5000})
    const metadata=await (await page.request.get(`${base}/api/runs/${id}/transcripts/${record.transcriptPath}`)).json()
    const count=record.metadata.u_messages
    const expected=count==null ? metadata.blocks.length : count+(metadata.blocks[count]?.type==='assistant' ? 1 : 0)
    await page.waitForFunction(n=>document.querySelectorAll('.p-dialog .message-blocks [data-block]').length===n,expected,{timeout:5000})
    await page.locator('.p-dialog .block-navigation button').last().click()
    const advice=await (await page.request.get(`${base}/api/runs/${id}/files/${record.adviceSource}`)).text()
    const output=page.locator(`.p-dialog [data-block="${expected}"] [data-part="content"] p`)
    await output.waitFor({timeout:5000})
    assert.equal((await output.textContent()).trim(),advice.trim())
    await output.scrollIntoViewIfNeeded()
   }
   const cell=`${id}/windows/0/forks/1`
   const point=page.locator(`.run-graphs [data-cell="${cell}"] [data-turn="1"]`)
   await point.click({timeout:5000});await check(0,1,1)
   if(process.env.ARTIFACT_DIR)await page.screenshot({path:`${process.env.ARTIFACT_DIR}/chart-point-${id}.png`})
   await page.getByRole('button',{name:'Next U turn',exact:true}).click();await check(0,1,2)
   await page.keyboard.press('ArrowLeft');await check(0,1,1)
   await page.getByRole('button',{name:'Close',exact:true}).click()
   const forkPoint=page.locator('[data-window="1"] .fork-branch[data-fork="0"] .fork-chart [data-turn="1"]')
   await forkPoint.focus({timeout:5000});await page.keyboard.press('Enter');await check(1,0,1)
   await page.getByRole('button',{name:'Close',exact:true}).click()
   const solo=diagram[0].forks.find(f=>f.solo.some(t=>t.advice))
   const turn=solo.solo.find(t=>t.advice).id
   await page.locator(`[data-window="0"] .solo[data-fork="${solo.id}"] .fork-chart [data-turn="${turn}"]`).click({timeout:5000});await check(0,solo.id,turn)
   await page.getByRole('button',{name:'Close',exact:true}).click()
   console.log(`${id}: top click, parallel keyboard, solo click, exact advice and turn arrows passed`)
  }
  assert.deepEqual(errors,[])
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1})
