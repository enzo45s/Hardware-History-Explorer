/* Public company profiles and admin editing on synthetic local records only. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const base=process.env.HHE_BASE_URL||'http://127.0.0.1:8080/';
 assert(['localhost','127.0.0.1','[::1]'].includes(new URL(base).hostname));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('Browser error:',e.message)});
 const api=p=>new URL('/api'+p,base).href;
 const suffix=Date.now(),name='Synthetic company '+suffix,model='Synthetic company system '+suffix,ids=[];let maker;
 const shortDescription='Introduzione breve del calcolatore sintetico.';
 const longDescription='Storia del calcolatore: architettura, impieghi e contesto commerciale. '.repeat(60)+'Conclusione visibile nella scheda completa.';
 const longName=model+'D '+('Sistema professionale con un nome commerciale molto lungo ').repeat(3).slice(0,105);
 const checkComputerCards=async()=>{
  await page.waitForFunction(()=>document.querySelectorAll('.catalog-card').length===4);
  const dimensions=await page.locator('.catalog-card').evaluateAll(cards=>cards.map(card=>{
   const box=card.getBoundingClientRect(),description=card.querySelector('.catalog-card-description'),title=card.querySelector('h3');
   return {height:box.height,footer:card.querySelector('.card-foot').getBoundingClientRect().top-box.top,
    description:description.clientHeight,descriptionLine:parseFloat(getComputedStyle(description).lineHeight),
    title:title.clientHeight,titleLine:parseFloat(getComputedStyle(title).lineHeight),
    photo:card.querySelector('.catalog-photo').getBoundingClientRect().height};
  }));
  assert(dimensions.every(d=>d.height<=360&&Math.abs(d.height-dimensions[0].height)<1));
  assert(dimensions.every(d=>Math.abs(d.footer-dimensions[0].footer)<1
   &&d.description>0&&d.description<=2*d.descriptionLine+1&&d.description===dimensions[0].description
   &&d.title>0&&d.title<=2*d.titleLine+1&&d.title===dimensions[0].title
   &&d.photo>0&&d.photo<150&&d.photo===dimensions[0].photo));
  const long=page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'B',exact:true})}).locator('.catalog-card-description');
  assert(await long.evaluate(node=>node.scrollHeight>node.clientHeight),'Long descriptions must be clipped in previews.');
  assert.equal(await long.getAttribute('title'),null,'The full description belongs in the detail page.');
  assert(await page.getByText(shortDescription,{exact:true}).isVisible());
  assert(await page.getByText('Descrizione non ancora disponibile.',{exact:true}).isVisible());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 };
 try{
  await page.route('https://example.org/synthetic-company-logo.svg',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="70"><rect width="180" height="70" fill="navy"/><text x="25" y="46" fill="white" font-size="30">TEST</text></svg>'}));
  await page.route('https://example.org/synthetic-computer-cover.svg',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><rect width="300" height="100" fill="seagreen"/></svg>'}));
  const post=async(path,data)=>{const r=await page.request.post(api(path),{data});assert.equal(r.status(),201,await r.text());return r.json()};
  const source=await post('/sources',{title:'Synthetic company source '+suffix,url:'https://example.org/company-history'});
  await page.goto(base);await page.getByRole('button',{name:'Amministrazione',exact:true}).click();
  await page.getByRole('button',{name:'Produttori',exact:true}).click();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Scarica resoconto produttori',exact:true}).click();
  const download=await downloadPromise,stream=await download.createReadStream(),chunks=[];
  for await(const chunk of stream)chunks.push(chunk);
  const research=JSON.parse(Buffer.concat(chunks).toString());
  assert.equal(download.suggestedFilename(),'profili-produttori.json');assert(research.total>0);assert.equal(research.manufacturers.length,research.total);
  await page.getByRole('button',{name:'Completa profili documentati',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Profili aggiornati:'}).waitFor();
  await page.getByRole('button',{name:'Nuovo produttore',exact:true}).click();
  for(const [label,value] of [['Nome del produttore',name],['Paese','Italia'],['Data di fondazione','1980'],['Data di cessazione','1995-06'],['Denominazione storica','Synthetic Company S.p.A.'],['Sede storica','Ivrea'],['Fondatori','Persona sintetica'],['Profilo storico in italiano','Storia sintetica italiana del produttore.\nSecondo paragrafo.'],['Attribuzione del testo','Autore testo sintetico'],['Fonte del testo','https://example.org/company-history'],['Licenza del testo','https://example.org/text-terms'],['URL del logo','https://example.org/synthetic-company-logo.svg'],['Autore del logo','Autore sintetico'],['Licenza o condizioni del logo','Condizioni sintetiche'],['Fonte del logo','https://example.org/logo-source']])await page.getByLabel(label,{exact:true}).fill(value);
  await page.getByLabel('Cerca una fonte aziendale',{exact:true}).fill(source.title);
  await page.getByRole('checkbox',{name:source.title,exact:true}).check();
  await page.getByRole('button',{name:'Salva produttore',exact:true}).click();await page.getByRole('status').filter({hasText:'Produttore salvato.'}).waitFor();
  maker=(await(await page.request.get(api('/manufacturers'))).json()).find(m=>m.name===name);
  assert(maker);assert.equal(maker.founded,'1980');assert.equal(maker.ceased,'1995-06');assert.equal(maker.sources[0].id,source.id);
  const meta=await(await page.request.get(api('/meta'))).json();
  for(const [computerName,year,description] of [[model+'A','1981',shortDescription],[model+'B','1988',longDescription],[model+'C','1990',null],[longName,'1998','Descrizione con un nome del modello particolarmente lungo.']])ids.push((await post('/computers',{manufacturer_id:maker.id,model_name:computerName,description,releases:[{market_id:meta.markets[0].id,release_date:year}]})).id);
  await post('/computers/'+ids[0]+'/images',{image_url:'https://example.org/synthetic-computer-cover.svg'});
  await page.getByRole('button',{name:'Esplora produttori',exact:true}).click();
  const search=page.getByRole('textbox',{name:'Cerca un produttore',exact:true});await search.fill(name);
  await page.getByRole('combobox',{name:'Paese del produttore'}).selectOption('Italia');
  await page.getByRole('combobox',{name:'Ordina produttori'}).selectOption('count');
  await page.getByRole('button',{name:'Esplora '+name,exact:true}).click();
  await page.getByRole('heading',{name,level:1,exact:true}).waitFor({timeout:10000});
  assert.match(await page.locator('main').innerText(),/4 sistemi nell’archivio · 1981–1998/);
  await checkComputerCards();
  assert(await page.getByRole('img',{name:'Fotografia di '+model+'A',exact:true}).isVisible());
  assert.match(await page.getByRole('region',{name:'Profilo dell’azienda'}).innerText(),/Storia sintetica italiana/);
  assert(await page.getByRole('region',{name:'Profilo dell’azienda'}).getByRole('link',{name:'Autore testo sintetico',exact:true}).isVisible());
  assert(await page.getByRole('link',{name:'Licenza del testo',exact:true}).isVisible());
  assert(await page.getByRole('img',{name:'Logo di '+name,exact:true}).isVisible());
  if(process.env.HHE_MANUFACTURER_SCREENSHOT)await page.screenshot({path:process.env.HHE_MANUFACTURER_SCREENSHOT,fullPage:true});
  assert(await page.getByRole('region',{name:'Fonti del produttore'}).getByRole('link',{name:new RegExp(source.title)}).isVisible());
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'A',exact:true})}).getByRole('button',{name:'Dettagli',exact:true}).click();
  await page.getByRole('heading',{name:model+'A',level:1,exact:true}).waitFor();await page.getByRole('button',{name,exact:true}).click();
  await page.getByRole('heading',{name,level:1,exact:true}).waitFor({timeout:10000});
  for(const mode of ['Tema: Chiaro','Tema: Fosfori verdi']){
   await page.getByRole('button',{name:mode,exact:true}).click();
   for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:950});await checkComputerCards();}
  }
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'B',exact:true})}).getByRole('button',{name:'Dettagli',exact:true}).click();
  await page.getByRole('heading',{name:model+'B',level:1,exact:true}).waitFor();
  assert(await page.getByText(longDescription,{exact:true}).isVisible());
  await page.getByRole('button',{name,exact:true}).click();
  await page.getByRole('heading',{name,level:1,exact:true}).waitFor();
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Tutti i produttori',exact:true}).click();
  await page.getByRole('textbox',{name:'Cerca un produttore'}).fill('nonexistent-company-'+suffix);
  await page.getByText('Nessun produttore corrisponde alla ricerca.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Catalogo',exact:true}).click();await page.getByPlaceholder('Cerca un sistema…',{exact:true}).fill(model);
  for(const mode of ['Tema: Chiaro','Tema: Fosfori verdi']){
   await page.getByRole('button',{name:mode,exact:true}).click();
   for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:950});await checkComputerCards();}
  }
  const compare=page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'A',exact:true})}).getByRole('button',{name:'+ Confronta',exact:true});
  await compare.click();
  assert.equal(await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'A',exact:true})}).getByRole('button',{name:'✓',exact:true}).getAttribute('aria-pressed'),'true');
  await page.locator('.catalog-card').filter({has:page.getByRole('heading',{name:model+'A',exact:true})}).getByRole('button',{name,exact:true}).click();
  await page.getByRole('heading',{name,level:1,exact:true}).waitFor({timeout:10000});
  const changed=await page.request.put(api('/manufacturers/'+maker.id),{data:{name,logo_url:'https://example.org/missing-company-logo.png'}});
  assert.equal(changed.status(),200);
  await page.route('https://example.org/missing-company-logo.png',route=>route.abort());
  await page.getByRole('button',{name:'Tutti i produttori',exact:true}).click();
  await page.getByRole('textbox',{name:'Cerca un produttore'}).fill(name);
  await page.getByRole('button',{name:'Esplora '+name,exact:true}).click();
  await page.getByLabel('Produttore '+name,{exact:true}).waitFor();
  assert.deepEqual(errors,[]);console.log('PASS manufacturers: profiles/citations/logo, shared compact system previews, short/long/missing descriptions, uniform heights and footers, full detail text, catalog comparison, light/dark at 320/390/768/1440 px; no JS errors.');
 }catch(error){console.error('Rendered page:',await page.locator('main').innerText().catch(()=>''));throw error;}finally{
  for(const id of ids)await page.request.delete(api('/computers/'+id)).catch(()=>{});
  if(maker)await page.request.delete(api('/manufacturers/'+maker.id)).catch(()=>{});
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
