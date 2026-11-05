import React, {useEffect, useRef, useState} from 'react'
import {createRoot} from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource-variable/inter-tight'
import './styles.css'

const API='/api'
const money=n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n||0)

function Chart({data, forecast=[]}) {
  const values=[...data.map(x=>x.sales),...forecast.map(x=>x.sales)], w=760,h=230, min=Math.min(...values)*.9,max=Math.max(...values)*1.05
  const points=(rows,key='sales',start=0)=>rows.map((d,i)=>`${(start+i)*(w-20)/(Math.max(1,data.length+forecast.length-1))+10},${h-15-(d[key]-min)*(h-30)/(max-min||1)}`).join(' ')
  return <div className="chart"><svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Sales history and seven day forecast"><line x1="10" x2={w-10} y1={h-15} y2={h-15}/><polyline points={points(data)} className="history"/><polyline points={points(forecast,'sales',data.length)} className="forecast"/></svg><div className="legend"><i/>Historical <i className="future"/>Forecast</div></div>
}

function Dashboard({result,onBack,onDisconnect}) {
  const [question,setQuestion]=useState('What will Saturday look like?'), [answer,setAnswer]=useState(null), [loading,setLoading]=useState(false)
  const ask=async q=>{setLoading(true);setQuestion(q);try {const r=await fetch(`${API}/ask`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,data:result.data})});const body=await r.json();setAnswer(r.ok?body:{answer:body.detail||'The analyst is unavailable.'})} catch {setAnswer({answer:'Unable to reach the analyst. Please try again.'})} finally {setLoading(false)}}
  return <main className="dashboard enter"><header><button className="wordmark" onClick={onBack}>FORECASTOPS <span>AI</span></button><div><button className="quiet" onClick={onBack}>Start over</button>{result.report?.source?.startsWith("Square")&&<button className="quiet" onClick={onDisconnect}>Disconnect Square</button>}</div></header><div className="eyebrow">{result.report?.source || 'SYNTHETIC DEMONSTRATION'} <b>•</b> {result.data.length} DAILY OBSERVATIONS</div><h1>Your next week,<br/><em>made visible.</em></h1><section className="stats"><div><small>MODEL MAE</small><strong>{money(result.metrics.model_mae)}</strong></div><div><small>BASELINE MAE</small><strong>{money(result.metrics.baseline_mae)}</strong></div><div><small>NEXT 7 DAYS</small><strong>{money(result.forecast.reduce((n,x)=>n+x.sales,0))}</strong></div></section><section className="panel"><div className="panel-head"><div><small>SALES TRAJECTORY</small><h2>History & forecast</h2></div><span>7-day model projection</span></div><Chart data={result.data.slice(-60)} forecast={result.forecast}/></section><div className="split"><section className="panel"><small>NEXT SEVEN DAYS</small>{result.forecast.map(x=><div className="row" key={x.date}><span>{new Date(x.date+'T00:00:00').toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}</span><strong>{money(x.sales)}</strong></div>)}</section><section className="panel analyst"><small>AI ANALYST <span className="live">{answer?.mode==='openai'?'LIVE':'DEMO READY'}</span></small><h2>Ask the numbers.</h2><div className="prompts">{['Why did sales drop last Tuesday?','What will Saturday look like?','Summarize the sales history.'].map(q=><button onClick={()=>ask(q)} key={q}>{q}</button>)}</div>{answer&&<p className="answer">{answer.answer}</p>}<form onSubmit={e=>{e.preventDefault();ask(question)}}><input value={question} onChange={e=>setQuestion(e.target.value)} aria-label="Ask the AI analyst"/><button disabled={loading}>{loading?'Thinking…':'Ask'}</button></form></section></div></main>
}

