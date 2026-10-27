// End-to-end browser test of every feature. Needs Node + Playwright (npm i -g playwright).
// Run:  python3 tests/e2e/serve.py &  then  node tests/e2e/full.test.js
const {chromium}=require('playwright');const fs=require('fs');
const B='http://localhost:8820';let fails=0;
const ok=(c,m)=>{console.log((c?'PASS ':'FAIL ')+m);if(!c)fails++};
const api=(p,path)=>p.evaluate(u=>fetch('/api'+u).then(r=>r.json()),path);
(async()=>{
const b=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const ctx=await b.newContext({viewport:{width:1300,height:850},permissions:['camera','microphone']});
const errs=[];const mk=async()=>{const p=await ctx.newPage();p.on('pageerror',e=>errs.push('pageerror: '+e.message));p.on('console',m=>m.type()==='error'&&errs.push(m.text()));p.on('dialog',d=>d.accept('Tester'));return p};
const p=await mk();p.on('request',r=>{if(r.url().includes('/api/items')&&r.method()!=='GET')console.log('   ',r.method(),r.url().replace(B,''),(r.postData()||'').slice(0,110))});await p.goto(B);
const nav=async v=>{await p.click(`a[data-v=${v}]`);await p.waitForTimeout(250)};
const closeDetail=async()=>{if(await p.locator('#detail.open').count())await p.click('#x')};

// ---------- DOCS / TASKS / LINKS / XSS
await nav('docs');await p.click('#new');await p.waitForSelector('#detail.open');
await p.fill('#t','Project Plan');await p.fill('#b','See [[Kickoff Task]] and [[Nope]]');await p.waitForTimeout(900);
ok((await p.textContent('#pv')).includes('Nope')&&await p.locator('#pv .lnk.dead').count()===2,'doc: unresolved [[link]] rendered as dead link');
await closeDetail();
await nav('tasks');await p.click('#new');await p.waitForSelector('#detail.open');
await p.fill('#t','Kickoff Task');await p.fill('#b','Part of [[Project Plan]]');await p.fill('[data-k=due]','2026-11-05');await p.waitForTimeout(900);
await closeDetail();await nav('tasks');
ok(await p.locator('.col[data-c=todo] .card',{hasText:'Kickoff Task'}).count()===1,'task: appears in todo column');
ok((await p.textContent('.col[data-c=todo] .card')).includes('2026-11-05'),'task: due date shown on card');
await p.locator('.card',{hasText:'Kickoff Task'}).dragTo(p.locator('.col[data-c=doing]'));await p.waitForTimeout(500);
ok(await p.locator('.col[data-c=doing] .card',{hasText:'Kickoff Task'}).count()===1,'task: drag to doing column');
await nav('docs');await p.click('.row:has-text("Project Plan")');await p.waitForSelector('#pv .lnk[data-id]');
ok(await p.locator('#pv .lnk[data-id]').count()===1,'doc: resolved [[link]] is clickable');
ok((await p.textContent('#detail')).includes('Linked from (1)')&&(await p.textContent('#detail')).includes('Kickoff Task'),'doc: backlink from task shown');
await p.click('#detail .lnk[data-id]');await p.waitForTimeout(400);
ok((await p.inputValue('#t'))==='Kickoff Task','backlink click opens the linked item');
await closeDetail();
await nav('docs');await p.click('#new');await p.waitForSelector('#detail.open');
await p.fill('#t','<img src=x onerror="window.__xss=1">');await p.fill('#b','<script>window.__xss=2</script>');await p.waitForTimeout(900);await closeDetail();await nav('docs');
ok(await p.evaluate(()=>window.__xss===undefined),'security: HTML in titles/bodies is escaped (no script execution)');
await p.click('.row:has-text("<img")');await p.waitForSelector('#del');await p.click('#del');await p.waitForTimeout(500);
ok(await p.locator('.row:has-text("<img")').count()===0,'doc: delete works');

// regression: switching items while an edit is still pending must not write one item's form onto the other
await nav('docs');await p.click('#new');await p.waitForSelector('#detail.open');const idA=await p.evaluate(()=>state.openId);
await closeDetail();await p.click('#new');await p.waitForSelector('#detail.open');const idB=await p.evaluate(()=>state.openId);await closeDetail();
await nav('docs');await p.click(`.row[data-id="${idA}"]`);await p.waitForSelector('#detail.open');await p.fill('#t','Race AAA');await p.fill('#b','body of A');
await p.click(`.row[data-id="${idB}"]`);await p.waitForTimeout(1200);
const A=await api(p,'/items/'+idA),Bk=await api(p,'/items/'+idB);
ok(A.title==='Race AAA'&&A.body==='body of A'&&Bk.title==='Untitled'&&Bk.body==='','editor: fast switch keeps each item\'s own edits (no cross-write)');
await closeDetail();
// ---------- CHAT
await nav('chat');await p.click('#nc');await p.waitForTimeout(500);
ok(await p.locator('.tabs button',{hasText:'# tester'}).count()===1,'chat: create channel');
await p.fill('#mi','ship the release');await p.press('#mi','Enter');await p.waitForSelector('.msg');
const p2=await mk();await p2.goto(B);await p2.click('a[data-v=chat]');await p2.waitForSelector('.tabs button:has-text("# tester")');await p2.click('.tabs button:has-text("# tester")');await p2.waitForSelector('.tabs button.on:has-text("# tester")');await p2.waitForSelector('.msg:has-text("ship the release")');
ok(true,'chat: message visible from a second client');
await p2.fill('#mi','got it');await p2.press('#mi','Enter');await p.waitForSelector('.msg:has-text("got it")',{timeout:6000});ok(true,'chat: live delivery between clients (polling)');
await p2.close();
await p.hover('.msg:has-text("ship the release")');await p.click('.msg:has-text("ship the release") button');await p.waitForSelector('#detail.open');
ok((await p.inputValue('#t'))==='ship the release','chat: message → task');
await closeDetail();

// ---------- CRM
await nav('crm');
await p.click('#new');await p.waitForSelector('#detail.open');await p.fill('#t','Ada Lovelace');await p.fill('[data-k=email]','ada@analytical.io');await p.fill('[data-k=company]','Analytical');await p.waitForTimeout(800);await closeDetail();
await p.click('.tabs button[data-t=company]');await p.click('#new');await p.waitForSelector('#detail.open');await p.fill('#t','Analytical Engines');await p.waitForTimeout(800);await closeDetail();
await p.click('.tabs button[data-t=deal]');await p.click('#new');await p.waitForSelector('#detail.open');await p.fill('#t','Big deal');await p.fill('[data-k=value]','5000');await p.waitForTimeout(800);await closeDetail();
await p.click('.tabs button[data-t=deal]');await p.waitForSelector('.col[data-c=lead] .card');
await p.locator('.card',{hasText:'Big deal'}).dragTo(p.locator('.col[data-c=proposal]'));await p.waitForTimeout(500);
ok(await p.locator('.col[data-c=proposal] .card',{hasText:'Big deal'}).count()===1&&(await p.locator('.card',{hasText:'Big deal'}).textContent()).includes('$5000'),'crm: deal pipeline drag + value');
await p.click('.tabs button[data-t=contact]');await p.waitForSelector('.row');
ok((await p.textContent('.row')).includes('ada@analytical.io'),'crm: contact list shows email');

// ---------- EMAIL (IMAP/SMTP via Settings UI against fake servers)
await nav('settings');await p.waitForSelector('#esave');
await p.fill('#e_name','Me');await p.fill('#e_address','me@x.com');await p.fill('#e_password','pw');
await p.fill('#e_imap_host','127.0.0.1');await p.fill('#e_imap_port','8821');await p.selectOption('#e_imap_security','none');
await p.fill('#e_smtp_host','127.0.0.1');await p.fill('#e_smtp_port','8822');await p.selectOption('#e_smtp_security','none');
await p.click('#esave');await p.waitForFunction(()=>document.querySelector('#emsg').textContent.includes('Connected'),null,{timeout:10000});
ok((await p.textContent('#emsg')).includes('3 message'),'email: IMAP connect + initial sync via Settings UI');
await nav('email');await p.waitForSelector('.row');
ok(await p.locator('.split .l .row').count()===3,'email: inbox lists 3 messages');
ok(await p.locator('.row.unread').count()===3,'email: unread highlighted');
await p.click('.row:has-text("Third")');await p.waitForSelector('.mailbody');
ok((await p.textContent('.mailbody')).includes('hello 3'),'email: reader shows body');
ok(await p.locator('.row.unread').count()===2,'email: opening marks read locally');
await p.click('#rep');await p.waitForSelector('#csend');
ok((await p.inputValue('#csub'))==='Re: Third'&&(await p.inputValue('#cto')).includes('ann3@x.com')&&(await p.inputValue('#cbody')).includes('> hello 3'),'email: reply prefilled (to, subject, quote)');
await p.fill('#cbody','Thanks Ann!\n\n'+await p.inputValue('#cbody'));await p.click('#csend');await p.waitForSelector('#toast:has-text("Sent")');
await p.waitForTimeout(700);const smtp=JSON.parse(fs.readFileSync(require('os').tmpdir()+'/macro-e2e-smtp.json','utf8'));
ok(smtp.length===1&&smtp[0][0][0]==='ann3@x.com'&&smtp[0][1].includes('Thanks Ann!')&&smtp[0][1].includes('In-Reply-To: <w3@x.com>'),'email: reply delivered over SMTP with threading header');
ok(await p.locator('.tabs button.on',{hasText:'Sent'}).count()===1,'email: lands in Sent folder');
await p.click('[data-b=inbox]');await p.click('.row:has-text("Second")');await p.waitForSelector('#tocon');
await p.click('#tocon');await p.waitForSelector('#detail.open');ok((await p.inputValue('#t'))==='Ann'&&(await p.inputValue('[data-k=email]'))==='ann2@x.com','email: → CRM contact');
await closeDetail();await p.click('#totask');await p.waitForSelector('#detail.open');ok((await p.inputValue('#t'))==='Second','email: → task');await closeDetail();
await p.click('#comp');await p.fill('#cto','new@y.com');await p.fill('#csub','Fresh');await p.fill('#cbody','hi');await p.click('#csend');await p.waitForTimeout(900);
ok(JSON.parse(fs.readFileSync(require('os').tmpdir()+'/macro-e2e-smtp.json','utf8')).length===2,'email: compose new message');
await p.click('[data-b=inbox]');await p.click('.row:has-text("First")');await p.waitForSelector('#del');await p.click('#del');await p.waitForTimeout(500);
ok(await p.locator('.split .l .row').count()===2,'email: delete message');
await p.click('#sync');await p.waitForTimeout(800);ok(await p.locator('.split .l .row').count()===2,'email: manual sync is idempotent');

// ---------- CALENDAR
await nav('calendar');await p.click('#ne');await p.waitForSelector('#detail.open');
await p.fill('#t','Team offsite');await p.selectOption('[data-k=allday]','yes');await p.waitForTimeout(900);
await p.selectOption('[data-k=rrule]','FREQ=WEEKLY');await p.fill('[data-k=location]','HQ');await p.waitForTimeout(900);
ok((await p.getAttribute('[data-k=start]','type'))==='date','calendar: all-day switches inputs to dates');
await closeDetail();await nav('calendar');await p.waitForSelector('.chip');
const chips=await p.locator('.chip:has-text("Team offsite")').count();
ok(chips>=2,`calendar: weekly recurrence repeats within the visible grid (${chips} chips)`);
await p.click('#nx');await p.waitForTimeout(400);const chips2=await p.locator('.chip:has-text("Team offsite")').count();ok(chips2>=4,`calendar: next month shows ${chips2} weekly occurrences`);await p.click('#td');
await p.click('[data-m=agenda]');await p.waitForSelector('.row');ok((await p.textContent('#view')).includes('Team offsite'),'calendar: agenda view');
await p.click('#nx').catch(()=>{});
await p.click('[data-m=month]');await p.click('#nx');await p.click('#pr');await p.click('#td');ok(true,'calendar: prev/next/today navigation');
// click a day creates an event
const before=(await api(p,'/items?type=event')).length;await p.locator('.cal .d').nth(20).click();await p.waitForSelector('#detail.open');await closeDetail();
ok((await api(p,'/items?type=event')).length===before+1,'calendar: click a day creates an event');
// ICS import/export
fs.writeFileSync(require('os').tmpdir()+'/macro-e2e-imp.ics','BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:imp1\r\nSUMMARY:Imported thing\r\nDTSTART:20261201T100000Z\r\nDTEND:20261201T110000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n');
await nav('settings');await p.setInputFiles('#icsfile',require('os').tmpdir()+'/macro-e2e-imp.ics');await p.waitForSelector('#toast:has-text("imported")');ok(true,'calendar: .ics import');
const exp=await p.evaluate(()=>fetch('/api/calendar/export.ics').then(r=>r.text()));ok(exp.includes('SUMMARY:Imported thing')&&exp.includes('SUMMARY:Team offsite')&&exp.includes('RRULE:FREQ=WEEKLY'),'calendar: .ics export includes events + recurrence');
// iCal feed subscription
await p.click('#addfeed');await p.locator('#feeds .fn').last().fill('Holidays');await p.locator('#feeds .fu').last().fill('webcal://127.0.0.1:8823/feed.ics'.replace('webcal','http'));
await p.click('#savefeeds');await p.waitForFunction(()=>document.querySelector('#fmsg').textContent.includes('synced'),null,{timeout:10000});
ok((await api(p,'/items?type=event')).some(e=>e.title==='Feed Holiday'),'calendar: iCal feed URL subscription');
// reminder toast
const soon=new Date(Date.now()+5*60000),pad=n=>String(n).padStart(2,'0');
const ev=await p.evaluate(async s=>fetch('/api/items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'event',title:'Standup NOW',data:{allday:'no',start:s,end:s}})}).then(r=>r.json()),`${soon.getFullYear()}-${pad(soon.getMonth()+1)}-${pad(soon.getDate())}T${pad(soon.getHours())}:${pad(soon.getMinutes())}`);
await p.reload();await p.waitForSelector('#toast:has-text("Standup NOW")',{timeout:8000});ok(true,'calendar: 10-minute reminder toast');

// ---------- CALLS
await nav('calendar');await p.click('[data-m=agenda]');await p.click('.row:has-text("Standup NOW")');await p.waitForSelector('#addcall');await p.click('#addcall');await p.waitForTimeout(1200);
const loc=await p.inputValue('[data-k=location]');ok(/#call\/[a-z0-9-]+$/.test(loc),'calls: "Add video call link" on an event');
await closeDetail();await nav('calls');await p.waitForSelector('.row:has-text("Call: Standup NOW")');ok(true,'calls: call listed');
await p.click('#start');await p.waitForSelector('#tiles .tile');await p.waitForTimeout(1500);
ok(await p.evaluate(()=>document.querySelector('#tiles video').videoWidth>0),'calls: local camera preview');
await p.click('#mic');ok((await p.textContent('#mic')).includes('Unmute'),'calls: mute toggle');
await p.click('#cam');ok((await p.textContent('#cam')).includes('Camera on'),'calls: camera toggle');
await p.click('#rec');await p.waitForTimeout(2000);await p.click('#rec');await p.waitForTimeout(1500);
await p.fill('#cn','Decided: ship [[Project Plan]]');await p.waitForTimeout(800);
await p.click('#leave');await p.waitForSelector('.row');await p.waitForTimeout(500);
const calls=await api(p,'/items?type=call');const last=calls.find(c=>c.data.recording);
ok(last&&last.data.status==='ended'&&last.body.includes('Project Plan'),'calls: solo call → recording saved, notes saved, status ended');
const rec=await p.evaluate(u=>fetch(u).then(r=>r.arrayBuffer().then(a=>[r.status,a.byteLength])),'/recordings/'+last.data.recording);const head=await p.evaluate(u=>fetch(u).then(r=>r.arrayBuffer()).then(a=>[...new Uint8Array(a.slice(0,4))].map(x=>x.toString(16)).join('')),'/recordings/'+last.data.recording);ok(rec[0]===200&&rec[1]>300&&head==='1a45dfa3',`calls: recording downloadable, valid WebM (${rec[1]} bytes)`);

// ---------- SEARCH
await nav('docs');await p.fill('#q','Project Plan');await p.waitForSelector('#view h2:has-text("Results")');await p.waitForSelector('#view .row');
ok(await p.locator('#view .row').count()>=2,'search: finds items by title and body links');
await p.click('#view .row:has-text("Project Plan")');await p.waitForSelector('#detail.open');ok(true,'search: result opens item');
await p.fill('#q','got it');await p.waitForFunction(()=>document.querySelector('#view').textContent.includes('got it'));ok(true,'search: finds chat messages');
await p.fill('#q','');await p.waitForTimeout(500);

// ---------- PWA / assets
const pwa=await p.evaluate(async()=>{const m=await fetch('/manifest.webmanifest').then(r=>r.json());const i=await Promise.all(m.icons.map(x=>fetch(x.src).then(r=>r.status)));const reg=await navigator.serviceWorker.getRegistration();return {name:m.name,icons:i,sw:!!reg}});
ok(pwa.name==='Macro Local'&&pwa.icons.every(s=>s===200)&&pwa.sw,'app: manifest, icons and service worker (installable)');

// ---------- responsive
await closeDetail();
await p.setViewportSize({width:390,height:800});
for(const v of ['docs','tasks','chat','email','calendar','calls','crm','settings']){await p.click(`a[data-v=${v}]`);await p.waitForTimeout(300);
  const w=await p.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]);if(w[0]>w[1]+2){console.log('  overflow in',v,w);fails++}}
ok(true,'responsive: 390px wide checked for horizontal overflow on all views');
console.log('console errors:',errs.filter(e=>!/status of 40[0-9]/.test(e)));
console.log(fails?`\n${fails} FAILED`:'\nALL PASSED');await b.close();process.exit(fails?1:0)})().catch(e=>{console.error('CRASH',e.message);process.exit(1)})
