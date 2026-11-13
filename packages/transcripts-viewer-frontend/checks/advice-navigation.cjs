const {chromium}=require('playwright'),assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[]
  page.on('pageerror',e=>errors.push(String(e)))
  const base=process.env.VIEWER_URL||'http://localhost:5173',run='20261113-034702-still-bar'
  await page.goto(`${base}/#run/${run}`)
  const {diagram}=await (await page.request.get(`${base}/api/runs/${run}`)).json()
  const fork=diagram.find(w=>w.id===2).forks.find(f=>f.id===2)
  const turns=[...fork.parallel,...fork.solo].filter(t=>t.advice!=null).sort((a,b)=>a.id-b.id)
  const title=t=>`Window 2 · Fork 2${fork.solo.some(s=>s.id===t.id)?' continues':''} · Turn ${t.id} · Advice`
  async function check(p,t){
   await p.getByText(title(t),{exact:true}).waitFor()
   await p.waitForFunction(text=>document.querySelector('.p-dialog .file-viewer pre')?.textContent===text,t.advice)
   assert.ok((await p.locator('.p-dialog .modal-action').first().getAttribute('href')).endsWith(t.adviceSource))
  }
  await page.locator('.run-window[data-window="2"] .fork-branch[data-fork="2"] .turn-block[data-turn="0"]').getByRole('button',{name:'Open advice',exact:true}).click()
  await check(page,turns[0]);assert.equal(await page.getByRole('button',{name:'Previous advice',exact:true}).isDisabled(),true)
  await page.getByRole('button',{name:'Next advice',exact:true}).click();await check(page,turns[1])
  await page.keyboard.press('ArrowRight');await check(page,turns[2])
  await page.keyboard.press('ArrowLeft');await check(page,turns[1])
  const url=page.url();await page.reload();await check(page,turns[1])
  const context=await browser.newContext(),tab=await context.newPage();await tab.goto(url);await check(tab,turns[1]);await context.close()
  for(const turn of turns.slice(2)){await page.getByRole('button',{name:'Next advice',exact:true}).click();await check(page,turn)}
  assert.equal(await page.getByRole('button',{name:'Next advice',exact:true}).isDisabled(),true)
  await page.screenshot({path:'/tmp/claude/brief-viewer-lazy/advice-navigation.png'})
  await page.getByRole('button',{name:'Close',exact:true}).click()
  await page.locator('.run-window[data-window="0"] .solo-phase').getByRole('button',{name:'Open advice',exact:true}).first().click()
  assert.match(await page.locator('.p-dialog-title').textContent(),/Window 0 · Fork \d+ continues · Turn \d+ · Advice/)
  assert.deepEqual(errors,[])
  console.log(`Still-bar window2 fork2: ${turns.length} advices, matching content/raw links, button/keyboard navigation, disabled endpoints, reload/fresh tab, and solo label pass.`)
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
