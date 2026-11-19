import { useState, useEffect, useCallback, useRef } from "react";

// Credit Nexus — credit research dashboard. All data comes from the local backend (/api/*).
const C={bg:"#0b0f14",card:"#121821",card2:"#18212c",bd:"#243041",tx:"#e6edf3",mu:"#94a3b8",dim:"#64748b",ac:"#14b8a6",ok:"#22c55e",err:"#ef4444",warn:"#f59e0b",vio:"#a78bfa",blue:"#60a5fa"};
const SYM={INR:"₹",USD:"$",GBP:"£",EUR:"€",JPY:"¥",KRW:"₩",CNY:"¥",SGD:"S$",HKD:"HK$",AED:"AED ",SAR:"SAR ",CHF:"CHF ",CAD:"C$",AUD:"A$"};

// Format a raw number in the company's reporting currency. INR uses Crore/Lakh.
function money(v,cur){
  if(v===null||v===undefined||v==="")return "—";
  const n=typeof v==="number"?v:parseFloat(String(v).replace(/[^0-9.\-eE]/g,""));
  if(!isFinite(n))return String(v);
  const s=SYM[cur]??(cur?cur+" ":""),a=Math.abs(n),sg=n<0?"-":"";
  if(cur==="INR"){if(a>=1e7)return `${sg}${s}${(a/1e7).toLocaleString("en-IN",{maximumFractionDigits:0})} Cr`;if(a>=1e5)return `${sg}${s}${(a/1e5).toFixed(1)} L`;return `${sg}${s}${a.toLocaleString("en-IN",{maximumFractionDigits:2})}`}
  if(a>=1e12)return `${sg}${s}${(a/1e12).toFixed(2)}T`;if(a>=1e9)return `${sg}${s}${(a/1e9).toFixed(2)}B`;if(a>=1e6)return `${sg}${s}${(a/1e6).toFixed(1)}M`;if(a>=1e3)return `${sg}${s}${(a/1e3).toFixed(0)}K`;
  return `${sg}${s}${a.toFixed(2)}`;
}
const num=v=>{if(v===null||v===undefined||v==="")return "—";const n=Number(v);return isFinite(n)?(Math.abs(n)>=1e6?n.toLocaleString(undefined,{maximumFractionDigits:0}):n.toLocaleString(undefined,{maximumFractionDigits:2})):String(v)};

function calcR(d){if(!d)return null;const n=v=>{const p=parseFloat(String(v||0).replace(/[^0-9.\-]/g,""));return isFinite(p)?p:0};const r=(a,b)=>b===0?null:Number((a/b).toFixed(2));const pct=(a,b)=>b===0?null:Number(((a/b)*100).toFixed(1));const rev=n(d.rev),cogs=n(d.cogs),ebitda=n(d.ebitda),ebit=n(d.ebit),ni=n(d.ni),cash=n(d.cash),recv=n(d.recv),inv=n(d.inv),pay=n(d.pay),td=n(d.debt),std=n(d.stDebt),eq=n(d.equity),ie=n(d.intExp),ca=n(d.ca),cl=n(d.cl),ta=n(d.assets),re=n(d.re),ocf=n(d.ocf),capex=n(d.capex),mk=n(d.mktCap);const fcf=ocf-capex,nd=td-cash,wc=ca-cl,gp=rev-cogs;
return{M:[{c:"Leverage",I:[{l:"ND/EBITDA",v:r(nd,ebitda),u:"x",g:v=>v<3},{l:"D/E",v:r(td,eq),u:"x",g:v=>v<2},{l:"D/A",v:r(td,ta),u:"x",g:v=>v<.5}]},{c:"Coverage",I:[{l:"EBIT/Int",v:r(ebit,ie),u:"x",g:v=>v>3},{l:"EBITDA/Int",v:r(ebitda,ie),u:"x",g:v=>v>4},{l:"DSCR",v:ie?r(fcf,ie):null,u:"x",g:v=>v>1.25}]},{c:"Liquidity",I:[{l:"Current",v:r(ca,cl),u:"x",g:v=>v>=1.5},{l:"Quick",v:cl?r(cash+recv,cl):null,u:"x",g:v=>v>=1}]},{c:"Profitability",I:[{l:"Gross%",v:pct(gp,rev),u:"%",g:v=>v>25},{l:"EBITDA%",v:pct(ebitda,rev),u:"%",g:v=>v>15},{l:"Net%",v:pct(ni,rev),u:"%",g:v=>v>8},{l:"ROE",v:pct(ni,eq),u:"%",g:v=>v>12},{l:"ROCE",v:pct(ebit,ta-cl),u:"%",g:v=>v>12}]},{c:"Valuation",I:[{l:"EV/EBITDA",v:ebitda?r(mk+nd,ebitda):null,u:"x",g:()=>true},{l:"P/E",v:ni?r(mk,ni):null,u:"x",g:()=>true},{l:"P/BV",v:eq?r(mk,eq):null,u:"x",g:()=>true}]},{c:"Efficiency",I:[{l:"InvDays",v:cogs?Math.round((inv/cogs)*365):null,u:"d",g:v=>v<60},{l:"RecvDays",v:rev?Math.round((recv/rev)*365):null,u:"d",g:v=>v<45}]},{c:"Distress",I:[{l:"Altman Z",v:ta?Number((1.2*(wc/ta)+1.4*(re/ta)+3.3*(ebit/ta)+.6*(td?mk/td:0)+rev/ta).toFixed(2)):null,u:"",g:v=>v>2.99}]}],F:(()=>{const fl=[];if(fcf<0)fl.push("Negative FCF");const nde=r(nd,ebitda);if(nde>5)fl.push(`ND/EBITDA ${nde}x`);if(r(ebit,ie)!=null&&r(ebit,ie)<1.5)fl.push(`Coverage ${r(ebit,ie)}x`);if(r(ca,cl)!=null&&r(ca,cl)<1)fl.push("Current<1");return fl})()}}

