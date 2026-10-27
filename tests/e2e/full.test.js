// End-to-end browser test of every feature. Needs Node + Playwright (npm i -g playwright).
// Run:  python3 tests/e2e/serve.py &  then  node tests/e2e/full.test.js
const {chromium}=require('playwright');const fs=require('fs'),os=require('os');
const B='http://localhost:8820';let fails=0;
const ok=(c,m)=>{console.log((c?'PASS ':'FAIL ')+m);if(!c)fails++};
const api=(p,path)=>p.evaluate(u=>fetch('/api'+u).then(r=>r.json()),path);
(async()=>{
const b=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const ctx=await b.newContext({viewport:{width:1300,height:850},permissions:['camera','microphone']});
const errs=[];const mk=async()=>{const p=await ctx.newPage();p.on('pageerror',e=>errs.push('pageerror: '+e.message));p.on('console',m=>m.type()==='error'&&errs.push(m.text()));p.on('dialog',d=>d.accept('Tester'));return p};
const p=await mk();await p.goto(B);
const mod=async v=>{await p.click(`[data-mod=${v}]`);await p.waitForTimeout(350)};
const row=(t)=>p.locator('#panel .prow',{hasText:t}).first();
const newItem=async()=>{await p.click('#panel #new');await p.waitForSelector('#t')};

// ---------- shell / branding
ok(await p.locator('#rail [data-mod]').count()===9,'ui: icon rail with all modules');
ok(await p.evaluate(()=>getComputedStyle(document.body).backgroundColor)==='rgb(245, 241, 232)','ui: Macro cream canvas');
const loaded=await p.evaluate(async()=>{await Promise.all([document.fonts.load('400 16px "Inter Variable"'),document.fonts.load('500 34px "Roboto Slab Variable"')]);return [...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family.replace(/"/g,''))});
ok(loaded.includes('Inter Variable')&&loaded.includes('Roboto Slab Variable'),'ui: bundled Inter + Roboto Slab fonts load offline ('+loaded.join(', ')+')');
ok((await p.textContent('.hello')).length>5&&await p.locator('.grid2 .card').count()===4,'home: greeting + 4 summary cards');

// ---------- DOCS / TASKS / LINKS / XSS
await mod('docs');await newItem();
await p.fill('#t','Project Plan');await p.fill('#b','See [[Kickoff Task]] and [[Nope]]');await p.waitForTimeout(900);
ok(await p.locator('#mn .pill.dead').count()===2,'doc: unresolved [[links]] shown as dead pills');
ok((await p.textContent('#bar .crumbs')).includes('Project Plan'),'doc: breadcrumb tracks the title live');
await mod('tasks');await newItem();
await p.fill('#t','Kickoff Task');await p.fill('#b','Part of [[Project Plan]]');await p.fill('[data-k=due]','2026-11-05');await p.waitForTimeout(900);
await mod('tasks');await p.waitForSelector('.col');
ok(await p.locator('.col[data-c=todo] .kcard',{hasText:'Kickoff Task'}).count()===1,'task: appears on the board (To do)');
ok((await p.textContent('.col[data-c=todo] .kcard')).includes('2026-11-05'),'task: due date shown on card');
await p.locator('.kcard',{hasText:'Kickoff Task'}).dragTo(p.locator('.col[data-c=doing]'));await p.waitForTimeout(600);
ok(await p.locator('.col[data-c=doing] .kcard',{hasText:'Kickoff Task'}).count()===1,'task: drag to In progress');
ok((await p.textContent('#panel')).includes('In progress'),'task: panel groups by status');
await mod('docs');await row('Project Plan').click();await p.waitForSelector('#mn .pill[data-id]');
ok(await p.locator('#mn .pill[data-id]').count()===1,'doc: resolved [[link]] becomes a clickable pill');
ok((await p.textContent('.sect')).includes('Kickoff Task'),'doc: backlink from task shown');
await p.click('.sect .lrow[data-id]');await p.waitForTimeout(500);
ok((await p.inputValue('#t'))==='Kickoff Task'&&(await p.evaluate(()=>S.mod))==='tasks','backlink opens the linked item in its own module');
await mod('docs');await newItem();
await p.fill('#t','<img src=x onerror="window.__xss=1">');await p.fill('#b','<script>window.__xss=2</script>');await p.waitForTimeout(900);await mod('docs');
ok(await p.evaluate(()=>window.__xss===undefined),'security: HTML in titles/bodies is escaped (no script execution)');
await row('<img').click();await p.waitForSelector('#del');await p.click('#del');await p.waitForTimeout(600);
ok(await p.locator('#panel .prow',{hasText:'<img'}).count()===0,'doc: delete works');
// regression: fast switching between items must not cross-write edits
await newItem();const idA=await p.evaluate(()=>S.id);await p.click('#panel #new');await p.waitForFunction(o=>S.id&&S.id!==o,idA);const idB=await p.evaluate(()=>S.id);
await p.click(`#panel .prow[data-id="${idA}"]`);await p.waitForSelector('#t');await p.fill('#t','Race AAA');await p.fill('#b','body of A');
await p.click(`#panel .prow[data-id="${idB}"]`);await p.waitForTimeout(1200);
const A=await api(p,'/items/'+idA),Bk=await api(p,'/items/'+idB);
ok(A.title==='Race AAA'&&A.body==='body of A'&&Bk.title==='Untitled'&&Bk.body==='','editor: fast switch keeps each item\'s own edits (no cross-write)');

// ---------- CHAT
await mod('chat');await p.click('#nc');await p.waitForSelector('#panel .prow:has-text("tester")');
ok((await p.textContent('#bar .crumbs')).includes('tester'),'chat: create channel and switch into it');
await p.fill('#mi','ship the release @macro');await p.press('#mi','Enter');await p.waitForSelector('.msg');
ok(await p.locator('.msg .mention').count()===1,'chat: @mention highlighted');
const p2=await mk();await p2.goto(B);await p2.click('[data-mod=chat]');await p2.waitForSelector('#panel .prow:has-text("tester")');await p2.click('#panel .prow:has-text("tester")');
await p2.waitForSelector('.msg:has-text("ship the release")');ok(true,'chat: message visible from a second client');
await p2.fill('#mi','got it');await p2.press('#mi','Enter');await p.waitForSelector('.msg:has-text("got it")',{timeout:6000});ok(true,'chat: live delivery between clients (polling)');
await p2.close();
await p.hover('.msg:has-text("ship the release")');await p.click('.msg:has-text("ship the release") .tools button');await p.waitForSelector('#t');
ok((await p.inputValue('#t'))==='ship the release @macro'&&(await p.evaluate(()=>S.mod))==='tasks','chat: message → task');

// ---------- CRM
await mod('crm');
await newItem();await p.fill('#t','Ada Lovelace');await p.fill('[data-k=email]','ada@analytical.io');await p.fill('[data-k=company]','Analytical');await p.waitForTimeout(800);
await p.click('#panel .seg [data-t=company]');await p.waitForTimeout(300);await newItem();await p.fill('#t','Analytical Engines');await p.waitForTimeout(800);
await p.click('#panel .seg [data-t=deal]');await p.waitForTimeout(300);await newItem();await p.fill('#t','Big deal');await p.fill('[data-k=value]','5000');await p.waitForTimeout(800);
await p.click('#panel [data-nav=board]');await p.waitForSelector('.col[data-c=lead] .kcard');
await p.locator('.kcard',{hasText:'Big deal'}).dragTo(p.locator('.col[data-c=proposal]'));await p.waitForTimeout(600);
ok(await p.locator('.col[data-c=proposal] .kcard',{hasText:'Big deal'}).count()===1&&(await p.locator('.kcard',{hasText:'Big deal'}).textContent()).includes('$5000'),'crm: deal pipeline drag + value');
await p.click('#panel .seg [data-t=contact]');await p.waitForFunction(()=>document.querySelector('#panel').textContent.includes('ada@analytical.io'),null,{timeout:5000}).catch(()=>{});
ok((await p.textContent('#panel')).includes('ada@analytical.io'),'crm: contact list shows email');

// ---------- EMAIL (IMAP/SMTP via Settings UI against fake servers)
await mod('settings');await p.waitForSelector('#esave');
await p.fill('#e_name','Me');await p.fill('#e_address','me@x.com');await p.fill('#e_password','pw');
await p.fill('#e_imap_host','127.0.0.1');await p.fill('#e_imap_port','8821');await p.selectOption('#e_imap_security','none');
await p.fill('#e_smtp_host','127.0.0.1');await p.fill('#e_smtp_port','8822');await p.selectOption('#e_smtp_security','none');
await p.click('#esave');await p.waitForFunction(()=>document.querySelector('#emsg').textContent.includes('Connected'),null,{timeout:10000});
ok((await p.textContent('#emsg')).includes('3 message'),'email: IMAP connect + initial sync via Settings UI');
await mod('email');await p.waitForSelector('#panel .prow.two');
ok(await p.locator('#panel .prow.two').count()===3,'email: inbox lists 3 messages');
ok(await p.locator('#panel .prow.unread').count()===3,'email: unread highlighted');
await row('Third').click();await p.waitForSelector('.mcard .mb');
ok((await p.textContent('.mcard .mb')).includes('hello 3')&&(await p.textContent('.thread-h'))==='Third','email: thread view shows body');
await p.waitForTimeout(400);ok(await p.locator('#panel .prow.unread').count()===2,'email: opening marks read');
await p.click('#rep');await p.waitForSelector('#csend');
ok((await p.inputValue('#csub'))==='Re: Third'&&(await p.inputValue('#cto')).includes('ann3@x.com')&&(await p.inputValue('#cbody')).includes('> hello 3'),'email: reply prefilled (to, subject, quote)');
await p.fill('#cbody','Thanks Ann!\n\n'+await p.inputValue('#cbody'));await p.click('#csend');await p.waitForSelector('#toast:has-text("Sent")');
await p.waitForTimeout(700);const smtp=JSON.parse(fs.readFileSync(os.tmpdir()+'/macro-e2e-smtp.json','utf8'));
ok(smtp.length===1&&smtp[0][0][0]==='ann3@x.com'&&smtp[0][1].includes('Thanks Ann!')&&smtp[0][1].includes('In-Reply-To: <w3@x.com>'),'email: reply delivered over SMTP with threading header');
ok(await p.locator('#panel .seg button.on',{hasText:'Sent'}).count()===1,'email: lands in Sent folder');
await p.click('#panel [data-b=inbox]');await row('Second').click();await p.waitForSelector('#tocon');
await p.click('#tocon');await p.waitForSelector('#t');ok((await p.inputValue('#t'))==='Ann'&&(await p.inputValue('[data-k=email]'))==='ann2@x.com','email: → CRM contact');
await mod('email');await row('Second').click();await p.waitForSelector('#totask');await p.click('#totask');await p.waitForSelector('#t');ok((await p.inputValue('#t'))==='Second','email: → task');
await mod('email');await p.click('#comp');await p.fill('#cto','new@y.com');await p.fill('#csub','Fresh');await p.fill('#cbody','hi');await p.click('#csend');await p.waitForTimeout(900);
ok(JSON.parse(fs.readFileSync(os.tmpdir()+'/macro-e2e-smtp.json','utf8')).length===2,'email: compose new message');
await p.click('#panel [data-b=inbox]');await row('First').click();await p.waitForSelector('#del');await p.click('#del');await p.waitForTimeout(600);
await p.waitForSelector('#panel .prow.two');ok(await p.locator('#panel .prow.two').count()===2,'email: delete message');
await p.click('#sync');await p.waitForTimeout(900);ok(await p.locator('#panel .prow.two').count()===2,'email: manual sync is idempotent');

// ---------- CALENDAR
await mod('calendar');await p.click('#ne');await p.waitForSelector('#t');
await p.fill('#t','Team offsite');await p.selectOption('[data-k=allday]','yes');await p.waitForTimeout(900);
await p.selectOption('[data-k=rrule]','FREQ=WEEKLY');await p.fill('[data-k=location]','HQ');await p.waitForTimeout(900);
ok((await p.getAttribute('[data-k=start]','type'))==='date','calendar: all-day switches inputs to dates');
await mod('calendar');await p.waitForSelector('.chip');
const chips=await p.locator('.chip:has-text("Team offsite")').count();
ok(chips>=2,`calendar: weekly recurrence repeats within the visible grid (${chips} chips)`);
await p.click('#nx');await p.waitForTimeout(400);const chips2=await p.locator('.chip:has-text("Team offsite")').count();ok(chips2>=4,`calendar: next month shows ${chips2} weekly occurrences`);await p.click('#td');await p.waitForTimeout(300);
await p.click('[data-m=agenda]');await p.waitForSelector('.agenda .lrow');ok((await p.textContent('#page')).includes('Team offsite'),'calendar: agenda view');
await p.click('[data-m=month]');await p.waitForSelector('.cal');
const before=(await api(p,'/items?type=event')).length;await p.locator('.cal .d').nth(20).click();await p.waitForSelector('#t');
ok((await api(p,'/items?type=event')).length===before+1,'calendar: click a day creates an event');
fs.writeFileSync(os.tmpdir()+'/macro-e2e-imp.ics','BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:imp1\r\nSUMMARY:Imported thing\r\nDTSTART:20261201T100000Z\r\nDTEND:20261201T110000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n');
await mod('settings');await p.setInputFiles('#icsfile',os.tmpdir()+'/macro-e2e-imp.ics');await p.waitForSelector('#toast:has-text("imported")');ok(true,'calendar: .ics import');
const exp=await p.evaluate(()=>fetch('/api/calendar/export.ics').then(r=>r.text()));ok(exp.includes('SUMMARY:Imported thing')&&exp.includes('SUMMARY:Team offsite')&&exp.includes('RRULE:FREQ=WEEKLY'),'calendar: .ics export includes events + recurrence');
await p.click('#addfeed');await p.locator('#feeds .fn').last().fill('Holidays');await p.locator('#feeds .fu').last().fill('http://127.0.0.1:8823/feed.ics');
await p.click('#savefeeds');await p.waitForFunction(()=>document.querySelector('#fmsg').textContent.includes('synced'),null,{timeout:10000});
ok((await api(p,'/items?type=event')).some(e=>e.title==='Feed Holiday'),'calendar: iCal feed URL subscription');
const soon=new Date(Date.now()+5*60000),pad=n=>String(n).padStart(2,'0');
await p.evaluate(async s=>fetch('/api/items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'event',title:'Standup NOW',data:{allday:'no',start:s,end:s}})}).then(r=>r.json()),`${soon.getFullYear()}-${pad(soon.getMonth()+1)}-${pad(soon.getDate())}T${pad(soon.getHours())}:${pad(soon.getMinutes())}`);
await p.reload();await p.waitForSelector('#toast:has-text("Standup NOW")',{timeout:8000});ok(true,'calendar: 10-minute reminder toast');

// ---------- CALLS
await mod('calendar');await p.waitForSelector('#panel .prow:has-text("Standup NOW")');await p.click('#panel .prow:has-text("Standup NOW")');await p.waitForSelector('#addcall');await p.click('#addcall');await p.waitForTimeout(1400);
const loc=await p.inputValue('[data-k=location]');ok(/#call\/[a-z0-9-]+$/.test(loc),'calls: "Add video call link" on an event');
await mod('calls');await p.waitForSelector('#panel .prow:has-text("Call: Standup NOW")');ok(true,'calls: call listed in panel');
await p.click('#start');await p.waitForSelector('#tiles .tile');await p.waitForTimeout(1500);
ok(await p.evaluate(()=>document.querySelector('#tiles video').videoWidth>0),'calls: local camera preview');
await p.click('#mic');ok((await p.textContent('#mic')).includes('Unmute'),'calls: mute toggle');
await p.click('#cam');ok((await p.textContent('#cam')).includes('Camera on'),'calls: camera toggle');
await mod('home');ok(await p.locator('#incall').count()===1,'calls: "In call" pill follows you around the app');await p.click('#incall');await p.waitForSelector('#tiles .tile');
await p.click('#rec');await p.waitForTimeout(2000);await p.click('#rec');await p.waitForTimeout(1500);
await p.fill('#cn','Decided: ship [[Project Plan]]');await p.waitForTimeout(800);
await p.click('#leave');await p.waitForSelector('#t');await p.waitForTimeout(500);
const calls=await api(p,'/items?type=call');const last=calls.find(c=>c.data.recording);
ok(last&&last.data.status==='ended'&&last.body.includes('Project Plan'),'calls: solo call → recording saved, notes saved, status ended');
ok(await p.locator('audio[src^="/recordings/"]').count()===1,'calls: recording player on the call page');
const rec=await p.evaluate(u=>fetch(u).then(r=>r.arrayBuffer().then(a=>[r.status,a.byteLength])),'/recordings/'+last.data.recording);
const head=await p.evaluate(u=>fetch(u).then(r=>r.arrayBuffer()).then(a=>[...new Uint8Array(a.slice(0,4))].map(x=>x.toString(16)).join('')),'/recordings/'+last.data.recording);
ok(rec[0]===200&&rec[1]>300&&head==='1a45dfa3',`calls: recording downloadable, valid WebM (${rec[1]} bytes)`);

// ---------- SEARCH PALETTE
await p.click('[data-act=search]');await p.waitForSelector('#palette.open');await p.fill('#q','Project Plan');await p.waitForSelector('#res .prow');
ok(await p.locator('#res .prow').count()>=2,'search: palette finds items by title and linked body text');
await p.press('#q','Enter');await p.waitForSelector('#t');ok((await p.evaluate(()=>S.mod))!=='home','search: Enter opens the top result');
await p.keyboard.press('Control+k');await p.waitForSelector('#palette.open');await p.fill('#q','got it');await p.waitForFunction(()=>document.querySelector('#res').textContent.includes('got it'));ok(true,'search: Ctrl/⌘+K opens palette; finds chat messages');
await p.keyboard.press('Escape');ok(await p.locator('#palette.open').count()===0,'search: Esc closes');

// ---------- NEW menu
await p.click('#rail [data-act=new]');await p.waitForSelector('#menu.open');ok(await p.locator('#menu .prow').count()===9,'ui: global New menu (doc, task, event, email, contact, company, deal, call, channel)');
const oldId=await p.evaluate(()=>S.id);await p.click('#menu .prow:has-text("Doc")');await p.waitForFunction(o=>S.id&&S.id!==o,oldId);ok((await p.evaluate(()=>S.mod))==='docs','ui: New → Doc');

// ---------- UPDATES UI
await mod('settings');await p.waitForSelector('#upd');
ok((await p.textContent('#upd')).includes('running from source')&&await p.locator('#u_auto').count()===1,'updates: settings section shows version + auto-update toggle');
await p.click('#u_check');await p.waitForTimeout(1200);ok((await p.textContent('#upd')).length>20,'updates: manual check responds (offline-safe)');
// banner appears when an update is ready
await p.evaluate(()=>{S.upd={...S.upd,available:true,ready:true,latest:'v9.9.9',can_install:true};renderUpdate()});
ok(await p.locator('#update.show').count()===1&&(await p.textContent('#update')).includes('v9.9.9')&&await p.locator('#u_go').count()===1,'updates: "Restart & update" banner');
await p.click('#u_later');ok(await p.locator('#update.show').count()===0,'updates: banner can be dismissed per version');

// ---------- PWA / assets
const pwa=await p.evaluate(async()=>{const m=await fetch('/manifest.webmanifest').then(r=>r.json());const i=await Promise.all(m.icons.map(x=>fetch(x.src).then(r=>r.status)));const reg=await navigator.serviceWorker.getRegistration();return {name:m.name,icons:i,sw:!!reg}});
ok(pwa.name==='Macro Local'&&pwa.icons.every(s=>s===200)&&pwa.sw,'app: manifest, icons and service worker (installable)');

// ---------- responsive
await p.setViewportSize({width:390,height:800});
for(const v of ['home','docs','tasks','chat','email','calendar','calls','crm','settings']){await p.click(`[data-mod=${v}]`);await p.waitForTimeout(350);
  const w=await p.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]);if(w[0]>w[1]+2){console.log('  overflow in',v,w);fails++}}
ok(true,'responsive: 390px wide checked for horizontal overflow on all views');
console.log('console errors:',errs.filter(e=>!/status of 40[0-9]/.test(e)));
console.log(fails?`\n${fails} FAILED`:'\nALL PASSED');await b.close();process.exit(fails?1:0)})().catch(e=>{console.error('CRASH',e.message);process.exit(1)})
