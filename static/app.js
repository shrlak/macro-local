/* Macro Local front end: icon rail + list panel + main page (Macro-style). No build step, no dependencies. */
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api=async(m,u,b)=>{const r=await fetch('/api'+u,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return r.json()};
const pad=n=>String(n).padStart(2,'0'),ymd=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`,hm=d=>pad(d.getHours())+':'+pad(d.getMinutes());
function toast(t){const e=$('#toast');e.textContent=t;e.style.display='block';clearTimeout(toast.t);toast.t=setTimeout(()=>e.style.display='none',5000)}

/* ---------- icons ---------- */
const IC={
  plus:'<path d="M5 12h14M12 5v14"/>',search:'<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  home:'<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  file:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.6A8 8 0 1 1 21 12z"/>',
  tasks:'<path d="m4 6 1.5 1.5L8 5M4 12l1.5 1.5L8 11M4 18l1.5 1.5L8 17M12 6h8M12 12h8M12 18h8"/>',
  cal:'<rect x="3" y="4.5" width="18" height="16" rx="2"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  video:'<rect x="2.5" y="6" width="13" height="12" rx="2"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/>',
  building:'<path d="M5 21V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v17M15 9h3a1 1 0 0 1 1 1v11M3 21h18M9 7h2M9 11h2M9 15h2"/>',
  sliders:'<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  hash:'<path d="M5 9h14M5 15h14M10 4 8 20M16 4l-2 16"/>',
  check:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>',
  briefcase:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"/>',
  trash:'<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
  link:'<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  reply:'<path d="m9 17-5-5 5-5"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>',
  refresh:'<path d="M20 11a8 8 0 0 0-14.5-4M4 4v4h4M4 13a8 8 0 0 0 14.5 4M20 20v-4h-4"/>',
  chev:'<path d="m9 6 6 6-6 6"/>',chevl:'<path d="m15 6-6 6 6 6"/>',x:'<path d="M6 6l12 12M18 6 6 18"/>',
  board:'<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="4" height="13" rx="1.5"/>',
  send:'<path d="M5 12h14M13 6l6 6-6 6"/>',download:'<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',back:'<path d="m15 6-6 6 6 6"/>'
};
const I=(n,sz=18)=>`<svg width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${IC[n]||''}</svg>`;
const AVC=['#D9C9B0','#C7D5C3','#C9D3E3','#E0C3C3','#D7CBE0','#E6D8A8','#C3D9D6'];
const avatar=(name,sz)=>{const n=String(name||'?').replace(/<.*?>/g,'').replace(/["']/g,'').trim()||'?';let h=0;for(const c of n)h=(h*31+c.charCodeAt(0))>>>0;
  return `<span class="avatar" style="background:${AVC[h%AVC.length]}${sz?`;width:${sz}px;height:${sz}px;font-size:${Math.round(sz/2.1)}px`:''}">${esc(n[0].toUpperCase())}</span>`};
const person=s=>String(s||'').replace(/<.*?>/g,'').replace(/["']/g,'').trim()||String(s||'').replace(/[<>]/g,'');

/* ---------- model ---------- */
const RRULES={'':'Does not repeat','FREQ=DAILY':'Daily','FREQ=WEEKLY':'Weekly','FREQ=MONTHLY':'Monthly','FREQ=YEARLY':'Yearly'};
const TYPES={
  doc:{label:'Docs',one:'Doc',fields:[]},
  task:{label:'Tasks',one:'Task',fields:[['status','Status',['todo','doing','done']],['due','Due','date']],board:'status',cols:['todo','doing','done']},
  contact:{label:'Contacts',one:'Contact',fields:[['email','Email'],['phone','Phone'],['company','Company']]},
  company:{label:'Companies',one:'Company',fields:[['domain','Domain'],['industry','Industry']]},
  deal:{label:'Deals',one:'Deal',fields:[['stage','Stage',['lead','qualified','proposal','won','lost']],['value','Value ($)'],['contact','Contact']],board:'stage',cols:['lead','qualified','proposal','won','lost']},
  email:{label:'Email',one:'Email',fields:[['from','From'],['to','To'],['cc','Cc'],['date','Date']]},
  event:{label:'Events',one:'Event',fields:[['allday','All day',['no','yes']],['start','Start','dt'],['end','End','dt'],['rrule','Repeat',Object.keys(RRULES),RRULES],['location','Location']]},
  call:{label:'Calls',one:'Call',fields:[['status','Status',['live','ended','scheduled']],['duration','Duration (min)'],['room','Room ID']]},
};
const MODS={home:['Home','home'],docs:['Docs','file'],email:['Email','mail'],chat:['Chat','chat'],tasks:['Tasks','tasks'],calendar:['Calendar','cal'],calls:['Calls','video'],crm:['CRM','building'],settings:['Settings','sliders']};
const RAIL=['home','docs','email','chat','tasks','calendar','calls','crm'];
const TYPE_ICON={doc:'file',task:'check',email:'mail',event:'cal',contact:'user',company:'building',deal:'briefcase',call:'video'};
const MOD_OF={doc:'docs',task:'tasks',email:'email',event:'calendar',call:'calls',contact:'crm',company:'crm',deal:'crm'};
const S={mod:'home',id:null,crm:'contact',box:'inbox',compose:null,cal:{d:new Date(),mode:'month'},rt:0,pt:0,timers:[],upd:null};
let call=null,pendingFlush=null;
const clearTimers=()=>{S.timers.forEach(clearInterval);S.timers=[]};
const every=(fn,ms)=>S.timers.push(setInterval(fn,ms));

/* ---------- routing ---------- */
function nav(mod,id=null,mobilePanel=false){
  if(pendingFlush)pendingFlush();
  S.mod=mod;S.id=id;if(mod==='email')S.compose=null;
  const h=`#/${mod}${id?'/'+id:''}`;if(location.hash!==h)history.pushState(null,'',h);
  document.body.classList.toggle('mob-panel',!!mobilePanel);render();
}
async function openItem(id){
  const it=await api('GET','/items/'+id);if(it.error)return;
  if(['contact','company','deal'].includes(it.type))S.crm=it.type;
  if(it.type==='email')S.box=it.data.folder==='sent'?'sent':'inbox';
  nav(MOD_OF[it.type]||'docs',id);
}
function parseHash(){
  const h=location.hash;let m=h.match(/^#call\/(.+)$/);
  if(m){history.replaceState(null,'',location.pathname+'#/calls');S.mod='calls';S.id=null;joinByRoom(m[1]);return}
  m=h.match(/^#\/(\w+)(?:\/(\w+))?/);if(m&&MODS[m[1]]){S.mod=m[1];S.id=m[2]||null}
}
window.addEventListener('popstate',()=>{parseHash();document.body.classList.remove('mob-panel');render()});
async function newItem(type,data={},title='Untitled'){
  const defaults={task:{status:'todo'},deal:{stage:'lead'}}[type]||{};
  const it=await api('POST','/items',{type,title,data:{...defaults,...data}});
  if(['contact','company','deal'].includes(type))S.crm=type;
  nav(MOD_OF[type],it.id);return it;
}

/* ---------- render ---------- */
async function render(){
  clearTimers();const t=++S.rt;
  renderRail();renderUpdate();
  await Promise.all([renderPanel(),renderPage(t)]);
}
function renderRail(){
  const btn=(k,ic,title,extra='')=>`<button class="ib ${S.mod===k?'on':''}" data-mod="${k}" title="${title}">${I(ic,19)}${extra}</button>`;
  const name=localStorage.name||'Me';
  $('#rail').innerHTML=`<button class="ib" data-act="new" title="New…">${I('plus',19)}</button><button class="ib" data-act="search" title="Search (⌘K)">${I('search',19)}</button>`+
    RAIL.map(k=>btn(k,MODS[k][1],MODS[k][0],k==='calls'&&call?'<i class="dot"></i>':'')).join('')+'<div class="sp"></div>'+btn('settings','sliders','Settings')+avatar(name);
  $('#rail').querySelectorAll('[data-mod]').forEach(b=>b.onclick=()=>nav(b.dataset.mod,null,true));
  $('#rail [data-act=new]').onclick=e=>newMenu(e.currentTarget);
  $('#rail [data-act=search]').onclick=openPalette;
}
function setBar(crumbs,acts=''){
  $('#bar').innerHTML=`<button class="ib mobback" style="display:none" title="Back">${I('back')}</button><div class="crumbs">${crumbs}</div><div class="acts">${call&&S.mod!=='calls'?`<button class="btn sm" id="incall"><span class="rec-dot">●</span> In call</button>`:''}${acts}</div>`;
  if($('#incall'))$('#incall').onclick=()=>nav('calls');
  const bk=$('#bar .mobback');if(bk){bk.onclick=()=>document.body.classList.add('mob-panel')}
  const mq=matchMedia('(max-width:820px)').matches;if(bk)bk.style.display=mq?'grid':'none';
}
const crumbRoot=()=>`<a data-root>${MODS[S.mod][0]}</a>`;
function bindCrumbRoot(){const a=$('#bar [data-root]');if(a)a.onclick=()=>nav(S.mod,null)}

/* ---------- panel (left list) ---------- */
const prow=o=>`<div class="prow ${o.sel?'sel':''} ${o.cls||''}" data-id="${esc(o.id||'')}" ${o.nav?`data-nav="${o.nav}"`:''}><span class="ico">${o.icon}</span><span class="txt">${o.html}</span>${o.meta?`<span class="meta">${esc(o.meta)}</span>`:''}</div>`;
const phead=(title,btns='')=>`<div class="phead"><h2>${title}</h2>${btns}</div>`;
const ago=ts=>{const d=Date.now()/1e3-ts;if(d<60)return'now';if(d<3600)return Math.floor(d/60)+'m';if(d<86400)return Math.floor(d/3600)+'h';return new Date(ts*1e3).toLocaleDateString(undefined,{month:'short',day:'numeric'})};
function bucket(ts){const d=Date.now()/1e3-ts;if(d<3600)return'Last hour';const t0=new Date();t0.setHours(0,0,0,0);const z=t0/1e3;if(ts>=z)return'Earlier today';if(ts>=z-86400)return'Yesterday';if(d<7*86400)return'This week';return'Earlier'}
const titleOf=i=>esc(i.title||'Untitled');
async function renderPanel(){
  const t=++S.pt,P=$('#panel');let html='',bind=()=>{};
  const done=()=>{if(t!==S.pt)return false;P.innerHTML=html;bind();return true};
  const rowsClick=fn=>{P.querySelectorAll('.prow[data-id]:not([data-nav])').forEach(r=>r.onclick=()=>{document.body.classList.remove('mob-panel');fn(r.dataset.id,r)})};
  if(S.mod==='home'){
    const all=(await api('GET','/items')).filter(i=>i.type!=='event'&&!(i.type==='email'&&i.data.folder==='sent')).slice(0,90);
    let last='';const groups=all.map(i=>{const b=bucket(i.updated),h=b!==last?`<div class="psec">${b}</div>`:'';last=b;return h+prow({id:i.id,icon:I(TYPE_ICON[i.type],16),html:titleOf(i),sel:S.id===i.id})}).join('');
    html=phead('Home',`<button class="ib" id="new" title="New…">${I('plus')}</button>`)+`<div class="pbody">${groups||'<div class="pempty">Nothing yet — create something with +</div>'}</div>`;
    bind=()=>{$('#new').onclick=e=>newMenu(e.currentTarget);rowsClick(id=>openItem(id))};
  }else if(['docs','tasks','crm','calls'].includes(S.mod)){
    const type=S.mod==='docs'?'doc':S.mod==='tasks'?'task':S.mod==='calls'?'call':S.crm,T=TYPES[type];
    const items=await api('GET','/items?type='+type);let body='',head='';
    if(S.mod==='tasks'||(S.mod==='crm'&&type==='deal')){
      body+=prow({id:'',icon:I('board',16),html:'Board',sel:!S.id,nav:'board'});
      if(S.mod==='tasks')T.cols.forEach(c=>{const l=items.filter(i=>(i.data.status||'todo')===c);if(l.length)body+=`<div class="psec">${{todo:'To do',doing:'In progress',done:'Done'}[c]}</div>`+l.map(i=>prow({id:i.id,icon:I('check',16),html:titleOf(i),meta:i.data.due||'',sel:S.id===i.id})).join('')});
      else body+=items.map(i=>prow({id:i.id,icon:I('briefcase',16),html:titleOf(i),meta:i.data.value?'$'+i.data.value:'',sel:S.id===i.id})).join('');
    }else body+=items.map(i=>prow({id:i.id,icon:I(TYPE_ICON[type],16),html:titleOf(i),meta:S.mod==='calls'?(i.data.status==='live'?'live':''):(i.data.email||i.data.domain||''),sel:S.id===i.id})).join('')||`<div class="pempty">No ${T.label.toLowerCase()} yet</div>`;
    if(S.mod==='crm')head=`<div style="padding:0 12px 8px"><div class="seg">${['contact','company','deal'].map(x=>`<button data-t="${x}" class="${S.crm===x?'on':''}">${TYPES[x].label}</button>`).join('')}</div></div>`;
    if(S.mod==='calls')head=`<button class="btn dark pnew" id="start">${I('video',16)} Start a call</button><div style="padding:0 18px 6px"><a class="lnk" id="join">Join with a link…</a></div>`;
    html=phead(MODS[S.mod][0],S.mod==='calls'?'':`<button class="ib" id="new" title="New ${T.one.toLowerCase()}">${I('plus')}</button>`)+head+`<div class="pbody">${body}</div>`;
    bind=()=>{if($('#new'))$('#new').onclick=()=>newItem(type);
      P.querySelectorAll('[data-nav=board]').forEach(r=>r.onclick=()=>{document.body.classList.remove('mob-panel');nav(S.mod,null)});
      P.querySelectorAll('.seg [data-t]').forEach(b=>b.onclick=()=>{S.crm=b.dataset.t;nav('crm',null,true)});
      rowsClick(id=>{if(id)nav(S.mod,id)});
      if($('#start'))$('#start').onclick=startCall;if($('#join'))$('#join').onclick=()=>{const m=(prompt('Paste the join link or room ID')||'').match(/([a-z0-9]+-[a-z0-9]+-[a-z0-9]+)\s*$/i);if(m)joinByRoom(m[1])}};
  }else if(S.mod==='email'){
    const items=await api('GET','/items?type=email');
    const list=items.filter(i=>(i.data.folder||'inbox')===S.box).sort((a,b)=>(b.data.date||'').localeCompare(a.data.date||''));
    html=phead('Email',`<button class="ib" id="sync" title="Sync">${I('refresh')}</button>`)+`<button class="btn dark pnew" id="comp">${I('plus',16)} New email</button>
      <div style="padding:0 12px 8px"><div class="seg"><button data-b="inbox" class="${S.box==='inbox'?'on':''}">Inbox</button><button data-b="sent" class="${S.box==='sent'?'on':''}">Sent</button></div> <span id="ms" class="err" style="font-size:12px"></span></div>
      <div class="pbody">${list.map(i=>{const who=person(S.box==='sent'?i.data.to:i.data.from);return `<div class="prow two ${i.data.unread==='yes'?'unread':''} ${S.id===i.id?'sel':''}" data-id="${i.id}"><span class="ico">${avatar(who,26)}</span><span class="txt"><span class="l1"><b>${esc(who)}</b><span class="meta">${esc((i.data.date||'').slice(5,10))}</span></span><span class="l2">${titleOf(i)}</span></span></div>`}).join('')||'<div class="pempty">No messages</div>'}</div>`;
    bind=()=>{P.querySelectorAll('.seg [data-b]').forEach(b=>b.onclick=()=>{S.box=b.dataset.b;nav('email',null,true)});
      $('#comp').onclick=composeNew;
      $('#sync').onclick=async()=>{$('#ms').textContent='Syncing…';$('#ms').className='muted';const r=await api('POST','/email/sync',{});if(r.error){$('#ms').textContent=r.error;$('#ms').className='err'}else{toast(r.new+' new message(s)');render()}};
      rowsClick(async id=>{const it=items.find(i=>i.id===id);if(it&&it.data.unread==='yes')await api('PUT','/items/'+id,{data:{unread:'no'}});nav('email',id)})};
  }else if(S.mod==='chat'){
    const chans=await api('GET','/channels');if(!S.id||!chans.find(c=>c.id===S.id))S.id=chans[0].id;
    html=phead('Chat',`<button class="ib" id="nc" title="New channel">${I('plus')}</button>`)+`<div class="pbody">${chans.map(c=>prow({id:c.id,icon:I('hash',16),html:esc(c.name),sel:S.id===c.id})).join('')}</div>`;
    bind=()=>{$('#nc').onclick=async()=>{const n=prompt('Channel name');if(n){const r=await api('POST','/channels',{name:n});nav('chat',r.id||null)}};rowsClick(id=>nav('chat',id))};
  }else if(S.mod==='calendar'){
    const a=new Date();a.setHours(0,0,0,0);const b=new Date(a);b.setDate(a.getDate()+21);
    const evs=await api('GET',`/calendar?start=${ymd(a)}&end=${ymd(b)}`);let last='',body=prow({id:'',icon:I('cal',16),html:'Calendar',sel:!S.id,nav:'cal'});
    evs.forEach(e=>{const [s]=evRange(e),k=ymd(s)<ymd(a)?ymd(a):ymd(s);if(k!==last){body+=`<div class="psec">${new Date(k+'T00:00').toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}</div>`;last=k}
      body+=prow({id:e.id,icon:I('cal',16),html:esc(e.title),meta:e.allday?'all day':hm(s),sel:S.id===e.id})});
    html=phead('Calendar',`<button class="ib" id="new" title="New event">${I('plus')}</button>`)+`<div class="pbody">${body}</div>`;
    bind=()=>{$('#new').onclick=newEventNow;P.querySelectorAll('[data-nav=cal]').forEach(r=>r.onclick=()=>{document.body.classList.remove('mob-panel');nav('calendar',null)});rowsClick(id=>{if(id)nav('calendar',id)})};
  }else if(S.mod==='settings'){
    const secs=[['google','Google'],['caldav','Apple Calendar & CalDAV'],['email','Email (IMAP / SMTP)'],['feeds','Calendar subscriptions'],['updates','Updates'],['misc','Reminders & data']];
    html=phead('Settings')+`<div class="pbody">${secs.map(([k,l])=>prow({id:k,icon:I('chev',14),html:l})).join('')}</div>`;
    bind=()=>rowsClick(k=>{document.body.classList.remove('mob-panel');const el=$('#sec-'+k);if(el)el.scrollIntoView({behavior:'smooth',block:'start'})});
  }
  done();
}

/* ---------- pages ---------- */
async function renderPage(t){
  const host=$('#page');host.scrollTop=0;
  const ok=()=>t===S.rt;
  try{
    if(S.mod==='home')await homePage(host,ok);
    else if(S.mod==='docs')S.id?await itemPage(S.id,host,ok):emptyPage(host,'docs','Docs','Notes you can link together with [[Title]].');
    else if(S.mod==='tasks')S.id?await itemPage(S.id,host,ok):await boardPage('task',host,ok);
    else if(S.mod==='crm')S.id?await itemPage(S.id,host,ok):TYPES[S.crm].board?await boardPage(S.crm,host,ok):emptyPage(host,'building',TYPES[S.crm].label,'Select one from the list, or create a new one with +.');
    else if(S.mod==='chat')await chatPage(host,ok);
    else if(S.mod==='email')await emailPage(host,ok);
    else if(S.mod==='calendar')S.id?await itemPage(S.id,host,ok):await calendarPage(host,ok);
    else if(S.mod==='calls')S.id?await itemPage(S.id,host,ok):call?renderCallScreen(host):lobbyPage(host);
    else if(S.mod==='settings')await settingsPage(host,ok);
  }catch(e){console.error(e);if(ok())host.innerHTML=`<div class="empty"><h3>Something went wrong</h3><div class="err">${esc(e.message)}</div></div>`}
}
function emptyPage(host,icon,title,sub){setBar(`<b>${MODS[S.mod][0]}</b>`);host.innerHTML=`<div class="empty"><div class="mark">${I(icon,24)}</div><h3>${esc(title)}</h3><div>${esc(sub)}</div></div>`}

/* home */
async function homePage(host,ok){
  setBar('<b>Home</b>');
  const t=new Date(),e=new Date(t.getTime()+864e5);
  const [evs,tasks,mails,docs]=await Promise.all([api('GET',`/calendar?start=${ymd(t)}&end=${ymd(t)}`),api('GET','/items?type=task'),api('GET','/items?type=email'),api('GET','/items?type=doc')]);
  if(!ok())return;
  const h=t.getHours(),greet=h<5?'Working late':h<12?'Good morning':h<18?'Good afternoon':'Good evening';
  const open=tasks.filter(x=>x.data.status!=='done').slice(0,6),unread=mails.filter(m=>(m.data.folder||'inbox')==='inbox'&&m.data.unread==='yes');
  const row=(ic,tx,m,id)=>`<div class="lrow" data-id="${id}"><span class="faint">${I(ic,16)}</span><span class="t">${tx}</span><span class="m">${esc(m||'')}</span></div>`;
  host.innerHTML=`<div class="wrap wide"><div class="faint">${t.toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'})}</div><div class="hello">${greet}${localStorage.name?', '+esc(localStorage.name):''}.</div>
   <div class="muted">${evs.length?`${evs.length} event${evs.length>1?'s':''} today`:'No events today'} · ${open.length} open task${open.length===1?'':'s'} · ${unread.length} unread</div>
   <div class="grid2">
    <div class="card"><h3>${I('cal',15)} Today</h3>${evs.map(x=>row('cal',esc(x.title),x.allday?'all day':hm(new Date(x.start)),x.id)).join('')||'<div class="faint">Nothing scheduled.</div>'}</div>
    <div class="card"><h3>${I('tasks',15)} Open tasks</h3>${open.map(x=>row('check',esc(x.title),x.data.due,x.id)).join('')||'<div class="faint">All clear.</div>'}</div>
    <div class="card"><h3>${I('mail',15)} Inbox</h3>${mails.filter(m=>(m.data.folder||'inbox')==='inbox').sort((a,b)=>(b.data.date||'').localeCompare(a.data.date||'')).slice(0,5).map(x=>row('mail',`<b style="font-weight:${x.data.unread==='yes'?650:450}">${esc(person(x.data.from))}</b> · ${esc(x.title)}`,'',x.id)).join('')||'<div class="faint">No mail yet.</div>'}</div>
    <div class="card"><h3>${I('file',15)} Recent docs</h3>${docs.slice(0,5).map(x=>row('file',esc(x.title||'Untitled'),ago(x.updated),x.id)).join('')||'<div class="faint">No docs yet.</div>'}</div>
   </div></div>`;
  host.querySelectorAll('.lrow').forEach(r=>r.onclick=()=>openItem(r.dataset.id));
}

/* item editor */
const toLocalInput=(s,allday)=>{if(!s)return'';if(allday)return s.slice(0,10);if(s.length===10)return s+'T09:00';if(s.endsWith('Z')){const d=new Date(s);return ymd(d)+'T'+hm(d)}return s.slice(0,16)};
function fieldHtml(it,[k,l,opt,labels]){
  const v=it.data[k]??'';
  if(Array.isArray(opt)){const o=opt.includes(v)||v===''&&!opt.includes('')?opt:[...opt,v];
    return `<select data-k="${k}">${o.map(x=>`<option value="${esc(x)}" ${v===x?'selected':''}>${esc(labels?.[x]??(x||'—'))}</option>`).join('')}</select>`}
  if(opt==='dt'){const ad=it.data.allday==='yes';return `<input data-k="${k}" type="${ad?'date':'datetime-local'}" value="${esc(toLocalInput(v,ad))}">`}
  return `<input data-k="${k}" type="${opt||'text'}" value="${esc(v)}" placeholder="—">`;
}
function normalizeData(type,data){
  if(type==='event'&&data.start){const ad=data.allday==='yes';
    if(ad){data.start=data.start.slice(0,10);data.end=(data.end||data.start).slice(0,10)}
    else{if(data.start.length===10)data.start+='T09:00';data.end=data.end?(data.end.length===10?data.end+'T10:00':data.end):data.start}
    if(data.end<data.start)data.end=data.start}
  return data;
}
async function itemPage(id,host,ok){
  const it=await api('GET','/items/'+id);
  if(!ok())return;
  if(it.error){S.id=null;return render()}
  if(it.type==='email'&&S.mod!=='email'){return openItem(id)}
  const T=TYPES[it.type],d=host,$d=q=>d.querySelector(q);
  const extra=it.type==='event'?`<div class="row"><button class="btn sm" id="addcall">${I('video',15)} Add video call link</button></div>`:
    it.type==='call'?`${it.data.recording?`<div class="sect"><h4>Recording</h4><audio controls style="width:100%" src="/recordings/${esc(it.data.recording)}"></audio><div><a class="lnk" href="/recordings/${esc(it.data.recording)}" download>Download</a></div></div>`:''}
      <div class="row"><button class="btn sm" id="copylink">${I('link',15)} Copy join link</button>${it.data.status==='live'||it.data.status==='scheduled'?`<button class="btn sm dark" id="rejoin">Join</button>`:''}</div>`:'';
  const placeholder=it.type==='call'?'Notes or transcript…':'Write something — link anything with [[Title]]';
  host.innerHTML=`<div class="wrap"><input class="doc-title" id="t" value="${esc(it.title)}" placeholder="Untitled">
    <div class="props">${T.fields.map(f=>`<label>${f[1]}</label><div>${fieldHtml(it,f)}</div>`).join('')}</div>${extra}
    <div class="mentions" id="mn"></div><textarea class="doc-body" id="b" placeholder="${placeholder}">${esc(it.body)}</textarea>
    <div class="sect"><h4>Linked from</h4>${it.backlinks.map(b=>`<div class="lrow" data-id="${b.id}"><span class="faint">${I(TYPE_ICON[b.type]||'file',15)}</span><span class="t">${esc(b.title||b.id)}</span></div>`).join('')||`<div class="faint">Nothing links here yet. Reference this item as [[${esc(it.title||'Title')}]] anywhere.</div>`}</div></div>`;
  const crumbs=()=>`${crumbRoot()}<span class="faint">${I('chev',13)}</span><span class="faint">${I(TYPE_ICON[it.type],15)}</span><b id="ct">${esc($d('#t')?$d('#t').value||'Untitled':it.title||'Untitled')}</b>`;
  const acts=`<button class="ib" id="copyref" title="Copy [[link]]">${I('link')}</button><button class="ib" id="del" title="Delete">${I('trash')}</button>`;
  setBar(crumbs(),acts);bindCrumbRoot();
  const grow=()=>{const b=$d('#b');b.style.height='auto';b.style.height=Math.max(220,b.scrollHeight+6)+'px'};grow();
  const mentions=()=>{$d('#mn').innerHTML=(it.links||[]).map(l=>l.item?`<a class="pill" data-id="${l.item.id}">${I(TYPE_ICON[l.item.type]||'file',13)} ${esc(l.item.title||l.ref)}</a>`:`<span class="pill dead">${esc(l.ref)}</span>`).join('');
    $d('#mn').querySelectorAll('a[data-id]').forEach(a=>a.onclick=()=>openItem(a.dataset.id))};mentions();
  // Snapshot the form when the user edits (never when a timer fires): by then the page may show a different item.
  let tm,snap=null;
  const collect=()=>{const data={};d.querySelectorAll('[data-k]').forEach(e=>data[e.dataset.k]=e.value);return{title:$d('#t').value,body:$d('#b').value,data:normalizeData(it.type,data)}};
  const flush=async reopen=>{clearTimeout(tm);if(pendingFlush===flush)pendingFlush=null;if(!snap)return;const s=snap;snap=null;
    await api('PUT','/items/'+id,s);renderPanel();if(S.id!==id)return;
    if(reopen===true)return render();it.links=(await api('GET','/items/'+id)).links;if(S.id===id)mentions()};
  const touch=()=>{snap=collect();pendingFlush=flush;clearTimeout(tm);tm=setTimeout(flush,400);if($('#ct'))$('#ct').textContent=snap.title||'Untitled';grow()};
  d.querySelectorAll('input,textarea,select').forEach(e=>{e.oninput=touch;e.onchange=()=>{if(e.dataset.k==='allday'){snap=collect();flush(true)}}});
  d.querySelectorAll('.lrow[data-id]').forEach(a=>a.onclick=()=>openItem(a.dataset.id));
  $('#del').onclick=async()=>{if(confirm('Delete this item?')){snap=null;clearTimeout(tm);pendingFlush=null;await api('DELETE','/items/'+id);nav(S.mod,null)}};
  $('#copyref').onclick=()=>{navigator.clipboard?.writeText(`[[${$d('#t').value||it.title}]]`);toast('Link copied — paste it into any note')};
  if($d('#addcall'))$d('#addcall').onclick=async()=>{const c=await api('POST','/items',{type:'call',title:'Call: '+(it.title||'event'),data:{room:rid(),status:'scheduled'}});
    await api('PUT','/items/'+id,{data:{location:callLink(c.data.room)},body:$d('#b').value+`\n\nVideo call: [[${c.id}]]`});render()};
  if($d('#copylink'))$d('#copylink').onclick=()=>{navigator.clipboard?.writeText(callLink(it.data.room));toast('Join link copied')};
  if($d('#rejoin'))$d('#rejoin').onclick=()=>joinRoom(it.data.room,id);
  if(it.title==='Untitled'||it.title==='New event')$d('#t').select();
}

/* board */
async function boardPage(type,host,ok){
  const items=await api('GET','/items?type='+type);if(!ok())return;
  const T=TYPES[type],f=T.board;
  setBar(`<b>${S.mod==='crm'?'Deals pipeline':T.label}</b>`,`<button class="btn sm dark" id="newb">${I('plus',15)} New ${T.one.toLowerCase()}</button>`);
  host.innerHTML=`<div class="board">${T.cols.map(c=>{const l=items.filter(i=>(i.data[f]||T.cols[0])===c);
    return `<div class="col" data-c="${c}"><h3>${{todo:'To do',doing:'In progress',done:'Done'}[c]||c} <span>${l.length}</span></h3>${l.map(i=>`<div class="kcard" draggable="true" data-id="${i.id}">${esc(i.title||'Untitled')}${i.data.due||i.data.value?`<small>${i.data.due?`<span class="tag">${I('cal',11)} ${esc(i.data.due)}</span>`:''}${i.data.value?`<span class="tag">$${esc(i.data.value)}</span>`:''}</small>`:''}</div>`).join('')}</div>`}).join('')}</div>`;
  host.querySelectorAll('.kcard').forEach(c=>{c.onclick=()=>nav(S.mod,c.dataset.id);c.ondragstart=e=>e.dataTransfer.setData('id',c.dataset.id)});
  host.querySelectorAll('.col').forEach(c=>{c.ondragover=e=>{e.preventDefault();c.classList.add('over')};c.ondragleave=()=>c.classList.remove('over');
    c.ondrop=async e=>{e.preventDefault();await api('PUT','/items/'+e.dataTransfer.getData('id'),{data:{[f]:c.dataset.c}});render()}});
  $('#newb').onclick=()=>newItem(type);
}

/* chat */
async function chatPage(host,ok){
  const chans=await api('GET','/channels');if(!ok())return;const ch=chans.find(c=>c.id===S.id)||chans[0];S.id=ch.id;
  setBar(`${crumbRoot()}<span class="faint">${I('chev',13)}</span><span class="faint">${I('hash',15)}</span><b>${esc(ch.name)}</b>`);bindCrumbRoot();
  host.innerHTML=`<div class="chat"><div class="msgs" id="msgs"></div><div class="composer"><div class="box"><input id="mi" placeholder="Message #${esc(ch.name)}" autocomplete="off"><button class="btn dark" id="ms" style="padding:5px 12px">${I('send',16)}</button></div></div></div>`;
  let since=0,last='';const box=$('#msgs'),me=localStorage.name||'me';
  const fmt=t=>esc(t).replace(/(^|\s)(@\w+)/g,'$1<span class="mention">$2</span>');
  const poll=async()=>{if(S.mod!=='chat'||S.id!==ch.id)return;const ms=await api('GET',`/channels/${ch.id}/messages?since=${since}`);
    if(!ms.length)return;const first=since===0,atEnd=box.scrollHeight-box.scrollTop-box.clientHeight<80;
    ms.forEach(m=>{since=m.seq;const mine=m.author===me,div=document.createElement('div');div.className='msg'+(mine?' me':'');
      div.innerHTML=`${mine?'':avatar(m.author,30)}<div><div class="who"><b>${esc(m.author)}</b>${new Date(m.created*1000).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})}</div><div class="bubble">${fmt(m.text)}</div>${m.task_id?` <a class="lnk" data-id="${m.task_id}" style="font-size:12px">${I('check',13)} task</a>`:''}</div>
        <div class="tools"><button class="btn sm" title="Turn into a task">→ task</button></div>`;
      div.querySelector('button').onclick=async()=>openItem((await api('POST',`/messages/${m.id}/to-task`)).id);
      const l=div.querySelector('.lnk');if(l)l.onclick=()=>openItem(l.dataset.id);box.appendChild(div);last=m.author});
    if(first||atEnd)box.scrollTop=box.scrollHeight};
  const send=async()=>{const x=$('#mi').value.trim();if(!x)return;$('#mi').value='';await api('POST',`/channels/${ch.id}/messages`,{text:x,author:me});poll()};
  $('#ms').onclick=send;$('#mi').onkeydown=e=>{if(e.key==='Enter')send()};
  await poll();every(poll,1500);if(!matchMedia('(max-width:820px)').matches)$('#mi').focus();
}

/* email */
async function emailPage(host,ok){
  const [items,st]=await Promise.all([api('GET','/items?type=email'),api('GET','/settings')]);if(!ok())return;
  const configured=(st.email&&st.email.address&&st.email.has_password)||(st.google?.connected&&st.google.mail);
  if(S.compose){const c=S.compose;
    setBar(`${crumbRoot()}<span class="faint">${I('chev',13)}</span><b>${c.reply?'Reply':'New email'}</b>`);bindCrumbRoot();
    host.innerHTML=`<div class="wrap"><div class="comp"><div class="r"><label>To</label><input id="cto" value="${esc(c.to)}" autocomplete="off"></div><div class="r"><label>Cc</label><input id="ccc" value="${esc(c.cc)}" autocomplete="off"></div>
      <div class="r"><label>Subject</label><input id="csub" value="${esc(c.subject)}" autocomplete="off"></div><textarea id="cbody" placeholder="Write your message…">${esc(c.body)}</textarea>
      <div class="foot"><button class="btn dark" id="csend">Send</button><button class="btn" id="ccancel">Discard</button><span id="cerr" class="err"></span></div></div>
      ${configured?'':'<div class="note">No email account is connected yet — open <a class="lnk" id="gs">Settings</a> first.</div>'}</div>`;
    if($('#gs'))$('#gs').onclick=()=>nav('settings');
    $('#ccancel').onclick=()=>{S.compose=null;render()};
    $('#csend').onclick=async()=>{$('#csend').disabled=true;$('#cerr').textContent='';
      const r=await api('POST','/email/send',{to:$('#cto').value,cc:$('#ccc').value,subject:$('#csub').value,body:$('#cbody').value,in_reply_to:c.reply});
      if(r.error){$('#cerr').textContent=r.error;$('#csend').disabled=false}else{S.compose=null;S.box='sent';toast('Sent');nav('email',r.id)}};
    (c.to?$('#cbody'):$('#cto')).focus();return;
  }
  const sel=items.find(i=>i.id===S.id);
  if(!sel){setBar('<b>Email</b>');
    host.innerHTML=configured?`<div class="empty"><div class="mark">${I('mail',24)}</div><h3>Select a message</h3><div>${items.length} message${items.length===1?'':'s'} synced.</div></div>`:
      `<div class="empty"><div class="mark">${I('mail',24)}</div><h3>Connect your email</h3><div>Add Gmail, iCloud, Outlook or any IMAP account in Settings.</div><button class="btn dark" id="gs">Open settings</button></div>`;
    if($('#gs'))$('#gs').onclick=()=>nav('settings',null,false);return}
  const d=sel.data,sent=d.folder==='sent';
  setBar(`${crumbRoot()}<span class="faint">${I('chev',13)}</span><span class="faint">${I('mail',15)}</span><b>${esc(sel.title)}</b>`,
    `<button class="ib" id="rep" title="Reply">${I('reply')}</button><button class="ib" id="tocon" title="Create CRM contact">${I('user')}</button><button class="ib" id="totask" title="Create task">${I('check')}</button><button class="ib" id="del" title="Delete">${I('trash')}</button>`);bindCrumbRoot();
  const who=person(d.from);
  host.innerHTML=`<div class="wrap"><h1 class="thread-h">${esc(sel.title)}</h1>
    <div class="chips"><span class="pill">${avatar(who,18)} ${esc(who)}</span><span class="pill">${avatar(person(d.to),18)} ${esc(person(d.to))}</span>${d.cc?`<span class="pill">Cc ${esc(person(d.cc))}</span>`:''}</div>
    <div class="mcard"><div class="mh">${avatar(who,30)}<div class="grow"><b>${esc(who)}</b> <span class="muted">to ${esc(sent?person(d.to):'me')}</span></div><span class="faint">${esc((d.date||'').replace('T',' '))}</span></div>
      <div class="mb">${esc(sel.body)}</div>${d.attachments?`<div class="mb" style="padding-top:0"><span class="tag">${esc(d.attachments)}</span> <span class="faint">open in your mail provider to download</span></div>`:''}
      <div class="replybar" id="replybar">${avatar(localStorage.name||'Me',22)} Reply…</div></div></div>`;
  const reply=()=>{S.compose={to:(sent?d.to:d.from),cc:'',subject:/^re:/i.test(sel.title)?sel.title:'Re: '+sel.title,reply:d.message_id||'',
    body:`\n\nOn ${(d.date||'').replace('T',' ')}, ${d.from} wrote:\n`+sel.body.split('\n').map(l=>'> '+l).join('\n')};render()};
  $('#rep').onclick=reply;$('#replybar').onclick=reply;
  $('#tocon').onclick=async()=>{const c=await api('POST',`/items/${sel.id}/to-contact`);toast('Contact created');openItem(c.id)};
  $('#totask').onclick=async()=>{const t=await api('POST',`/items/${sel.id}/to-task`);toast('Task created');openItem(t.id)};
  $('#del').onclick=async()=>{if(confirm('Delete this message from Macro Local? (Your mail server copy is untouched.)')){await api('DELETE','/items/'+sel.id);nav('email',null)}};
}

/* calendar */
function evRange(e){let s,en;
  if(e.allday){s=new Date(e.start.slice(0,10)+'T00:00');en=new Date(e.end.slice(0,10)+'T00:00');en.setDate(en.getDate()+1)}
  else{s=new Date(e.start);en=new Date(e.end||e.start)}
  return [s,en]}
function eachDay(s,en,fn){const d=new Date(s.getFullYear(),s.getMonth(),s.getDate());let n=0;do{fn(new Date(d));d.setDate(d.getDate()+1)}while(d<en&&++n<60)}
function composeNew(){S.mod='email';S.id=null;S.compose={to:'',cc:'',subject:'',body:'',reply:''};history.pushState(null,'','#/email');document.body.classList.remove('mob-panel');render()}
function newEventNow(){const t=new Date();t.setMinutes(0);t.setHours(t.getHours()+1);const e=new Date(t.getTime()+3600e3);
  return newItem('event',{allday:'no',start:ymd(t)+'T'+hm(t),end:ymd(e)+'T'+hm(e),rrule:''},'New event')}
async function calendarPage(host,ok){
  const C=S.cal;let a,b;
  if(C.mode==='month'){const f=new Date(C.d.getFullYear(),C.d.getMonth(),1);a=new Date(f);a.setDate(1-f.getDay());b=new Date(a);b.setDate(a.getDate()+41)}
  else{a=new Date();a.setHours(0,0,0,0);b=new Date(a);b.setDate(a.getDate()+30)}
  const evs=await api('GET',`/calendar?start=${ymd(a)}&end=${ymd(b)}`);if(!ok())return;const byDay={};
  evs.forEach(e=>{const[s,en]=evRange(e);eachDay(s,en,d=>(byDay[ymd(d)]??=[]).push({...e,s,en,first:ymd(d)===ymd(s)}))});
  setBar(`<b class="ctitle" style="text-align:left;min-width:0">${C.mode==='month'?C.d.toLocaleDateString(undefined,{month:'long',year:'numeric'}):'Next 30 days'}</b>`,
    `<button class="ib" id="pr">${I('chevl')}</button><button class="btn sm" id="td">Today</button><button class="ib" id="nx">${I('chev')}</button>
     <div class="seg"><button data-m="month" class="${C.mode==='month'?'on':''}">Month</button><button data-m="agenda" class="${C.mode==='agenda'?'on':''}">Agenda</button></div><button class="btn sm dark" id="ne">${I('plus',15)} New event</button>`);
  const chip=e=>`<div class="chip" data-id="${e.id}" title="${esc(e.title)}">${e.allday||!e.first?'':hm(e.s)+' '}${esc(e.title)}</div>`;
  if(C.mode==='month'){let cells='';const today=ymd(new Date());
    for(let i=0;i<42;i++){const d=new Date(a);d.setDate(a.getDate()+i);const k=ymd(d),l=byDay[k]||[];
      cells+=`<div class="d ${d.getMonth()!==C.d.getMonth()?'out':''} ${k===today?'today':''}" data-d="${k}"><span class="n">${d.getDate()}</span>${l.slice(0,3).map(chip).join('')}${l.length>3?`<div class="more">+${l.length-3} more</div>`:''}</div>`}
    host.innerHTML=`<div class="cal">${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(x=>`<div class="dh">${x}</div>`).join('')}${cells}</div>`;
  }else{const days=Object.keys(byDay).sort();
    host.innerHTML=`<div class="wrap agenda">${days.map(k=>`<h3>${new Date(k+'T00:00').toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'})}</h3>`+byDay[k].sort((x,y)=>x.s-y.s).map(e=>`<div class="lrow" data-id="${e.id}"><span class="faint">${I('cal',16)}</span><span class="t"><b style="font-weight:550">${esc(e.title)}</b></span><span class="m">${e.allday?'All day':hm(e.s)+'–'+hm(e.en)}${e.location?' · '+esc(e.location):''}</span></div>`).join('')).join('')||'<div class="empty"><div class="mark">'+I('cal',24)+'</div><h3>Nothing coming up</h3></div>'}</div>`}
  host.querySelectorAll('[data-id]').forEach(c=>c.onclick=e=>{e.stopPropagation();nav('calendar',c.dataset.id)});
  host.querySelectorAll('.d').forEach(c=>c.onclick=()=>newItem('event',{allday:'no',start:c.dataset.d+'T09:00',end:c.dataset.d+'T10:00',rrule:''},'New event'));
  document.querySelectorAll('#bar [data-m]').forEach(x=>x.onclick=()=>{C.mode=x.dataset.m;render()});
  $('#pr').onclick=()=>{C.d=new Date(C.d.getFullYear(),C.d.getMonth()-1,1);render()};
  $('#nx').onclick=()=>{C.d=new Date(C.d.getFullYear(),C.d.getMonth()+1,1);render()};
  $('#td').onclick=()=>{C.d=new Date();render()};$('#ne').onclick=newEventNow;
}
/* reminders: notify 10 minutes before timed events while the app is open */
const notified=new Set();
async function checkReminders(){
  try{const t=new Date(),e=new Date(t.getTime()+864e5),evs=await api('GET',`/calendar?start=${ymd(t)}&end=${ymd(e)}`);
    evs.filter(x=>!x.allday).forEach(x=>{const s=new Date(x.start),mins=(s-t)/6e4,k=x.id+x.start;
      if(mins>-1&&mins<=10&&!notified.has(k)){notified.add(k);const msg=`${x.title} at ${hm(s)}${x.location?' · '+x.location:''}`;
        toast('⏰ '+msg);if(window.Notification&&Notification.permission==='granted')new Notification('Upcoming event',{body:msg})}})}catch(e){}
}
setInterval(checkReminders,60000);setTimeout(checkReminders,3000);

/* ---------- calls (peer-to-peer WebRTC; the server only relays signaling) ---------- */
const rid=()=>Math.random().toString(36).slice(2,5)+'-'+Math.random().toString(36).slice(2,6)+'-'+Math.random().toString(36).slice(2,5);
const callLink=r=>location.origin+'/#call/'+r;
function lobbyPage(host){
  setBar('<b>Calls</b>');
  host.innerHTML=`<div class="empty"><div class="mark">${I('video',24)}</div><h3>Calls</h3><div style="max-width:420px">Peer-to-peer video and audio, right in the app. Share the join link with anyone who can reach this server. Record the audio and keep notes — everything is saved to the call.</div><button class="btn dark" id="start2">${I('video',16)} Start a call</button></div>`;
  $('#start2').onclick=startCall;
}
async function startCall(){const it=await api('POST','/items',{type:'call',title:'Call '+new Date().toLocaleString(),data:{room:rid(),status:'live'}});joinRoom(it.data.room,it.id)}
async function joinByRoom(room){const items=await api('GET','/items?type=call'),it=items.find(i=>i.data.room===room);joinRoom(room,it?it.id:null)}
async function joinRoom(room,itemId){
  if(call)return toast('Already in a call');
  S.mod='calls';S.id=null;clearTimers();
  localStorage.name=localStorage.name||prompt('Your name for calls','')||'guest';
  let local;
  try{local=await navigator.mediaDevices.getUserMedia({audio:true,video:true})}
  catch(e){try{local=await navigator.mediaDevices.getUserMedia({audio:true})}catch(e2){render();return toast('Camera/microphone unavailable ('+e2.name+'). Browsers require https:// or localhost.')}}
  const j=await api('POST',`/rooms/${room}/join`,{name:localStorage.name});
  call={room,itemId,id:j.id,pcs:{},pend:{},streams:{},names:{},local,start:Date.now(),rec:null,recSrc:{}};
  if(itemId)api('PUT','/items/'+itemId,{data:{status:'live',room}});
  j.peers.forEach(p=>{call.names[p.id]=p.name;connectPeer(p.id,true)});
  call.timer=setInterval(pollRoom,1000);
  call.clock=setInterval(()=>{const s=Math.floor((Date.now()-call.start)/1000);if($('#ct'))$('#ct').textContent=pad(Math.floor(s/60))+':'+pad(s%60)},1000);
  document.body.classList.remove('mob-panel');history.replaceState(null,'','#/calls');render();
}
const sig=(to,type,data)=>api('POST',`/rooms/${call.room}/signal`,{from:call.id,to,type,data});
function connectPeer(pid,offerer){
  const pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});call.pcs[pid]=pc;
  call.local.getTracks().forEach(t=>pc.addTrack(t,call.local));
  pc.onicecandidate=e=>e.candidate&&sig(pid,'ice',e.candidate);
  pc.ontrack=e=>{call.streams[pid]=e.streams[0];if(call.rec)mixIn(pid);renderTiles()};
  if(offerer)pc.createOffer().then(o=>pc.setLocalDescription(o)).then(()=>sig(pid,'offer',pc.localDescription));
  return pc;
}
async function pollRoom(){
  if(!call)return;const r=await api('GET',`/rooms/${call.room}/poll?id=${call.id}`);
  r.peers.forEach(p=>call.names[p.id]=p.name);
  for(const m of r.msgs){let pc=call.pcs[m.from];
    if(m.type==='offer'){pc=pc||connectPeer(m.from,false);await pc.setRemoteDescription(m.data);await pc.setLocalDescription(await pc.createAnswer());sig(m.from,'answer',pc.localDescription);
      (call.pend[m.from]||[]).forEach(c=>pc.addIceCandidate(c));call.pend[m.from]=[]}
    else if(m.type==='answer'&&pc){await pc.setRemoteDescription(m.data);(call.pend[m.from]||[]).forEach(c=>pc.addIceCandidate(c));call.pend[m.from]=[]}
    else if(m.type==='ice'){if(pc&&pc.remoteDescription)pc.addIceCandidate(m.data);else(call.pend[m.from]??=[]).push(m.data)}}
  const ids=r.peers.map(p=>p.id);
  Object.keys(call.pcs).filter(id=>!ids.includes(id)).forEach(id=>{call.pcs[id].close();delete call.pcs[id];delete call.streams[id]});
  renderTiles();
}
function renderCallScreen(host){
  setBar(`${crumbRoot()}<span class="faint">${I('chev',13)}</span><b>In call</b> <span class="tag" id="ct">00:00</span>`,`<button class="btn sm" id="cp">${I('link',15)} Copy join link</button>`);bindCrumbRoot();
  host.innerHTML=`<div class="wrap wide"><div class="tiles" id="tiles"></div>
   <div class="ctrl"><button class="btn" id="mic">🎤 Mute</button><button class="btn" id="cam">📷 Camera off</button><button class="btn" id="scr">🖥 Share screen</button><button class="btn" id="rec">⏺ Record audio</button><button class="btn danger" id="leave">Leave</button></div>
   ${call.itemId?'<div class="f"><label class="faint">Notes</label><textarea id="cn" class="boxed" rows="8" placeholder="Call notes — use [[links]] to reference tasks, docs, contacts" style="border-radius:12px;padding:10px 12px"></textarea></div>':''}</div>`;
  const track=k=>call.local.getTracks().find(t=>t.kind===k);
  const tog=(id,k,on,off)=>{$(id).onclick=()=>{const t=track(k);if(!t)return;t.enabled=!t.enabled;$(id).textContent=t.enabled?on:off}};
  tog('#mic','audio','🎤 Mute','🎤 Unmute');tog('#cam','video','📷 Camera off','📷 Camera on');
  $('#cp').onclick=()=>{navigator.clipboard?.writeText(callLink(call.room));toast('Join link copied')};
  $('#scr').onclick=async()=>{try{const s=await navigator.mediaDevices.getDisplayMedia({video:true}),t=s.getVideoTracks()[0],old=track('video');
    Object.values(call.pcs).forEach(pc=>pc.getSenders().find(x=>x.track&&x.track.kind==='video')?.replaceTrack(t));
    call.local.addTrack(t);if(old)call.local.removeTrack(old);t.onended=()=>{if(old){Object.values(call.pcs).forEach(pc=>pc.getSenders().find(x=>x.track===t)?.replaceTrack(old));call.local.addTrack(old)}call.local.removeTrack(t);renderTiles()};renderTiles()}catch(e){}};
  $('#rec').onclick=toggleRec;$('#leave').onclick=leaveCall;if(call.rec)$('#rec').textContent='⏹ Stop recording';
  if(call.itemId){api('GET','/items/'+call.itemId).then(it=>{if($('#cn'))$('#cn').value=it.body;});let tm;
    $('#cn').oninput=()=>{const v=$('#cn').value,iid=call.itemId;clearTimeout(tm);tm=setTimeout(()=>api('PUT','/items/'+iid,{body:v}),500)}}
  call.tiles={};renderTiles();
}
function renderTiles(){
  const box=$('#tiles');if(!box||!call)return;
  const want={me:[call.local,localStorage.name+' (you)',true],...Object.fromEntries(Object.entries(call.streams).map(([k,s])=>[k,[s,call.names[k]||'guest',false]]))};
  Object.keys(call.tiles).filter(k=>!want[k]).forEach(k=>{call.tiles[k].remove();delete call.tiles[k]});
  for(const[k,[s,name,mute]]of Object.entries(want)){let t=call.tiles[k];
    if(!t){t=call.tiles[k]=document.createElement('div');t.className='tile';t.innerHTML='<video autoplay playsinline></video><span></span>';box.appendChild(t)}
    const vd=t.querySelector('video');if(vd.srcObject!==s)vd.srcObject=s;vd.muted=mute;t.querySelector('span').textContent=name}
}
function mixIn(pid){if(call.recSrc[pid]||!call.streams[pid]||!call.streams[pid].getAudioTracks().length)return;
  call.recSrc[pid]=call.ac.createMediaStreamSource(call.streams[pid]);call.recSrc[pid].connect(call.dest)}
async function toggleRec(){
  if(call.rec){call.rec.stop();return}
  if(!call.itemId)return toast('Recording needs a call saved on this server');
  call.ac=new AudioContext();call.dest=call.ac.createMediaStreamDestination();call.recSrc={};
  if(call.local.getAudioTracks().length)call.ac.createMediaStreamSource(new MediaStream(call.local.getAudioTracks())).connect(call.dest);
  Object.keys(call.streams).forEach(mixIn);
  const chunks=[];call.rec=new MediaRecorder(call.dest.stream);call.rec.ondataavailable=e=>chunks.push(e.data);
  call.rec.onstop=async()=>{call.rec=null;call.ac.close();if($('#rec'))$('#rec').textContent='⏺ Record audio';
    await fetch(`/api/calls/${call.itemId}/recording`,{method:'POST',body:new Blob(chunks,{type:'audio/webm'})});toast('Recording saved to the call')};
  call.rec.start();$('#rec').textContent='⏹ Stop recording';
}
async function leaveCall(){
  const c=call;if(c.rec){const done=new Promise(r=>c.rec.addEventListener('stop',()=>setTimeout(r,500)));c.rec.stop();await done}
  clearInterval(c.timer);clearInterval(c.clock);Object.values(c.pcs).forEach(pc=>pc.close());c.local.getTracks().forEach(t=>t.stop());
  await api('POST',`/rooms/${c.room}/leave`,{id:c.id});
  if(c.itemId){const mins=Math.max(1,Math.round((Date.now()-c.start)/6e4));
    const left=(await api('GET',`/rooms/${c.room}/poll?id=none`)).peers.length;
    await api('PUT','/items/'+c.itemId,{data:{status:left?'live':'ended',duration:String(mins)}})}
  call=null;nav('calls',c.itemId||null);
}
window.addEventListener('beforeunload',()=>{if(call)navigator.sendBeacon(`/api/rooms/${call.room}/leave`,JSON.stringify({id:call.id}))});

/* ---------- settings ---------- */
const PRESETS={gmail:{imap_host:'imap.gmail.com',imap_port:993,imap_security:'ssl',smtp_host:'smtp.gmail.com',smtp_port:465,smtp_security:'ssl'},
  outlook:{imap_host:'outlook.office365.com',imap_port:993,imap_security:'ssl',smtp_host:'smtp.office365.com',smtp_port:587,smtp_security:'starttls'},
  icloud:{imap_host:'imap.mail.me.com',imap_port:993,imap_security:'ssl',smtp_host:'smtp.mail.me.com',smtp_port:587,smtp_security:'starttls'},
  yahoo:{imap_host:'imap.mail.yahoo.com',imap_port:993,imap_security:'ssl',smtp_host:'smtp.mail.yahoo.com',smtp_port:465,smtp_security:'ssl'}};
const TZ=()=>Intl.DateTimeFormat().resolvedOptions().timeZone;
const CALDAV_PRESETS={icloud:'https://caldav.icloud.com',fastmail:'https://caldav.fastmail.com/dav/',nextcloud:'https://YOUR-SERVER/remote.php/dav',other:''};
async function settingsPage(host,ok){
  const [st,upd]=await Promise.all([api('GET','/settings'),api('GET','/update')]);if(!ok())return;
  S.upd=upd;const e=st.email||{},feeds=st.feeds||[];
  setBar('<b>Settings</b>');
  const f=(k,l,t='text')=>`<div class="f"><label>${l}</label><input id="e_${k}" type="${t}" value="${esc(e[k]??'')}"></div>`;
  const sel=(id,opts,cur)=>`<select id="${id}">${opts.map(o=>`<option ${cur===o?'selected':''}>${o}</option>`).join('')}</select>`;
  host.innerHTML=`<div class="wrap">
   <section class="sec card" id="sec-google"><h3>Google — Gmail &amp; Calendar</h3><div class="sub">Sign in once to sync mail and your calendar, both ways.</div><div id="gsec"></div></section>
   <section class="sec card" id="sec-caldav"><h3>Apple Calendar (iCloud) &amp; CalDAV</h3><div class="sub">Two-way sync with iCloud, Fastmail, Nextcloud and other CalDAV servers.</div><div id="dsec"></div>
     <div class="f" style="margin-top:14px"><label>New events you create here go to</label><select id="tgt_sel">${[['auto','Automatic (Google if connected, else iCloud/CalDAV)'],['google','Google Calendar'],['caldav','iCloud / CalDAV'],['local','Stay local only']].map(([v,l])=>`<option value="${v}" ${(st.calendar_target||'auto')===v?'selected':''}>${l}</option>`).join('')}</select></div></section>
   <section class="sec card" id="sec-email"><h3>Other email (IMAP / SMTP)</h3>${st.google?.connected&&st.google.mail?'<div class="note">Gmail is connected above, so mail sync and sending use Google. This account is used only if you turn Google mail sync off.</div>':''}
     <div class="sub">Gmail, iCloud, Yahoo and most providers need an <b>app password</b> instead of your normal password. Credentials stay in the local database on this computer.</div>
     <div class="row">Preset: ${Object.keys(PRESETS).map(p=>`<button class="btn sm" data-p="${p}">${p}</button>`).join('')}</div>
     <div style="max-width:520px">${f('name','Your name')}${f('address','Email address','email')}${f('username','Username (blank = address)')}
     <div class="f"><label>Password ${e.has_password?'(saved — leave blank to keep)':''}</label><input id="e_password" type="password"></div>
     ${f('imap_host','IMAP server')}${f('imap_port','IMAP port','number')}<div class="f"><label>IMAP security</label>${sel('e_imap_security',['ssl','starttls','none'],e.imap_security||'ssl')}</div>
     ${f('smtp_host','SMTP server')}${f('smtp_port','SMTP port','number')}<div class="f"><label>SMTP security</label>${sel('e_smtp_security',['ssl','starttls','none'],e.smtp_security||'starttls')}</div>
     <div class="row"><button class="btn dark" id="esave">Save &amp; sync</button><span id="emsg"></span></div>
     ${st.email_state?.synced?`<div class="faint">Last synced ${new Date(st.email_state.synced*1000).toLocaleString()} · auto-sync every 5 min while the app runs</div>`:''}</div></section>
   <section class="sec card" id="sec-feeds"><h3>Calendar subscriptions</h3><div class="sub">Read-only iCal / webcal feeds — Outlook, schedules, or an Apple Calendar shared as “Public Calendar”. Refreshed every 30 minutes.</div>
     <div id="feeds">${feeds.map(x=>`<div class="row"><input class="fn" style="width:150px" placeholder="Name" value="${esc(x.name)}"><input class="fu" style="flex:1;min-width:200px" placeholder="https://…/basic.ics" value="${esc(x.url)}"><button class="ib" data-rm>${I('x',16)}</button></div>`).join('')}</div>
     <div class="row"><button class="btn sm" id="addfeed">${I('plus',14)} Add calendar</button><button class="btn dark sm" id="savefeeds">Save &amp; sync calendars</button><span id="fmsg"></span></div>
     <div class="row" style="margin-top:14px"><span class="muted">Import .ics</span><input type="file" id="icsfile" accept=".ics,text/calendar" style="width:auto"><a class="lnk" href="/api/calendar/export.ics" download>Export all events (.ics)</a></div></section>
   <section class="sec card" id="sec-updates"><h3>Updates</h3><div id="upd"></div></section>
   <section class="sec card" id="sec-misc"><h3>Reminders &amp; data</h3><div class="row"><button class="btn" id="notif">Enable desktop reminders</button><span class="faint">Events notify 10 minutes before they start while the app is open.</span></div>
     <div class="faint">Your data lives in <code>~/.macro-local</code> — copy that folder to back up or move it.</div></section></div>`;
  googleSection(st.google||{});caldavSection(st.caldav||{});updatesSection();
  $('#tgt_sel').onchange=ev=>api('POST','/caldav/target',{target:ev.target.value});
  host.querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>{Object.entries(PRESETS[b.dataset.p]).forEach(([k,x])=>$('#e_'+k).value=x)});
  const collect=()=>[...host.querySelectorAll('#feeds .row')].map(r=>({name:r.querySelector('.fn').value,url:r.querySelector('.fu').value.trim()}));
  $('#esave').onclick=async()=>{const em={};['name','address','username','password','imap_host','imap_port','imap_security','smtp_host','smtp_port','smtp_security'].forEach(k=>em[k]=$('#e_'+k).value);
    await api('POST','/settings',{email:em});$('#emsg').className='';$('#emsg').textContent=' Syncing…';const r=await api('POST','/email/sync',{});
    $('#emsg').className=r.error?'err':'';$('#emsg').textContent=r.error?' '+r.error:` Connected — ${r.new} message(s) fetched`};
  const feedRow=()=>{const d=document.createElement('div');d.className='row';d.innerHTML=`<input class="fn" style="width:150px" placeholder="Name"><input class="fu" style="flex:1;min-width:200px" placeholder="https://…/basic.ics"><button class="ib">${I('x',16)}</button>`;d.querySelector('button').onclick=()=>d.remove();return d};
  $('#addfeed').onclick=()=>$('#feeds').appendChild(feedRow());
  host.querySelectorAll('[data-rm]').forEach(b=>b.onclick=()=>b.parentElement.remove());
  $('#savefeeds').onclick=async()=>{await api('POST','/settings',{feeds:collect()});$('#fmsg').textContent=' Syncing…';const r=await api('POST','/calendar/sync',{});
    $('#fmsg').className=r.errors.length?'err':'';$('#fmsg').textContent=r.errors.length?' '+r.errors.join('; '):` ${r.events} events synced`};
  $('#icsfile').onchange=async ev=>{const t=await ev.target.files[0].text();const r=await api('POST','/calendar/import',{ics:t});toast(r.imported+' events imported')};
  $('#notif').onclick=async()=>{if(!window.Notification)return toast('Notifications not supported here');toast('Permission: '+await Notification.requestPermission())};
}
function googleSection(g){
  const box=$('#gsec');if(!box)return;
  if(g.connected){
    box.innerHTML=`<div class="note" style="color:var(--ink)">✅ Connected as <b>${esc(g.email)}</b></div>
     <div class="row"><label><input type="checkbox" id="g_mail" ${g.mail?'checked':''}> Sync Gmail (inbox + sent, send mail, read-state) — every 5 min</label></div>
     <div class="row"><label><input type="checkbox" id="g_cal" ${g.calendar?'checked':''}> Two-way Google Calendar sync (primary) — pull every 10 min, edits pushed immediately</label></div>
     ${g.error?`<div class="err">Last error: ${esc(g.error)}</div>`:''}
     <div class="row"><button class="btn dark" id="g_sync">Sync now</button><button class="btn danger" id="g_off">Disconnect</button><span id="g_msg"></span></div>`;
    $('#g_mail').onchange=e=>api('POST','/google/config',{mail:e.target.checked});
    $('#g_cal').onchange=e=>api('POST','/google/config',{calendar:e.target.checked});
    $('#g_sync').onclick=async()=>{$('#g_msg').textContent=' Syncing…';const r=await api('POST','/google/sync',{});
      $('#g_msg').className=r.error?'err':'';$('#g_msg').textContent=r.error?' '+r.error:` Done — ${r.mail.new} new message(s), ${r.calendar.events} calendar events`};
    $('#g_off').onclick=async()=>{if(confirm('Disconnect Google? Your synced mail and events stay in Macro Local.')){await api('POST','/google/disconnect',{});render()}};
    return;
  }
  box.innerHTML=`<details ${g.has_secret?'':'open'}><summary style="cursor:pointer"><b>One-time setup</b> (about 5 minutes) — you create your own private Google "app" so nobody else sees your data</summary>
   <ol style="line-height:1.8">
    <li>Open <a class="lnk" href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noopener">Google Cloud Console → New project</a> (any name).</li>
    <li>Enable the APIs: <a class="lnk" href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noopener">Gmail API</a> and <a class="lnk" href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com" target="_blank" rel="noopener">Google Calendar API</a> (click <i>Enable</i> on each).</li>
    <li><a class="lnk" href="https://console.cloud.google.com/auth/overview" target="_blank" rel="noopener">Google Auth platform</a> → <i>Get started</i>: app name “Macro Local”, audience <b>External</b>, your email as contact. Then under <i>Audience</i> click <b>Publish app</b> (otherwise Google expires your connection every 7 days). Google will warn the app is unverified — that's fine, it's yours.</li>
    <li><a class="lnk" href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener">Clients</a> → <i>Create client</i> → type <b>Desktop app</b>. Copy the Client ID and Client secret below.</li>
   </ol></details>
   <div style="max-width:520px"><div class="f"><label>Client ID</label><input id="g_id" value="${esc(g.client_id||'')}" placeholder="1234…apps.googleusercontent.com"></div>
   <div class="f"><label>Client secret ${g.has_secret?'(saved — leave blank to keep)':''}</label><input id="g_sec" type="password"></div></div>
   <div class="row"><button class="btn dark" id="g_go">Connect Google</button><span id="g_msg"></span></div>
   <div class="note">Google will show “Google hasn't verified this app” → click <b>Advanced</b> → <b>Go to Macro Local (unsafe)</b>, then allow Gmail and Calendar. Tokens stay on this computer.</div>`;
  $('#g_go').onclick=async()=>{const m=$('#g_msg');m.className='';
    if(!$('#g_id').value.trim()||(!g.has_secret&&!$('#g_sec').value)){m.textContent=' Enter the client ID and secret first.';m.className='err';return}
    await api('POST','/google/config',{client_id:$('#g_id').value,client_secret:$('#g_sec').value,timezone:TZ()});
    const r=await api('POST','/google/connect',{timezone:TZ()});if(r.error){m.textContent=' '+r.error;m.className='err';return}
    window.open(r.url,'_blank');m.innerHTML=` Waiting for Google… <a class="lnk" href="${esc(r.url)}" target="_blank" rel="noopener">open sign-in again</a>`;
    clearTimers();let tries=0;
    every(async()=>{const st=await api('GET','/settings');
      if(st.google.connected){clearTimers();toast('Google connected: '+st.google.email);if(S.mod==='settings')render()}
      else if(++tries>150)clearTimers()},2000)};
}
function caldavSection(c){
  const box=$('#dsec');if(!box)return;
  if(c.connected){
    box.innerHTML=`<div class="note" style="color:var(--ink)">✅ Connected as <b>${esc(c.username)}</b> (${esc(c.url)})</div>
     <div class="f"><label>Calendars to sync</label>${c.calendars.map(x=>`<div class="row" style="margin:2px 0"><label><input type="checkbox" class="dc" value="${esc(x.href)}" ${x.selected?'checked':''}> ${esc(x.name)}</label>
       <label class="faint"><input type="radio" name="dd" value="${esc(x.href)}" ${c.default===x.href?'checked':''}> new events go here</label></div>`).join('')}</div>
     ${c.error?`<div class="err">Last error: ${esc(c.error)}</div>`:''}
     <div class="row"><button class="btn dark" id="d_save">Save &amp; sync now</button><button class="btn danger" id="d_off">Disconnect</button><span id="d_msg"></span></div>
     <div class="faint">Pulled every 10 min; your edits are pushed immediately. Alarms, attendees and other details set in Apple Calendar are preserved when you edit an event here.</div>`;
    $('#d_save').onclick=async()=>{const m=$('#d_msg');m.className='';m.textContent=' Syncing…';
      const sel=[...box.querySelectorAll('.dc:checked')].map(x=>x.value),def=(box.querySelector('[name=dd]:checked')||{}).value;
      await api('POST','/caldav/calendars',{selected:sel,default:def});const r=await api('POST','/caldav/sync',{});
      m.className=r.error?'err':'';m.textContent=r.error?' '+r.error:` Done — ${r.events} events`};
    $('#d_off').onclick=async()=>{if(confirm('Disconnect this calendar? Events already synced stay in Macro Local.')){await api('POST','/caldav/disconnect',{});render()}};
    return;
  }
  box.innerHTML=`<div class="note">For iCloud, create an <b>app-specific password</b>: <a class="lnk" href="https://account.apple.com/account/manage" target="_blank" rel="noopener">Apple Account</a> → Sign-In and Security → App-Specific Passwords. Your normal Apple ID password will not work.</div>
   <div class="row">Preset: ${Object.keys(CALDAV_PRESETS).map(p=>`<button class="btn sm" data-dp="${p}">${p}</button>`).join('')}</div>
   <div style="max-width:520px"><div class="f"><label>Server URL</label><input id="d_url" value="${esc(c.url||CALDAV_PRESETS.icloud)}"></div>
   <div class="f"><label>Username (iCloud: your Apple ID email)</label><input id="d_user" value="${esc(c.username||'')}"></div>
   <div class="f"><label>Password (iCloud: app-specific password)</label><input id="d_pw" type="password"></div></div>
   <div class="row"><button class="btn dark" id="d_go">Connect</button><span id="d_msg"></span></div>`;
  box.querySelectorAll('[data-dp]').forEach(b=>b.onclick=()=>$('#d_url').value=CALDAV_PRESETS[b.dataset.dp]);
  $('#d_go').onclick=async()=>{const m=$('#d_msg');m.className='';m.textContent=' Connecting…';
    const r=await api('POST','/caldav/connect',{url:$('#d_url').value,username:$('#d_user').value,password:$('#d_pw').value,timezone:TZ()});
    if(r.error){m.className='err';m.textContent=' '+r.error;return}
    m.textContent=' Syncing…';const sy=await api('POST','/caldav/sync',{});toast(sy.error?sy.error:`Connected — ${sy.events} events synced`);render()};
}

/* ---------- updates ---------- */
async function loadUpdate(){try{S.upd=await api('GET','/update')}catch(e){}renderUpdate()}
function renderUpdate(){
  const u=S.upd,el=$('#update');if(!u)return;
  const dismissed=localStorage.dismissedUpdate===u.latest;
  const show=u.available&&!dismissed&&(u.ready||!u.can_install);
  el.classList.toggle('show',!!show);if(!show){el.innerHTML='';return}
  el.innerHTML=u.ready?`<span>${I('download',16)}</span><span class="grow"><b>Macro Local ${esc(u.latest)}</b> is ready — it installs automatically when you quit, or restart now.</span><button class="btn sm dark" id="u_go">Restart &amp; update</button><button class="btn sm" id="u_later">Later</button>`
    :`<span>${I('download',16)}</span><span class="grow"><b>Macro Local ${esc(u.latest)}</b> is available.</span><a class="btn sm dark" href="${esc(u.page)}" target="_blank" rel="noopener">Download</a><button class="btn sm" id="u_later">Later</button>`;
  $('#u_later').onclick=()=>{localStorage.dismissedUpdate=u.latest;renderUpdate()};
  if($('#u_go'))$('#u_go').onclick=installUpdate;
}
async function installUpdate(){
  if(call&&!confirm('You are in a call — restarting will end it. Continue?'))return;
  const r=await api('POST','/update/install',{});if(r.error)return toast(r.error);toast('Updating — Macro Local will reopen in a moment…');
}
function updatesSection(){
  const u=S.upd,box=$('#upd');if(!box||!u)return;
  const status=u.error?`<span class="err">Couldn't check: ${esc(u.error)}</span>`:u.available?(u.ready?`<b>${esc(u.latest)}</b> is downloaded and ready.`:`<b>${esc(u.latest)}</b> is available.`):`You're up to date.`;
  box.innerHTML=`<div class="sub">Version <b>${esc(u.current)}</b>${u.packaged?'':' · running from source'}${u.checked?` · last checked ${new Date(u.checked*1000).toLocaleString()}`:''}</div>
   <div class="row">${status}</div>
   <div class="row"><label><input type="checkbox" id="u_auto" ${u.auto?'checked':''}> Download updates automatically and install them when I quit</label></div>
   <div class="row"><button class="btn" id="u_check">Check for updates</button>${u.available&&u.can_install?`<button class="btn dark" id="u_install">${u.ready?'Restart & update now':'Download & install'}</button>`:''}${u.available&&!u.can_install&&u.page?`<a class="btn dark" href="${esc(u.page)}" target="_blank" rel="noopener">Download ${esc(u.latest)}</a>`:''}<span id="u_msg" class="faint"></span></div>
   ${u.notes?`<div class="faint" style="white-space:pre-wrap">${esc(u.notes)}</div>`:''}`;
  $('#u_auto').onchange=async e=>{S.upd=await api('POST','/update/config',{auto:e.target.checked})};
  $('#u_check').onclick=async()=>{$('#u_msg').textContent=' Checking…';S.upd=await api('POST','/update/check',{});updatesSection();renderUpdate()};
  if($('#u_install'))$('#u_install').onclick=async()=>{$('#u_msg').textContent=' Downloading…';installUpdate()};
}

/* ---------- search palette + new menu ---------- */
let sres=[],sidx=0;
function openPalette(){$('#palette').classList.add('open');$('#q').value='';$('#res').innerHTML='<div class="pempty">Type to search everything</div>';sres=[];$('#q').focus()}
function closePalette(){$('#palette').classList.remove('open')}
$('#palette').onclick=e=>{if(e.target.id==='palette')closePalette()};
let st;$('#q').oninput=e=>{clearTimeout(st);st=setTimeout(async()=>{const q=e.target.value;if(!q.trim()){$('#res').innerHTML='<div class="pempty">Type to search everything</div>';sres=[];return}
  sres=await api('GET','/search?q='+encodeURIComponent(q));sidx=0;paintRes()},150)};
function paintRes(){
  $('#res').innerHTML=sres.map((r,i)=>`<div class="prow ${i===sidx?'sel':''}" data-i="${i}"><span class="ico">${I(r.kind==='item'?TYPE_ICON[r.type]||'file':'chat',16)}</span><span class="txt"><b style="font-weight:500">${esc(r.title||'Untitled')}</b> <span class="faint">${esc(r.snippet||(r.channel?'#chat':''))}</span></span><span class="meta">${esc(r.kind==='item'?TYPES[r.type]?.one||r.type:'Chat')}</span></div>`).join('')||'<div class="pempty">No results</div>';
  $('#res').querySelectorAll('.prow').forEach(r=>{r.onclick=()=>pick(+r.dataset.i)})}
function pick(i){const r=sres[i];if(!r)return;closePalette();if(r.kind==='item')openItem(r.id);else nav('chat',r.channel)}
$('#q').onkeydown=e=>{if(e.key==='Escape')closePalette();else if(e.key==='ArrowDown'){sidx=Math.min(sidx+1,sres.length-1);paintRes();e.preventDefault()}
  else if(e.key==='ArrowUp'){sidx=Math.max(sidx-1,0);paintRes();e.preventDefault()}else if(e.key==='Enter')pick(sidx)};
document.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette()}
  else if(e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)){e.preventDefault();openPalette()}
  else if(e.key==='Escape'){closePalette();closeMenu()}});