// ── UI atoms ──
const Bd=({children,c=C.blue})=><span style={{display:"inline-block",padding:"2px 8px",borderRadius:4,background:c+"22",color:c,fontSize:10,fontWeight:700,marginRight:4}}>{children}</span>;
const Card=({title,children,span=1,ai,real})=>(<div style={{background:C.card,border:`1px solid ${C.bd}`,borderRadius:8,padding:"14px 16px",gridColumn:`span ${span}`,minWidth:0}}>
  {title&&<div style={{display:"flex",justifyContent:"space-between",alignItems:"center",borderBottom:`1px solid ${C.bd}`,paddingBottom:6,marginBottom:8}}><span style={{fontSize:10,fontWeight:700,color:C.dim,textTransform:"uppercase",letterSpacing:1.2}}>{title}</span>{ai&&<Bd c={C.vio}>AI — verify</Bd>}{real&&<Bd c={C.ok}>LIVE DATA</Bd>}</div>}{children}</div>);
const Mt=({l,v,c})=><div><div style={{fontSize:9,color:C.dim,textTransform:"uppercase"}}>{l}</div><div style={{fontSize:15,fontWeight:700,color:c||C.tx,fontFamily:"ui-monospace,monospace",marginTop:2,wordBreak:"break-word"}}>{v??"—"}</div></div>;
const Rw=({l,v,c})=>(v===undefined||v===null||v===""||v==="—")?null:<div style={{display:"flex",justifyContent:"space-between",gap:12,padding:"4px 0",borderBottom:`1px solid ${C.bd}55`,fontSize:12}}><span style={{color:C.mu}}>{l}</span><span style={{color:c||C.tx,fontFamily:"ui-monospace,monospace",textAlign:"right",wordBreak:"break-word"}}>{String(v)}</span></div>;
// Shown on AI cards: figures the AI wrote that were not in the real data (removed in strict mode).
const Unv=({ins,sec})=>{const u=(ins?._unverified||[]).filter(v=>String(v.field).startsWith(sec));if(!u.length)return null;return <div style={{fontSize:11,color:C.warn,background:C.warn+"11",border:`1px solid ${C.warn}44`,borderRadius:6,padding:"6px 8px",marginBottom:8,lineHeight:1.5}} title={u.map(v=>`${v.field}: ${v.value}`).join("\n")}>⚠ {u.length} figure{u.length>1?"s":""} the AI wrote could not be found in the source data and {ins._strict?"were removed":"are unverified"} ({u.slice(0,4).map(v=>v.value).join(", ")}{u.length>4?"…":""}).</div>};
const Empty=({children})=><div style={{color:C.dim,fontSize:12,padding:"8px 0"}}>{children}</div>;
const Grid=({cols=2,children})=><div className="cn-grid" style={{display:"grid",gridTemplateColumns:`repeat(${cols},minmax(0,1fr))`,gap:10}}>{children}</div>;
function Gauge({score,grade}){const s=Number(score)||0,g=s>=70?C.ok:s>=40?C.warn:C.err,ci=2*Math.PI*46;return <svg width="110" height="110" viewBox="0 0 110 110" role="img" aria-label={`Score ${s}`}><circle cx="55" cy="55" r="46" fill="none" stroke={C.card2} strokeWidth="7"/><circle cx="55" cy="55" r="46" fill="none" stroke={g} strokeWidth="7" strokeLinecap="round" strokeDasharray={ci} strokeDashoffset={ci-(s/100)*ci} transform="rotate(-90 55 55)"/><text x="55" y="52" textAnchor="middle" fill={g} fontSize="24" fontWeight="800" fontFamily="monospace">{s}</text><text x="55" y="70" textAnchor="middle" fill={C.mu} fontSize="12" fontWeight="600">{grade}</text></svg>}
const recC=r=>r==="APPROVE"?C.ok:r==="DECLINE"?C.err:C.warn;

let MODE={public:false};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
// Every request: hard timeout, automatic retry on connection drops, and a message that says what actually happened.
async function getJSON(url,{timeout=100000,retries=2}={}){
  let lastErr;
  for(let i=0;i<=retries;i++){
    const ctl=new AbortController();const t=setTimeout(()=>ctl.abort(),timeout);
    try{
      const r=await fetch(url,{signal:ctl.signal});
      let body=null;try{body=await r.json()}catch{}
      if(!r.ok){
        if(r.status>=502&&r.status<=504&&i<retries){await sleep(3000*(i+1));continue}  // host waking up / gateway hiccup
        throw new Error(body?.error||`Server returned HTTP ${r.status}`);
      }
      if(body===null)throw new Error("Server sent an unreadable reply");
      return body;
    }catch(e){
      lastErr=e;
      if(e.name==="AbortError"){lastErr=new Error(`No answer within ${timeout/1000} s`);if(i<retries)continue}
      else if(e instanceof TypeError){ // fetch() network failure: "Failed to fetch" / "Load failed"
        lastErr=new Error(MODE.public?"Could not reach the website server — free hosting may be waking up (up to ~1 min)":"Could not reach the Credit Nexus server on this computer — is its window still open?");
        if(i<retries){await sleep(3000*(i+1));continue}
      }
      else throw e;
    }finally{clearTimeout(t)}
  }
  throw lastErr;
}
const btn2={background:C.card2,border:`1px solid ${C.bd}`,borderRadius:6,padding:"6px 14px",color:C.tx,fontSize:11,cursor:"pointer",marginTop:8};

