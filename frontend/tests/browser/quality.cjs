/* Real UI with an isolated, synthetic catalog. No operator data or live scraping. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const base=process.env.HHE_BASE_URL||'http://127.0.0.1:8080/';
 const apiBase=process.env.HHE_QUALITY_API_URL||'http://127.0.0.1:18095';
 assert(['127.0.0.1','localhost'].includes(new URL(apiBase).hostname));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],batches=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  const marker=await(await page.request.get(apiBase+'/__quality_fixture')).json();
  assert.equal(marker.fixture,'catalog-quality-synthetic');assert.equal(marker.isolated,true);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url());if(u.pathname.endsWith('/catalog-quality/variants/apply'))batches.push(route.request().postDataJSON().target_ids.length);const response=await route.fetch({url:new URL(u.pathname+u.search,apiBase).href});await route.fulfill({response});});
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
  // Different source profiles are one sheet; video standards remain on values.
  const atariResponse=await page.request.post(apiBase+'/api/computers',{data:{manufacturer_id:maker.id,model_name:'Synthetic Atari 400',configurations:[
   {variant_name:'NTSC',specifications:[{component_type:'CPU',component_name:'maincpu',property_name:'Modello',text_value:'6502'},
    {component_type:'Video',property_name:'Frequenza di aggiornamento',numeric_value:60,unit:'Hz'}]},
   {variant_name:'PAL',specifications:[{component_type:'CPU',component_name:'maincpu',property_name:'Modello',text_value:'6502'},
    {component_type:'Video',property_name:'Frequenza di aggiornamento',numeric_value:50,unit:'Hz'}]},
   {variant_name:'Scheda tecnica',specifications:[{component_type:'CPU',property_name:'Modello',text_value:'6502'},
    {component_type:'RAM',property_name:'Capacità riportata',text_value:'16 - 48Kb'}]}
  ]}});assert.equal(atariResponse.status(),201);const atariId=(await atariResponse.json()).id;
  await page.getByRole('button',{name:'Catalogo',exact:true}).click();await page.getByPlaceholder('Cerca un sistema…',{exact:true}).fill('Synthetic Atari 400');
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:'Synthetic Atari 400',exact:true})}).getByRole('button',{name:'Dettagli',exact:true}).click();
  const technical=page.getByRole('region',{name:'Configurazione · Scheda tecnica',exact:true});await technical.waitFor();
  assert.equal(await page.getByRole('region',{name:/^Configurazione ·/}).count(),1);
  assert.equal(await technical.getByRole('row').filter({hasText:'CPU · Modello'}).count(),1);
  assert.doesNotMatch(await technical.innerText(),/PAL|NTSC|50 Hz|60 Hz/);
  assert.match(await technical.innerText(),/16 - 48Kb/);
  for(const width of [320,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:1440,height:1000});
  const atariRaw=await(await page.request.get(apiBase+`/api/admin/computers/${atariId}`)).json();assert.equal(atariRaw.configurations.length,3);
  await page.getByRole('button',{name:'Confronta',exact:true}).click();
  const picker=page.getByRole('combobox',{name:'Cerca un sistema da aggiungere'});
  for(const name of ['Synthetic Atari 400','PET 2001']){await picker.fill(name);await page.getByRole('listbox',{name:'Sistemi trovati'}).getByRole('option').filter({hasText:name}).click();}
  await page.getByRole('table',{name:'Confronto dei sistemi e delle configurazioni selezionate'}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'Configurazione di Synthetic Atari 400',exact:true}).count(),0);
  assert.equal(await page.getByRole('combobox',{name:'Configurazione di PET 2001',exact:true}).getByRole('option').count(),7);
  assert.doesNotMatch(await page.locator('.comparison-results').innerText(),/PAL|NTSC|50 Hz|60 Hz/);
  // Reader RAM projection: two consistent rows, source evidence and variants intact.
  const ramSourceResponse=await page.request.post(apiBase+'/api/sources',{data:{title:'Synthetic RAM documentation',url:'https://example.org/ram-display',source_type:'manual'}});
  assert.equal(ramSourceResponse.status(),201);const ramSource=(await ramSourceResponse.json()).id;
  const ramSpec=(property,amount)=>({component_type:'RAM',property_name:property,numeric_value:amount,unit:'MiB',source_ids:[ramSource]});
  const ramComputers=[];
  for(const [name,configs] of [
   ['Synthetic RAM A',[{variant_name:'Base',specifications:[ramSpec('Capacità',4),ramSpec('Capacità di riferimento',4),ramSpec('Capacità massima riportata',8),{component_type:'RAM',property_name:'Opzioni di memoria',text_value:'4096 KiB / 8192 KiB',source_ids:[ramSource]}]},{variant_name:'Espansa',specifications:[ramSpec('Capacità',8),ramSpec('Capacità massima riportata',16)]}]],
   ['Synthetic RAM B',[{variant_name:'Base',specifications:[ramSpec('Capacità riportata',4),ramSpec('Capacità di riferimento',8),ramSpec('Limite hardware riportato',16)]}]]]){
    const response=await page.request.post(apiBase+'/api/computers',{data:{manufacturer_id:maker.id,model_name:name,description:'Contesto sintetico conservato.',configurations:configs}});
    assert.equal(response.status(),201);const id=(await response.json()).id;
    ramComputers.push(await(await page.request.get(apiBase+`/api/admin/computers/${id}`)).json());
  }
  for(const name of ['Synthetic Atari 400','PET 2001'])await page.getByRole('button',{name:`Rimuovi ${name} dal confronto`,exact:true}).click();
  for(const name of ['Synthetic RAM A','Synthetic RAM B']){await picker.fill(name);await page.getByRole('listbox',{name:'Sistemi trovati'}).getByRole('option').filter({hasText:name}).click();}
  const ramTable=page.getByRole('table',{name:'Confronto dei sistemi e delle configurazioni selezionate'});
  const ramRow=ramTable.getByRole('row').filter({has:page.getByRole('rowheader',{name:'RAM',exact:true})});
  const optionsRow=ramTable.getByRole('row').filter({has:page.getByRole('rowheader',{name:'RAM · Opzioni di memoria',exact:true})});
  await ramRow.getByRole('cell').nth(0).getByText('4 / 8 MB',{exact:true}).waitFor();
  assert.equal(await ramRow.count(),1);assert.equal(await optionsRow.count(),1);
  const ramHeaders=await ramTable.getByRole('rowheader').allTextContents();
  assert.equal(ramHeaders.indexOf('RAM · Opzioni di memoria'),ramHeaders.indexOf('RAM')+1);
  assert.equal(await ramRow.getByRole('cell').nth(1).locator('.comparison-spec-value').innerText(),'4 MB');
  assert.match(await ramRow.getByRole('cell').nth(1).innerText(),/Altri valori di riferimento: 8 MB/);
  assert.doesNotMatch(await ramTable.innerText(),/RAM · Capacità/);
  const ramA=await(await page.request.get(apiBase+`/api/computers/${ramComputers[0].id}`)).json();
  const baseConfig=ramA.display_configurations.find(c=>c.configuration_ids.includes(ramComputers[0].configurations[0].id));
  await page.getByRole('combobox',{name:'Configurazione di Synthetic RAM A',exact:true}).selectOption(String(baseConfig.id));
  await ramRow.getByRole('cell').nth(0).getByText('4 MB',{exact:true}).waitFor();
  assert.equal(await optionsRow.getByRole('cell').nth(0).locator('.comparison-spec-value').innerText(),'4 / 8 MB; Massima: 8 MB');
  for(const width of [320,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Catalogo',exact:true}).click();await page.getByPlaceholder('Cerca un sistema…',{exact:true}).fill('Synthetic RAM B');
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:'Synthetic RAM B',exact:true})}).getByRole('button',{name:'Dettagli',exact:true}).click();
  await page.getByRole('heading',{name:'Synthetic RAM B',level:1,exact:true}).waitFor();
  const ramSheet=page.getByRole('region',{name:/^Configurazione ·/});
  assert.equal((await ramSheet.locator('tr').allTextContents()).filter(text=>text.startsWith('RAM')).length,2);
  assert.doesNotMatch(await ramSheet.innerText(),/Capacità riportata|Capacità di riferimento|KiB/);
  for(const original of ramComputers){assert.deepEqual(await(await page.request.get(apiBase+`/api/admin/computers/${original.id}`)).json(),original);}
  // General rule, including singleton names and more than one batch of 100.
  for(const name of ['System-80 (50 Hz)','System-80 (60 Hz)','PDP-11 [Q-BUS] (M7195 - MXV11-B)','PDP-11 [Unibus](M9301-YA)','PDP-11 [Unibus](M9312)',...Array.from({length:103},(_,i)=>`Unlisted model ${i} (optional board)`)]){
   const manufacturerId=name.startsWith('PDP-11')?meta.manufacturers.find(m=>m.name==='Digital Equipment Corporation').id:maker.id;
   const r=await page.request.post(apiBase+'/api/computers',{data:{manufacturer_id:manufacturerId,model_name:name,configurations:[{variant_name:'Base',specifications:[{component_type:'CPU',property_name:'Modello',text_value:'Synthetic CPU'}]}]}});assert.equal(r.status(),201);
  }
  batches.length=0;await openQuality();await page.getByRole('button',{name:'Analizza varianti da accorpare',exact:true}).click();
  await page.getByText('105 nomi da sistemare; 4 schede duplicate da accorpare.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Accorpa i gruppi selezionati',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Aggiornati 105 nomi'}).waitFor();assert.deepEqual(batches,[100,5]);
  const cleaned=await(await page.request.get(apiBase+'/api/computers?limit=500')).json();
  assert.equal(cleaned.items.filter(c=>c.model_name==='System-80').length,1);assert.equal(cleaned.items.filter(c=>c.model_name==='PDP-11').length,1);
  assert.equal(cleaned.items.filter(c=>c.model_name.startsWith('Unlisted model ')).length,103);
  assert(cleaned.items.filter(c=>c.model_name.startsWith('Unlisted model ')).every(c=>!/[()[\]]/.test(c.model_name)));
  await openQuality();for(const width of [320,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(errors,[]);console.log('PASS quality browser: sourced RAM, one RAM field with adjacent options, readable units, preserved sources/raw records, independent configuration selection, hardware variants, no regional-video noise, 105 cleanup groups and mobile.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
