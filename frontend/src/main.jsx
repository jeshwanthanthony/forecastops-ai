import React, {useEffect, useRef, useState} from 'react'
import {createRoot} from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource-variable/inter-tight'
import './styles.css'
import ResultsDashboard from './ResultsDashboard'
import ForecastAction from './ForecastAction'
import SalesReveal from './SalesReveal'

const API='/api'
let activeImport = null
async function cancelImport() {
  if (!activeImport) return
  activeImport.cancelled = true
  if (activeImport.id) await fetch(`${API}/square/import/jobs/${activeImport.id}`, {method:'DELETE', signal:AbortSignal.timeout(15000)})
}
async function readResponse(response) {
  const type = response.headers.get('content-type') || ''
  if (!type.includes('application/json')) throw new Error('The server is unavailable. Please try again.')
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || 'Request failed. Please try again.')
  return data
}
async function importSquare() {
  const current = {id:null,cancelled:false}; activeImport=current
  const job = await readResponse(await fetch(`${API}/square/import/jobs`, {method:'POST', signal:AbortSignal.timeout(15000)}))
  current.id=job.job_id
  if(current.cancelled){await fetch(`${API}/square/import/jobs/${job.job_id}`,{method:'DELETE',signal:AbortSignal.timeout(15000)});throw new Error('Import cancelled.')}
  for (let i=0;i<180;i++) {
    if(current.cancelled) throw new Error('Import cancelled.')
    await new Promise(resolve=>setTimeout(resolve,2000))
    const status=await readResponse(await fetch(`${API}/square/import/jobs/${job.job_id}`,{cache:'no-store',signal:AbortSignal.timeout(15000)}))
    if(status.status==='completed') return status.result
    if(status.status==='failed'||status.status==='cancelled') throw new Error(status.error||'Import cancelled.')
  }
  throw new Error('Import is taking longer than expected. Please try again later.')
}