// AI sections all come from ONE request per company (the free AI allows one request per 30 s).
function AIBlock({ins,title,retry,children}){
  const[t,setT]=useState(0);
  useEffect(()=>{if(ins.st!=="loading")return;const s=Date.now();const h=setInterval(()=>setT(Math.round((Date.now()-s)/1000)),1000);return()=>clearInterval(h)},[ins.st]);
  if(ins.st==="loading")return <Card title={title} ai><Empty>AI analysis running… {t}s<br/><span style={{fontSize:11}}>Free AI (Pollinations) handles one request every 30 s, so this can take 30–90 s. Live-data tabs work meanwhile.</span></Empty></Card>;
  if(ins.st==="error"||!ins.data)return <Card title={title} ai><div style={{color:C.warn,fontSize:12,lineHeight:1.5}}>{ins.error||"AI analysis not available."}</div>{ins.st==="error"&&<button onClick={retry} style={btn2}>Retry</button>}</Card>;
  return children(ins.data);
}
const QUICK=[
  ["United States",[["Apple","AAPL"],["Microsoft","MSFT"],["JPMorgan","JPM"],["Exxon Mobil","XOM"]]],
  ["United Kingdom",[["HSBC","HSBA.L"],["BP","BP.L"],["Unilever","ULVR.L"],["AstraZeneca","AZN.L"]]],
  ["India",[["TCS","TCS.NS"],["Reliance","RELIANCE.NS"],["HDFC Bank","HDFCBANK.NS"],["Infosys","INFY.NS"]]],
];
const MARKETS=[["","US, UK & India"],["us","United States"],["uk","United Kingdom"],["in","India"]];
const TABS=["overview","financials","ratios","credit","stress","warnings","outlook","debt","shareholding","team","comps","risk","industry","news"];