function closeMenu(){$('#menu').classList.remove('open')}
function newMenu(anchor){
  const m=$('#menu'),items=[['file','Doc',()=>newItem('doc')],['check','Task',()=>newItem('task')],['cal','Event',newEventNow],['mail','Email',composeNew],
    ['user','Contact',()=>newItem('contact')],['building','Company',()=>newItem('company')],['briefcase','Deal',()=>newItem('deal')],['video','Call',startCall],['hash','Channel',async()=>{const n=prompt('Channel name');if(n){const r=await api('POST','/channels',{name:n});nav('chat',r.id)}}]];
  m.innerHTML=items.map(([ic,l],i)=>`<div class="prow" data-i="${i}"><span class="ico">${I(ic,16)}</span><span class="txt">${l}</span></div>`).join('');
  const r=anchor.getBoundingClientRect();m.style.left=Math.min(r.right+8,innerWidth-210)+'px';m.style.top=Math.min(r.top,innerHeight-items.length*34-20)+'px';
  m.classList.add('open');m.querySelectorAll('.prow').forEach(row=>row.onclick=()=>{closeMenu();items[+row.dataset.i][2]()});
  setTimeout(()=>document.addEventListener('click',closeMenu,{once:true}),0);
}

/* ---------- boot ---------- */
fetch('/api/ping').catch(()=>{});setInterval(()=>fetch('/api/ping').catch(()=>{}),15000);
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
parseHash();document.body.classList.toggle('mob-panel',matchMedia('(max-width:820px)').matches&&!S.id);
render();setTimeout(loadUpdate,2500);setInterval(loadUpdate,5*60e3);