function CsvCard({onResult}) {
  const [dragging,setDragging]=useState(false)
  const useSample=async()=>{try{const response=await fetch('/api/sample.csv');if(!response.ok)throw new Error();inspect(new File([await response.blob()],'sample-sales.csv',{type:'text/csv'}))}catch{setError('Could not load the sample CSV.')}}
  const input=useRef(), [file,setFile]=useState(null), [preview,setPreview]=useState(null), [date,setDate]=useState(''), [sales,setSales]=useState(''), [count,setCount]=useState(''), [order,setOrder]=useState(''), [error,setError]=useState(''), [busy,setBusy]=useState(false)
  const inspect=async selected=>{if(!selected)return;setBusy(true);setError('');try{const form=new FormData();form.append('file',selected);const data=await readResponse(await fetch(`${API}/csv/preview`,{method:'POST',body:form}));setFile(selected);setPreview(data);setDate(data.candidates.date.length===1?data.candidates.date[0]:'');setSales(data.candidates.sales.length===1?data.candidates.sales[0]:'');setCount(data.candidates.order_count.length===1?data.candidates.order_count[0]:'')}catch(e){setError(e.message)}finally{setBusy(false)}}
  const submit=async()=>{setBusy(true);setError('');try{const form=new FormData();form.append('file',file);form.append('date_column',date);form.append('sales_column',sales);form.append('count_column',count);form.append('date_order',order);onResult(await readResponse(await fetch(`${API}/csv/import`,{method:'POST',body:form})))}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <article className="card upload-card enter d2"><h2>Upload CSV</h2><p>Start with a file of daily sales or transactions.</p>{!preview&&<div className="sample-file" draggable onDragStart={e=>e.dataTransfer.setData("application/x-forecastops-sample","true")}><button type="button" className="quiet" onClick={useSample}><span>sample-sales.csv</span><small>date · sales · order_count</small></button><span>Drag into the upload area, or click to try</span></div>}{!preview&&<button type="button" disabled={busy} className={dragging?"dropzone dragging":"dropzone"} onClick={()=>input.current.click()} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);if(!busy){if(e.dataTransfer.getData("application/x-forecastops-sample"))useSample();else inspect(e.dataTransfer.files[0])}}}><span className="upload-symbol" aria-hidden="true">↑</span><strong>Drop your CSV here</strong><span>or click to browse</span><small>CSV or TSV · up to 5 MB</small></button>}{preview?<div className="csv-mapping"><p>{file.name} · {preview.encoding} · {preview.delimiter}</p>{[['Date',date,setDate],['Sales',sales,setSales],['Order count (optional)',count,setCount]].map(([label,value,set])=><label key={label}>{label}<select value={value} onChange={e=>set(e.target.value)}><option value="">Choose column</option>{preview.columns.map(c=><option key={c}>{c}</option>)}</select></label>)}<label>Date format<select value={order} onChange={e=>setOrder(e.target.value)}><option value="">Automatic / ISO</option><option value="mdy">Month / day / year</option><option value="dmy">Day / month / year</option></select></label><div className="csv-preview" role="region" aria-label="CSV preview"><table><thead><tr>{preview.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{preview.preview.map((row,i)=><tr key={i}>{preview.columns.map(c=><td key={c}>{row[c]}</td>)}</tr>)}</tbody></table></div><button className="button" disabled={busy||!date||!sales} onClick={submit}>{busy?'Processing…':'Create forecast'}</button></div>:<><div className="csv"><span>date, sales, order_count</span><i>2026-10-01, 1843.50, 92</i><i>2026-10-02, 2010.25, 101</i></div><button className="button" disabled={busy} onClick={()=>input.current.click()}>{busy?'Reading…':'Choose CSV'}</button><a href={`${API}/sample.csv`}>Download sample CSV</a></>}<input ref={input} type="file" accept=".csv,.tsv,text/csv" hidden onChange={e=>inspect(e.target.files[0])}/>{error&&<p className="error" role="alert">{error}</p>}</article>
}
function SquareCard({onResult}) {
  const [status,setStatus]=useState(null),[connected,setConnected]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{
    fetch(`${API}/square/status`).then(r=>r.json()).then(setStatus).catch(()=>setError('Unable to reach Square configuration.'));
    fetch(`${API}/square/session`).then(r=>r.json()).then(d=>setConnected(!!d.connected)).catch(()=>{});
  },[]);
  const importSales=async()=>{
    setBusy(true);setError('');
    try {
      const data=await importSquare();
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
  return <article className="card square-card enter d1">
    <div className="number">01 <b>{status?.mode==='production'?'PRODUCTION':'SANDBOX'}</b></div>
    <h2>Connect to Square</h2>
    <p>Authorize read-only access to your own completed orders and build a seven-day forecast.</p>
    {connected?<><button className="button" disabled={busy} onClick={importSales}>{busy?'Importing…':'Import my sales'}</button>{busy?<button className="quiet" onClick={()=>cancelImport().catch(()=>setError('Could not cancel. Please try again.'))}>Cancel import</button>:<button className="quiet" onClick={disconnect}>Disconnect Square</button>}</>
      :<button className="button" disabled={!status?.configured} onClick={()=>location.href=`${API}/square/connect`}>{status?.configured?'Connect Square':'Configuration needed'}</button>}
    <p className="note">{status?.message||'Read-only permission. Your connection is temporary; disconnect when finished. Forecast figures are estimates.'}</p>
    {error&&<p className="error" role="alert">{error}</p>}
  </article>
}
function DemoCard({onResult}) { return <section className="demo-launch enter"><div><small>START WITH A DEMO</small><h2>See the forecast come together.</h2><p>Explore fictional restaurant sales, watch the Python workflow, then open the prediction.</p></div><ForecastAction demo onResult={result=>onResult({...result,report:{...result.report,source:"Synthetic demonstration",scenario:"normal"}})}/></section> }
function Welcome({onResult}){return <main className="welcome"><header><div className="wordmark">ForecastOps <span>AI</span></div><div className="tag">SALES FORECASTING</div></header><section className="hero enter"><p className="eyebrow">GET STARTED</p><h1>A clearer view<br/><em>of what’s ahead.</em></h1><p className="lead">Bring your sales data, or explore a sample to see how it works.</p></section><DemoCard onResult={onResult}/><section className="cards" aria-label="Choose how to get started"><SquareCard onResult={onResult}/><CsvCard onResult={onResult}/></section><footer>ForecastOps AI <span>·</span> Sales forecasting and analysis</footer></main>}
function App(){
  const [pendingReview,setPendingReview]=useState(null)
  const [result,setResult]=useState(null),[leaving,setLeaving]=useState(false),[squareError,setSquareError]=useState(''),[squareLoading,setSquareLoading]=useState(false);
  const navigate=next=>{
    if(next&&!next.reviewed){setPendingReview(next);return}
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
      setSquareLoading(true);
      importSquare()
        .then(data=>setPendingReview(data))
        .catch(e=>setSquareError(e.message))
        .finally(()=>setSquareLoading(false));
    }
  },[]);
  return <div className={leaving?'page page-leaving':'page'}>
    {pendingReview&&<SalesReveal result={pendingReview} onClose={()=>setPendingReview(null)} onView={()=>{const next=pendingReview;setPendingReview(null);navigate({...next,reviewed:true})}}/>}
    {squareLoading&&<p role="status" style={{maxWidth:840,margin:'1rem auto',padding:12}}>Importing your Square sales. This may take a few minutes. <button className="quiet" onClick={()=>cancelImport().catch(()=>setSquareError('Could not cancel. Please try again.'))}>Cancel import</button></p>}
    {squareError&&<p className="error" role="alert" style={{maxWidth:840,margin:'1rem auto',padding:12}}>{squareError}</p>}
    {result?<ResultsDashboard result={result} onBack={()=>navigate(null)} onDisconnect={disconnect} onResult={setResult}/>:<Welcome onResult={navigate}/>}
  </div>
}
createRoot(document.getElementById('root')).render(<App/>)
