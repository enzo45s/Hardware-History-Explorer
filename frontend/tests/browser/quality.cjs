/* Real UI with an isolated, synthetic catalog. No operator data or live scraping. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const base=process.env.HHE_BASE_URL||'http://127.0.0.1:8080/';
 const apiBase=process.env.HHE_QUALITY_API_URL||'http://127.0.0.1:18095';
 assert(['127.0.0.1','localhost'].includes(new URL(apiBase).hostname));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  const marker=await(await page.request.get(apiBase+'/__quality_fixture')).json();
  assert.equal(marker.fixture,'catalog-quality-synthetic');assert.equal(marker.isolated,true);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url());const response=await route.fetch({url:new URL(u.pathname+u.search,apiBase).href});await route.fulfill({response});});
  const meta=await(await page.request.get(apiBase+'/api/meta')).json();
  const maker=meta.manufacturers.find(m=>m.name==='Commodore');
  const ids=[];
  for(const keyboard of ['B','N'])for(const ram of [8,16,32]){
   const response=await page.request.post(apiBase+'/api/computers',{data:{manufacturer_id:maker.id,model_name:`PET 2001-${keyboard}${ram}`,description:`Storia sintetica ${keyboard}${ram}.`,
    configurations:[{variant_name:'Base',specifications:[{component_type:'RAM',property_name:'Capacità',numeric_value:ram,unit:'KB'},{component_type:'Tastiera',property_name:'Variante',text_value:keyboard}]}],
    releases:[{market_id:meta.markets[0].id,release_date:'1979',price:100+ram,currency:'USD'}]}});
   assert.equal(response.status(),201);ids.push((await response.json()).id);
  }
  const hpMaker=await(await page.request.post(apiBase+'/api/manufacturers',{data:{name:'HP'}})).json();
  const hpResponse=await page.request.post(apiBase+'/api/computers',{data:{manufacturer_id:hpMaker.id,model_name:'HP 85',description:'Contesto sintetico già curato.'}});
  assert.equal(hpResponse.status(),201);const hp=(await hpResponse.json()).id;
  await page.goto(base);
  async function openQuality(){await page.getByRole('button',{name:'Amministrazione',exact:true}).click();await page.getByRole('button',{name:'RAM e varianti',exact:true}).click();}
  await openQuality();await page.getByRole('button',{name:'Controlla RAM mancanti',exact:true}).click();
  await page.getByRole('button',{name:'Completa RAM documentata',exact:true}).click();
  await page.getByRole('status').filter({hasText:'RAM aggiunta a 1 sistemi'}).waitFor();
  const hpData=await(await page.request.get(apiBase+`/api/computers/${hp}`)).json();
  assert.equal(hpData.description,'Contesto sintetico già curato.');assert.equal(hpData.configurations[0].specifications[0].text_value,'16 - 32Kb');
  await page.getByRole('button',{name:'Analizza varianti da accorpare',exact:true}).click();
  await page.getByRole('button',{name:'Accorpa i gruppi selezionati',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Accorpate 5 schede'}).waitFor();
  const found=await(await page.request.get(apiBase+'/api/computers?q=B16')).json();assert.equal(found.total,1);const family=found.items[0];
  const data=await(await page.request.get(apiBase+`/api/computers/${family.id}`)).json();
  assert.equal(data.model_name,'PET 2001');assert.equal(data.configurations.length,6);assert.equal(data.releases.length,6);
  assert.deepEqual([...new Set(data.configurations.flatMap(c=>c.specifications.filter(s=>s.component_type==='RAM').map(s=>s.numeric_value)))].sort((a,b)=>a-b),[8,16,32]);
  assert(data.releases.every(r=>r.model_variant));
  await page.getByRole('button',{name:'Catalogo',exact:true}).click();await page.getByPlaceholder('Cerca un sistema…',{exact:true}).fill('B16');
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:'PET 2001',exact:true})}).getByRole('button',{name:'Dettagli',exact:true}).click();
  await page.getByRole('heading',{name:'PET 2001',level:1,exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:/Configurazione · PET 2001-/}).count(),6);
  assert.match(await page.locator('main').innerText(),/Configurazione: PET 2001-N16/);
  assert.match(await page.locator('main').innerText(),/Storia sintetica B8/);
  await openQuality();for(const width of [320,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(errors,[]);console.log('PASS quality browser: HP 85 sourced RAM, PET variants/configurations, price scope, old-name search, preserved histories and mobile.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