export default function App(){
  const[status,setStatus]=useState(null);const[statusErr,setStatusErr]=useState(null);
  const[q,setQ]=useState("");const[co,setCo]=useState("");const[mkt,setMkt]=useState("");
  const[busy,setBusy]=useState(false);const[d,setD]=useState(null);const[err,setErr]=useState(null);
  const[tab,setTab]=useState("overview");
  const[ins,setIns]=useState({st:"idle"});
  const reqId=useRef(0);
  const loadIns=useCallback(async(c,id)=>{
    setIns({st:"loading"});
    try{const r=await getJSON(`/api/insights?company=${encodeURIComponent(c)}`,{timeout:300000,retries:1});if(id===reqId.current)setIns(r.data?{st:"ok",data:r.data}:{st:"error",error:r.error})}
    catch(e){if(id===reqId.current)setIns({st:"error",error:e.message})}
  },[]);

  useEffect(()=>{getJSON("/api/status",{timeout:30000,retries:3}).then(st=>{MODE.public=!!st.public;setStatus(st)}).catch(e=>setStatusErr(e.message))},[]);

  const run=useCallback(async(name,fresh=false,market,exact=false)=>{
    const mk=market===undefined?mkt:market;
    const c=(name??q).trim();if(!c)return;setQ(c);
    const id=++reqId.current;setBusy(true);setErr(null);setD(null);setTab("overview");setIns({st:"idle"});
    try{const r=await getJSON(`/api/analyze?company=${encodeURIComponent(c)}${fresh?"&fresh=true":""}${mk?`&market=${mk}`:""}${exact?"&exact=true":""}`,{timeout:150000,retries:1});if(id===reqId.current){setD(r);setCo(c);if(r.ai_enabled&&(r.financials?.rev||r.financials?.assets))loadIns(c,id);else setIns({st:"error",error:r.ai_enabled?"No real financial data, so no AI commentary.":"AI commentary is switched off."})}}
    catch(e){if(id===reqId.current)setErr(`Analysis failed: ${e.message}. Open Health to diagnose.`)}
    finally{if(id===reqId.current)setBusy(false)}
  },[q,mkt,loadIns]);
  const retryIns=()=>loadIns(co,reqId.current);

  const f=d?.financials||{},p=d?.profile||{},h=d?.holders||{},cr=ins.data?.credit||{},rpt=d?.credit_report||{};
  const s=rpt.summary||{},dp=rpt.default_probability||{},st=rpt.stress_test||{},ew=rpt.early_warnings||[];
  const cur=f.currency||p.currency||"";const $=v=>money(v,cur);
  const est=false;

  return(<div style={{minHeight:"100vh",background:C.bg,color:C.tx,fontFamily:"system-ui,-apple-system,'Segoe UI',sans-serif"}}>
    <style>{`@media(max-width:760px){.cn-grid{grid-template-columns:1fr!important}.cn-grid>*{grid-column:auto!important}}button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid ${C.ac};outline-offset:2px}`}</style>
    <header style={{background:C.card,borderBottom:`1px solid ${C.bd}`,padding:"10px 16px",display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:8}}>
      <div><div style={{fontSize:16,fontWeight:800,letterSpacing:1}}>CREDIT <span style={{color:C.ac}}>NEXUS</span></div>
        <div style={{fontSize:10,color:C.dim}}>{status?<>AI: {status.ai_enabled?"Pollinations (free, no key)":"off"}</>:statusErr?<span style={{color:C.err}}>Server unreachable — restart START.bat</span>:"connecting…"}</div></div>
      <form onSubmit={e=>{e.preventDefault();run()}} style={{display:"flex",gap:6,flexWrap:"wrap",alignItems:"center"}}>
        <select aria-label="Market" value={mkt} onChange={e=>setMkt(e.target.value)} style={{background:C.card2,border:`1px solid ${C.bd}`,borderRadius:6,padding:"8px 6px",color:C.tx,fontSize:12}}>{MARKETS.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
        <input aria-label="Company, ticker or ISIN" value={q} onChange={e=>setQ(e.target.value)} placeholder="Company or ticker (AAPL, HSBA.L, TCS.NS)" style={{width:240,maxWidth:"60vw",background:C.card2,border:`1px solid ${C.bd}`,borderRadius:6,padding:"8px 10px",color:C.tx,fontSize:13}}/>
        <button type="submit" disabled={busy||!q.trim()} style={{background:C.ac,color:"#04201d",border:"none",borderRadius:6,padding:"8px 16px",fontWeight:800,fontSize:12,cursor:busy?"wait":"pointer",opacity:busy||!q.trim()?.6:1}}>{busy?"ANALYZING…":"ANALYZE"}</button>
        <a href="/health" style={{color:C.mu,fontSize:12}}>Health</a>
      </form>
    </header>

    {!d&&!busy&&<div style={{maxWidth:760,margin:"60px auto",padding:"0 16px",textAlign:"center"}}>
      <div style={{fontSize:20,fontWeight:800}}>Credit research in one search</div>
      <div style={{fontSize:13,color:C.mu,marginTop:6,lineHeight:1.6}}>Live financials for US, UK and Indian companies (Yahoo Finance / NSE) → deterministic credit score, stress test, default probability and early warnings. AI commentary is always labelled.</div>
      <div style={{fontSize:12,color:C.dim,marginTop:10,lineHeight:1.6}}>Numbers appear in seconds. AI sections fill in about 30–90 s later — the free AI (Pollinations, no key) takes one request every 30 s, so the app asks once per company.</div>
      {err&&<div style={{color:C.err,marginTop:16,fontSize:13}}>{err}</div>}
      <div style={{marginTop:20,display:"grid",gap:10}}>{QUICK.map(([m,list])=><div key={m}><div style={{fontSize:10,color:C.dim,textTransform:"uppercase",letterSpacing:1,marginBottom:4}}>{m}</div><div style={{display:"flex",gap:6,flexWrap:"wrap",justifyContent:"center"}}>{list.map(([n,t])=><button key={t} onClick={()=>run(t,false,"",true)} title={t} style={{...btn2,marginTop:0}}>{n} <span style={{color:C.dim}}>{t}</span></button>)}</div></div>)}</div>
    </div>}
    {busy&&<div role="status" style={{textAlign:"center",paddingTop:100,color:C.ac}}>Fetching live data for {q}… (10–40 s on first lookup)</div>}

    {d&&!busy&&<>
      {d.match?.symbol&&<div style={{padding:"8px 16px",fontSize:12,color:C.mu,display:"flex",gap:8,flexWrap:"wrap",alignItems:"center",borderBottom:`1px solid ${C.bd}`,background:C.card}}>
        <span>You searched <b style={{color:C.tx}}>“{d.match.query}”</b>{d.match.market&&<> in {d.match.market}</>} → <b style={{color:C.ac}}>{d.match.symbol}</b> · {d.match.name}{d.match.exchange&&<> · {d.match.exchange}</>} · price in {d.match.quote_currency}{d.match.statement_currency&&d.match.statement_currency!==d.match.quote_currency&&<>, statements in {d.match.statement_currency}</>}</span>
        {d.match.others?.length>0&&<><span style={{color:C.dim}}>Other listings:</span>{d.match.others.map(o=><button key={o.symbol} onClick={()=>run(o.symbol,false,"",true)} title={o.name} style={{...btn2,marginTop:0,padding:"2px 8px"}}>{o.symbol}{o.exchange&&<span style={{color:C.dim}}> · {o.exchange}</span>}</button>)}</>}
      </div>}
      <div style={{padding:"8px 16px",fontSize:11,color:C.mu,display:"flex",gap:8,flexWrap:"wrap",alignItems:"center",borderBottom:`1px solid ${C.bd}`}}>
        <span>Sources:</span>{d.sources.length?d.sources.map(x=><Bd key={x} c={C.ok}>{x}</Bd>):<Bd c={C.err}>none reachable</Bd>}{est&&<Bd c={C.vio}>financials = AI estimate</Bd>}
        {f.period&&<span>{f.period}</span>}{cur&&<span>· Currency {cur}</span>}
        {Object.entries(d.source_errors||{}).map(([k,v])=><span key={k} title={v} style={{color:C.warn}}>· {k} failed</span>)}
        {d.strict&&<Bd c={C.ac}>strict: AI figures verified</Bd>}
      </div>
      {d.freshness&&Object.keys(d.freshness).length>0&&<div style={{padding:"6px 16px",fontSize:11,color:C.mu,display:"flex",gap:10,flexWrap:"wrap",alignItems:"center",borderBottom:`1px solid ${C.bd}`}}>
        <span>Data as of —</span>
        {d.freshness.statements&&<span>Statements: <b style={{color:d.freshness.statements_stale?C.warn:C.tx}}>{d.freshness.statements}</b>{d.freshness.statements_age_days!=null&&` (${d.freshness.statements_age_days} days ago)`}</span>}
        {d.freshness.balance_sheet_date&&<span>· Balance sheet: <b style={{color:C.tx}}>{d.freshness.balance_sheet_date}</b></span>}
        {d.freshness.price_time&&<span>· Price: <b style={{color:C.tx}}>{d.freshness.price_time}</b></span>}
        {d.freshness.fx_note&&<span style={{color:C.blue}}>· {d.freshness.fx_note}</span>}
        <span>· Fetched {d.freshness.fetched_at}</span>
        <button onClick={()=>run(co,true,undefined,!!d.match?.exact)} style={{...btn2,marginTop:0,padding:"3px 10px"}}>↻ Refresh now</button>
      </div>}
      {d.warnings?.length>0&&<div style={{margin:"10px 16px 0",padding:"10px 12px",border:`1px solid ${C.warn}55`,background:C.warn+"11",borderRadius:6,fontSize:12,color:C.warn,lineHeight:1.6}}>{d.warnings.map((w,i)=><div key={i}>⚠ {w}</div>)}{!d.sources.length&&<div>Open <a href="/health" style={{color:C.ac}}>Health</a> to see why live sources failed.</div>}</div>}
      <nav style={{display:"flex",overflowX:"auto",borderBottom:`1px solid ${C.bd}`,background:C.card,marginTop:10}}>{TABS.map(t=><button key={t} onClick={()=>setTab(t)} aria-pressed={tab===t} style={{background:"none",border:"none",borderBottom:`2px solid ${tab===t?C.ac:"transparent"}`,color:tab===t?C.ac:C.mu,padding:"9px 12px",fontSize:11,fontWeight:700,cursor:"pointer",textTransform:"uppercase",whiteSpace:"nowrap"}}>{t}{t==="warnings"&&ew.length>0?` (${ew.length})`:""}</button>)}</nav>
      <main style={{padding:"12px 16px",maxWidth:1300,margin:"0 auto"}}>

      {tab==="overview"&&<Grid cols={3}>
        <Card title="Company" span={2} real={p._source!=="ai"} ai={p._source==="ai"}>
          <div style={{fontSize:20,fontWeight:800}}>{p.name||d.company}</div>
          <div style={{marginTop:4}}>{[p.ticker,p.sector,p.industry,p.country].filter(Boolean).map((x,i)=><Bd key={i}>{x}</Bd>)}</div>
          {p.summary&&<p style={{fontSize:12,color:C.mu,lineHeight:1.6,marginTop:8}}>{p.summary}</p>}
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(110px,1fr))",gap:10,marginTop:10}}>
            <Mt l="Market cap" v={$(f.mktCap)}/><Mt l="Revenue" v={$(f.rev)}/><Mt l="EBITDA" v={$(f.ebitda)}/><Mt l="Net income" v={$(f.ni)} c={f.ni<0?C.err:undefined}/>
            <Mt l="Total debt" v={$(f.debt)}/><Mt l="Cash" v={$(f.cash)}/><Mt l="Net debt" v={$(f.netDebt)}/><Mt l="Rev growth" v={f.revGr||"—"}/></div>
        </Card>
        <Card title="Model credit score">{s.score!==undefined?<div style={{textAlign:"center"}}><Gauge score={s.score} grade={s.grade}/><div><Bd c={recC(s.verdict)}>{s.verdict}</Bd></div>
          <div style={{fontSize:11,color:C.mu,marginTop:8,lineHeight:1.6}}>Stress resilience: <b>{s.stress_resilience}</b><br/>PD (blended): <b>{dp.blended_pd}</b> · {dp.pd_band}<br/>Warnings: <b style={{color:s.warnings_critical?C.err:C.tx}}>{s.warnings_total} ({s.warnings_critical} critical)</b>{cr.score?<><br/>AI opinion: {cr.score}/100 {cr.grade} · {cr.rec}</>:ins.st==="loading"?<><br/>AI opinion: loading…</>:null}</div>
          <div style={{fontSize:10,color:C.dim,marginTop:6}}>Deterministic model on reported financials — not an agency rating.</div></div>:<Empty>Needs revenue/asset data.</Empty>}</Card>
        <Card title="Security identifiers" span={3} real><Grid cols={3}><div><Rw l="Ticker" v={p.ticker}/><Rw l="Exchange" v={p.exchange}/></div><div><Rw l="ISIN" v={p.isin}/><Rw l="Currency" v={cur}/></div><div><Rw l="Employees" v={num(p.employees)}/><Rw l="Website" v={p.website}/></div></Grid>
          <div style={{fontSize:10,color:C.dim,marginTop:8}}>Agency credit ratings and bond terms (coupon, maturity, call dates) aren't available from free data sources, so they are not shown — never guessed.</div></Card>
      </Grid>}

      {tab==="financials"&&<Grid cols={3}>
        <Card title="Income statement" real={!est} ai={est}><Rw l="Revenue" v={$(f.rev)}/><Rw l="Cost of revenue" v={$(f.cogs)}/><Rw l="Gross profit" v={$(f.gp)}/><Rw l="Gross margin" v={f.gpM}/><Rw l="EBITDA" v={$(f.ebitda)}/><Rw l="EBITDA margin" v={f.ebitdaM}/><Rw l="EBIT" v={$(f.ebit)}/><Rw l="Interest expense" v={$(f.intExp)}/><Rw l="Net income" v={$(f.ni)}/><Rw l="EPS" v={num(f.eps)}/></Card>
        <Card title="Balance sheet" real={!est} ai={est}><Rw l="Total assets" v={$(f.assets)}/><Rw l="Current assets" v={$(f.ca)}/><Rw l="Current liabilities" v={$(f.cl)}/><Rw l="Equity" v={$(f.equity)}/><Rw l="Total debt" v={$(f.debt)}/><Rw l="Short-term debt" v={$(f.stDebt)}/><Rw l="Cash" v={$(f.cash)}/><Rw l="Net debt" v={$(f.netDebt)}/><Rw l="Debt trend" v={f.debtTrend}/><Rw l="Cash trend" v={f.cashTrend}/></Card>
        <Card title="Cash flow & valuation" real={!est} ai={est}><Rw l="Operating CF" v={$(f.ocf)}/><Rw l="Capex" v={$(f.capex)}/><Rw l="Free CF" v={$(f.fcf)}/><Rw l="Investing CF" v={$(f.icf)}/><Rw l="EV/EBITDA" v={num(f.evEbitda)}/><Rw l="P/E" v={num(f.pe)}/><Rw l="P/B" v={num(f.pbv)}/><Rw l="P/Sales" v={num(f.pRev)}/><Rw l="ROE" v={f.roe}/></Card>
        {d.prev_financials&&Object.keys(d.prev_financials).length>0&&<Card title={`Prior year ${d.prev_financials.period||""}`} span={3} real><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(130px,1fr))",gap:10}}>{[["Revenue","rev"],["EBITDA","ebitda"],["Net income","ni"],["Total debt","debt"],["Cash","cash"],["Operating CF","ocf"]].map(([l,k])=><Mt key={k} l={l} v={$(d.prev_financials[k])}/>)}</div></Card>}
      </Grid>}

      {tab==="ratios"&&(()=>{const cm=calcR(f);if(!cm)return <Card title="Ratios"><Empty>No data</Empty></Card>;return <Grid cols={3}>{cm.M.map(cat=><Card key={cat.c} title={cat.c}>{cat.I.map((m,i)=>{const miss=m.v==null||!isFinite(m.v);const ok=!miss&&m.g(m.v);return <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${C.bd}55`,fontSize:12}}><span>{m.l}</span><span style={{fontFamily:"monospace",fontWeight:700,color:miss?C.dim:ok?C.ok:C.err}}>{miss?"—":`${m.v}${m.u}`}</span></div>})}</Card>)}{cm.F.length>0&&<Card title="Ratio flags" span={3}>{cm.F.map((x,i)=><Bd key={i} c={C.err}>{x}</Bd>)}</Card>}</Grid>})()}

      {tab==="credit"&&<Grid>
        <Card title="Model factor breakdown" real>{rpt.score?.factors?Object.entries(rpt.score.factors).map(([k,v])=><div key={k} style={{marginBottom:8}}><div style={{display:"flex",justifyContent:"space-between",fontSize:11}}><span style={{color:C.mu,textTransform:"capitalize"}}>{k}</span><span style={{fontFamily:"monospace"}}>{v.score}/{v.max}</span></div><div style={{height:5,background:C.card2,borderRadius:3}}><div style={{height:"100%",width:`${v.score/v.max*100}%`,background:v.score>=7?C.ok:v.score>=4?C.warn:C.err,borderRadius:3}}/></div></div>):<Empty>No data</Empty>}</Card>
        <Card title="Default probability" real><Rw l="Rating-implied PD" v={dp.rating_pd}/><Rw l="Altman Z-score PD" v={dp.zscore_pd}/><Rw l="Score-model PD" v={dp.model_pd}/><Rw l="Blended PD" v={dp.blended_pd} c={dp.pd_band==="Distressed"?C.err:dp.pd_band==="Speculative"?C.warn:C.ok}/><Rw l="Band" v={dp.pd_band}/><Rw l="Altman Z" v={dp.altman_z!=null?Number(dp.altman_z).toFixed(2)+` (${dp.altman_zone})`:""}/><Rw l="LGD" v={dp.lgd&&`${dp.lgd} — ${dp.lgd_reasoning}`}/><Rw l="Expected loss" v={$(dp.expected_loss)}/></Card>
        <div style={{gridColumn:"span 2"}}><AIBlock ins={ins} title="Analyst commentary" retry={retryIns}>{x=>{const c=x.credit||{};return <Card title="Analyst commentary" ai><Unv ins={x} sec="credit"/>{c.rationale?<><p style={{fontSize:12,color:C.mu,lineHeight:1.6}}>{c.rationale}</p><Grid><div>{(c.strengths||[]).filter(Boolean).map((t,i)=><div key={i} style={{fontSize:12,borderLeft:`2px solid ${C.ok}`,paddingLeft:8,margin:"6px 0"}}>{t}</div>)}</div><div>{(c.risks||[]).filter(Boolean).map((t,i)=><div key={i} style={{fontSize:12,borderLeft:`2px solid ${C.err}`,paddingLeft:8,margin:"6px 0"}}>{t}</div>)}</div></Grid>{c.score!=null&&<div style={{fontSize:11,color:C.dim,marginTop:6}}>AI opinion: {c.score}/100 {c.grade} · {c.rec} (the model score above is the auditable one)</div>}</>:<Empty>No commentary returned.</Empty>}</Card>}}</AIBlock></div>
      </Grid>}

      {tab==="stress"&&(st.base?<Grid cols={3}>{["base","adverse","severe"].map(k=>{const x=st[k];return <Card key={k} title={x.label} real><div style={{fontSize:11,color:C.mu,marginBottom:6}}>{x.description}</div><Rw l="Revenue" v={$(x.revenue)}/><Rw l="EBITDA" v={$(x.ebitda)}/><Rw l="EBITDA margin" v={x.ebitda_margin+"%"}/><Rw l="Net debt / EBITDA" v={x.nd_ebitda!=null?x.nd_ebitda+"x":""}/><Rw l="Interest cover" v={x.interest_coverage!=null?x.interest_coverage+"x":""}/><Rw l="DSCR" v={x.dscr!=null?x.dscr+"x":""}/><Rw l="Free CF" v={$(x.fcf)} c={x.fcf>0?C.ok:C.err}/><Rw l="Stressed score" v={x.score}/><div style={{marginTop:8}}><Bd c={x.survives?C.ok:C.err}>{x.survives?"SURVIVES":"AT RISK"}</Bd></div></Card>})}</Grid>:<Card title="Stress test"><Empty>{st.error||"Needs revenue and EBITDA."}</Empty></Card>)}

      {tab==="warnings"&&<Card title="Early warning system (deterministic)" real>{ew.length===0?<div style={{color:C.ok,fontSize:13}}>✓ No warning flags triggered.</div>:ew.map((w,i)=><div key={i} style={{padding:"8px 10px",background:C.card2,borderRadius:6,marginBottom:6,borderLeft:`3px solid ${w.level==="critical"?C.err:w.level==="high"?C.warn:C.blue}`}}><div style={{display:"flex",justifyContent:"space-between",gap:8}}><b style={{fontSize:13}}>{w.flag}</b><Bd c={w.level==="critical"?C.err:w.level==="high"?C.warn:C.blue}>{w.level}</Bd></div><div style={{fontSize:12,color:C.mu}}>{w.detail}</div><div style={{fontSize:11,color:C.ac}}>Action: {w.action}</div></div>)}</Card>}

      {tab==="outlook"&&<Grid>
        <Card title="Analyst consensus" real>{Object.keys(d.consensus||{}).length?<><Rw l="Recommendation" v={d.consensus.recommendation}/><Rw l="Analysts" v={d.consensus.analysts}/><Rw l="Target (mean)" v={num(d.consensus.targetMean)}/><Rw l="Target range" v={d.consensus.targetLow&&`${num(d.consensus.targetLow)} – ${num(d.consensus.targetHigh)}`}/><Rw l="Forward EPS" v={num(d.consensus.forwardEps)}/><Rw l="Forward P/E" v={num(d.consensus.forwardPE)}/><Rw l="Earnings growth" v={d.consensus.earningsGrowth}/><Rw l="Revenue growth" v={d.consensus.revenueGrowth}/></>:<Empty>No consensus data published for this ticker.</Empty>}</Card>
        <AIBlock ins={ins} title="Outlook narrative" retry={retryIns}>{x=>{const o=x.outlook||{};return <Card title="Outlook narrative" ai><Unv ins={x} sec="outlook"/>{o.outlook?<><p style={{fontSize:12,color:C.mu,lineHeight:1.6}}>{o.outlook}</p><Rw l="Guidance" v={o.guidance}/><Rw l="Revision" v={o.revision}/></>:<Empty>No outlook returned.</Empty>}</Card>}}</AIBlock></Grid>}

      {tab==="debt"&&<Grid><Card title="Debt figures" real><Rw l="Total debt" v={$(f.debt)}/><Rw l="Short-term debt" v={$(f.stDebt)}/><Rw l="Cash" v={$(f.cash)}/><Rw l="Net debt" v={$(f.netDebt)}/><Rw l="Net debt / EBITDA" v={f.ndEbitda}/><Rw l="Interest expense" v={$(f.intExp)}/><Rw l="Debt trend" v={f.debtTrend}/><Rw l="Cash trend" v={f.cashTrend}/></Card>
        <AIBlock ins={ins} title="Structure & liquidity" retry={retryIns}>{x=>{const b=x.debt||{};return <Card title="Structure & liquidity" ai><Unv ins={x} sec="debt"/><p style={{fontSize:12,color:C.mu,lineHeight:1.6}}>{b.capStructure}</p><Rw l="Liquidity" v={b.liquiditySummary}/><Rw l="Covenant risks" v={b.covenants}/><div style={{fontSize:10,color:C.dim,marginTop:8}}>Actual covenants and maturity schedules are in bond prospectuses — not estimated here.</div></Card>}}</AIBlock></Grid>}

      {tab==="shareholding"&&<Grid><Card title="Ownership" real={!!d.sources.length}><Rw l="Insiders / promoters" v={h.promoter}/><Rw l="Institutions" v={h.fii}/><Rw l="Price" v={h.price!=null?money(h.price,h.currency||cur):""}/><Rw l="Shares outstanding" v={num(h.sharesOut)}/><Rw l="Float shares" v={num(h.freeFloat)}/><Rw l="Dividend yield" v={h.divYield}/>{!h.promoter&&!h.fii&&<Empty>No ownership data from available sources.</Empty>}</Card><Card title="Top institutional holders" real>{(h.holders||[]).length?h.holders.map((x,i)=><Rw key={i} l={x.name} v={x.stake}/>):<Empty>Not published for this ticker.</Empty>}</Card></Grid>}

      {tab==="team"&&<Grid><Card title="Officers" real>{(d.officers||[]).length?d.officers.map((m,i)=><div key={i} style={{padding:"6px 0",borderBottom:`1px solid ${C.bd}55`}}><div style={{fontSize:13,fontWeight:700}}>{m.name}</div><div style={{fontSize:11,color:C.ac}}>{m.title}</div></div>):<Empty>No officer data from Yahoo Finance.</Empty>}</Card>
        <AIBlock ins={ins} title="Governance" retry={retryIns}>{x=>{const g=x.governance||{};return <Card title="Governance" ai><Unv ins={x} sec="governance"/>{g.governance||g.quality?<><Rw l="Assessment" v={g.quality}/><p style={{fontSize:12,color:C.mu,marginTop:6,lineHeight:1.6}}>{g.governance}</p></>:<Empty>No assessment returned.</Empty>}</Card>}}</AIBlock></Grid>}

      {tab==="comps"&&<AIBlock ins={ins} title="Peers" retry={retryIns}>{x=>{const pr=x.peers||{};return <Card title="Peer comparison — figures live from Yahoo Finance" real>
        <div style={{fontSize:11,color:C.mu,marginBottom:8}}>AI only suggested which companies are peers; every number below was fetched live. Tickers that don't exist are dropped automatically.</div>
        {pr.error&&<div style={{fontSize:11,color:C.warn}}>{pr.error}</div>}
        <div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}><thead><tr>{["Company","Ticker","Mkt cap","Revenue","EBITDA %","Debt/Equity","Net debt/EBITDA","ROE %","Interest cover","Period"].map(t=><th key={t} style={{textAlign:"left",color:C.dim,fontSize:10,padding:"4px 6px",borderBottom:`1px solid ${C.bd}`,whiteSpace:"nowrap"}}>{t}</th>)}</tr></thead>
        <tbody>{(pr.rows||[]).map((r,i)=><tr key={i} style={{background:r.self?C.ac+"14":"transparent"}}>{[r.name,r.symbol,money(r.mktCap,r.currency),money(r.rev,r.currency),r.ebitdaM,r.de,r.ndEbitda,r.roe,r.intCover,r.period].map((v,k)=><td key={k} style={{padding:"5px 6px",borderBottom:`1px solid ${C.bd}55`,fontFamily:k>1?"monospace":"inherit",whiteSpace:k===0?"normal":"nowrap"}}>{v??"—"}</td>)}</tr>)}
        {pr.medians&&<tr>{["Peer median","","","",pr.medians.ebitdaM,pr.medians.de,pr.medians.ndEbitda,pr.medians.roe,pr.medians.intCover,""].map((v,k)=><td key={k} style={{padding:"5px 6px",color:C.mu,fontStyle:"italic",fontFamily:k>1?"monospace":"inherit"}}>{v??"—"}</td>)}</tr>}</tbody></table></div>
        {pr.dropped?.length>0&&<div style={{fontSize:11,color:C.warn,marginTop:8}}>Dropped (not found on Yahoo Finance): {pr.dropped.join(", ")}</div>}
        <div style={{fontSize:10,color:C.dim,marginTop:6}}>Bond spreads and yields aren't in free data sources, so they are not estimated.</div></Card>}}</AIBlock>}

      {tab==="risk"&&<AIBlock ins={ins} title="Risk assessment" retry={retryIns}>{x=>{const r=x.risk||{};return <Card title="Risk assessment" ai><Unv ins={x} sec="risk"/>{r.overall&&<Bd c={r.overall==="high"?C.err:r.overall==="low"?C.ok:C.warn}>overall {r.overall}</Bd>}{(r.risks||[]).map((k,i)=><div key={i} style={{padding:"8px 10px",background:C.card2,borderRadius:6,marginTop:6,borderLeft:`3px solid ${k.sev==="high"?C.err:k.sev==="med"?C.warn:C.blue}`}}><div style={{display:"flex",justifyContent:"space-between",gap:8}}><b style={{fontSize:13}}>{k.factor}</b><span><Bd>{k.cat}</Bd><Bd c={k.sev==="high"?C.err:C.warn}>{k.sev}</Bd></span></div><div style={{fontSize:12,color:C.mu}}>{k.desc}</div>{k.mitigant&&<div style={{fontSize:11,color:C.ok}}>Mitigant: {k.mitigant}</div>}</div>)}<div style={{fontSize:11,color:C.dim,marginTop:8}}>Hard-number warnings are in the Warnings tab (deterministic).</div></Card>}}</AIBlock>}

      {tab==="industry"&&<AIBlock ins={ins} title="Industry" retry={retryIns}>{x=>{const k=x.industry||{};return <Card title={`${k.industry||p.industry||"Sector"} — what to watch`} ai><Unv ins={x} sec="industry"/>{k.moat&&<Bd c={C.vio}>moat: {k.moat}</Bd>}{k.position&&<Bd c={C.ok}>{k.position}</Bd>}{(k.kpis||[]).map((m,i)=><div key={i} style={{padding:"6px 0",borderBottom:`1px solid ${C.bd}55`}}><div style={{fontSize:13,fontWeight:600}}>{m.name}</div><div style={{fontSize:12,color:C.mu}}>{m.why}</div></div>)}<div style={{fontSize:10,color:C.dim,marginTop:8}}>Sector KPI values aren't in free data sources, so only the KPIs to track are listed — no invented values.</div></Card>}}</AIBlock>}

      {tab==="news"&&<Card title="Recent headlines (Yahoo Finance)" real>{ins.st==="ok"&&ins.data.newsSentiment&&<div style={{marginBottom:8}}><Bd c={C.vio}>AI sentiment: {ins.data.newsSentiment}</Bd></div>}{ins.st==="loading"&&<div style={{fontSize:11,color:C.dim,marginBottom:6}}>AI sentiment tags loading…</div>}
        {(d.news||[]).length?(ins.st==="ok"?ins.data.news:d.news).map((a,i)=><div key={i} style={{padding:"8px 0",borderBottom:`1px solid ${C.bd}55`}}><a href={a.url||undefined} target="_blank" rel="noopener noreferrer" style={{color:C.tx,fontSize:13,fontWeight:600,textDecoration:"none"}}>{a.t}</a><div style={{fontSize:10,color:C.dim}}>{a.src} · {a.date}{a.sent&&<> · <span style={{color:String(a.sent).startsWith("pos")?C.ok:String(a.sent).startsWith("neg")?C.err:C.warn}}>{a.sent}</span></>}{a.imp&&<> · impact {a.imp}</>}</div>{a.sum&&<div style={{fontSize:12,color:C.mu,marginTop:2}}>{a.sum}</div>}{a.why&&<div style={{fontSize:11,color:C.vio}}>↳ {a.why}</div>}</div>):<Empty>No recent headlines from Yahoo Finance.</Empty>}</Card>}

      </main>
      <footer style={{padding:"10px 16px",borderTop:`1px solid ${C.bd}`,fontSize:10,color:C.dim,textAlign:"center",lineHeight:1.6}}>Credit Nexus · For research and educational use. Figures come from the listed sources; AI-labelled content is generated and must be verified. Not investment advice.</footer>
    </>}
  </div>);
}
