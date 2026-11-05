import React, {useRef, useState} from 'react'
import {SalesFacts} from './SalesReveal'

export default function ForecastAction({data,onResult,demo=false}) {
  const dialog=useRef(null), [days,setDays]=useState(7),[busy,setBusy]=useState(false),[result,setResult]=useState(null),[error,setError]=useState('')
  const run=async()=>{
    setBusy(true);setResult(null);setError('');dialog.current.showModal()
    try {
      let rows=data
      if(!rows){const response=await fetch('/api/demo',{signal:AbortSignal.timeout(30000)});if(!response.ok)throw new Error('Could not load the sample data.');rows=(await response.json()).data}
      const response=await fetch('/api/forecast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:rows,days}),signal:AbortSignal.timeout(30000)})
      if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('The server is unavailable. Please try again.')
      const body=await response.json();if(!response.ok)throw new Error(body.detail||'Forecast failed.');setResult(body)
    } catch(e){setError(e.name==='TimeoutError'?'The request timed out. Please try again.':e.message)} finally{setBusy(false)}
  }
  return <><div className="forecast-actions"><label>Forecast ahead<select value={days} onChange={e=>setDays(Number(e.target.value))}><option value={1}>Tomorrow</option><option value={7}>Next week</option><option value={14}>Next two weeks</option></select></label><button className="button" disabled={busy} onClick={run}>{demo?'Try the interactive demo':'Generate forecast'}</button></div><dialog ref={dialog} className="forecast-theatre sales-reveal-dialog" aria-label="Sales overview"><header><small>YOUR SALES OVERVIEW</small><button className="quiet" onClick={()=>dialog.current.close()}>Close</button></header>{busy&&<div className="reveal-loading" role="status"><h2>Preparing your sales history.</h2><p>Calculating from the selected dataset.</p></div>}{error&&<p className="error" role="alert">{error}</p>}{result&&<SalesFacts result={result} demo={demo} onView={()=>{dialog.current.close();onResult({...result,reviewed:true})}}/>}{error&&<button className="button" onClick={()=>{dialog.current.close();run()}}>Try again</button>}</dialog></>
}