function CsvCard({onResult}) { const input=useRef(), [error,setError]=useState(''), [busy,setBusy]=useState(false); const upload=async file=>{if(!file)return;setBusy(true);setError('');try{const form=new FormData();form.append('file',file);const r=await fetch(`${API}/upload`,{method:'POST',body:form});const body=await r.json();r.ok?onResult(body):setError(body.detail||'Could not validate this file.')}catch{setError('Could not reach the server. Please try again.')}finally{setBusy(false);if(input.current)input.current.value=''}}; return <article className="card enter d2"><div className="number">02</div><h2>Upload CSV</h2><p>Start with a file of your daily sales.</p><div className="csv" aria-label="CSV example"><span>date, sales, order_count</span><i>2026-10-01, 1843.50, 92</i><i>2026-10-02, 2010.25, 101</i></div><button className="button" disabled={busy} onClick={()=>input.current.click()}>{busy?'Validating…':'Choose CSV'}</button><input ref={input} type="file" accept=".csv,text/csv" hidden onChange={e=>upload(e.target.files[0])}/><a href={`${API}/sample.csv`}>Download sample CSV</a>{error&&<p className="error" role="alert">{error}</p>}</article> }
function SquareCard({onResult}) {
  const [status,setStatus]=useState(null),[connected,setConnected]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{
    fetch(`${API}/square/status`).then(r=>r.json()).then(setStatus).catch(()=>setError('Unable to reach Square configuration.'));
    fetch(`${API}/square/session`).then(r=>r.json()).then(d=>setConnected(!!d.connected)).catch(()=>{});
  },[]);
  const importSales=async()=>{
    setBusy(true);setError('');
    try {
      const r=await fetch(`${API}/square/import`,{cache:'no-store'});
      const data=await r.json();
      if(!r.ok)throw new Error(data.detail||'Sales import failed.');
      onResult(data);
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  };
  const disconnect=async()=>{
    setBusy(true);setError('');
    try {
      const r=await fetch(`${API}/square/disconnect`,{method:'POST'});
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'Disconnect failed.');
      setConnected(false);
      if(data.message)setError(data.message);
    } catch(e){setError(e.message);} finally {setBusy(false);}
  };
  return <article className="card enter d1">
    <div className="number">01 <b>{status?.mode==='production'?'PRODUCTION':'SANDBOX'}</b></div>
    <h2>Connect to Square</h2>
    <p>Authorize read-only access to your own completed orders and build a seven-day forecast.</p>
    {connected?<><button className="button" disabled={busy} onClick={importSales}>{busy?'Importing…':'Import my sales'}</button><button className="quiet" disabled={busy} onClick={disconnect}>Disconnect Square</button></>
      :<button className="button" disabled={!status?.configured} onClick={()=>location.href=`${API}/square/connect`}>{status?.configured?'Connect Square':'Configuration needed'}</button>}
    <p className="note">{status?.message||'Read-only permission. Your connection is temporary; disconnect when finished. Forecast figures are estimates.'}</p>
    {error&&<p className="error" role="alert">{error}</p>}
  </article>
}
function DemoCard({onResult}){const [busy,setBusy]=useState(false),[error,setError]=useState('');const open=async()=>{setBusy(true);setError('');try{const r=await fetch(`${API}/demo`);if(!r.ok)throw new Error();onResult(await r.json())}catch{setError('The demo could not be loaded. Please try again.')}finally{setBusy(false)}};return <article className="card enter d3"><div className="number">03</div><h2>See how it works</h2><p>Explore forecasts using fictional sales data.</p><button className="button" disabled={busy} onClick={open}>{busy?'Loading…':'Explore the demo'}</button>{error&&<p className="error" role="alert">{error}</p>}</article>}
function Welcome({onResult}){return <main className="welcome"><header><div className="wordmark">ForecastOps <span>AI</span></div><div className="tag">SALES FORECASTING</div></header><section className="hero enter"><p className="eyebrow">GET STARTED</p><h1>A clearer view<br/><em>of what’s ahead.</em></h1><p className="lead">Bring your sales data, or explore a sample to see how it works.</p></section><section className="cards" aria-label="Choose how to get started"><SquareCard onResult={onResult}/><CsvCard onResult={onResult}/><DemoCard onResult={onResult}/></section><footer>ForecastOps AI <span>·</span> Sales forecasting and analysis</footer></main>}
function App(){
  const [result,setResult]=useState(null),[leaving,setLeaving]=useState(false),[squareError,setSquareError]=useState('');
  const navigate=next=>{
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){setResult(next);return}
    setLeaving(true);
    window.setTimeout(()=>{setResult(next);setLeaving(false);window.scrollTo(0,0)},180);
  };
  const disconnect=async()=>{
    const r=await fetch(`${API}/square/disconnect`,{method:'POST'});
    const data=await r.json();
    if(!r.ok) {setSquareError(data.detail||'Could not disconnect.');return}
    setSquareError(data.message||'');
    setResult(null);
  };
  useEffect(()=>{
    if(new URLSearchParams(location.search).get('square')==='connected'){
      history.replaceState(null,'','/');
      fetch(`${API}/square/import`,{cache:'no-store'})
        .then(async r=>{const data=await r.json();if(!r.ok)throw new Error(data.detail||'Square sales import failed.');setResult(data)})
        .catch(e=>setSquareError(e.message));
    }
  },[]);
  return <div className={leaving?'page page-leaving':'page'}>
    {squareError&&<p className="error" role="alert" style={{maxWidth:840,margin:'1rem auto',padding:12}}>{squareError}</p>}
    {result?<Dashboard result={result} onBack={()=>navigate(null)} onDisconnect={disconnect}/>:<Welcome onResult={navigate}/>}
  </div>
}
createRoot(document.getElementById('root')).render(<App/>)
