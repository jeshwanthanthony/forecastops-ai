import React, {useEffect,useRef,useState} from 'react'

const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(value)

export function SalesFacts({result,demo=false,onView}) {
  const [ready,setReady]=useState(false)
  useEffect(()=>{setReady(false);const delay=window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:2300;const timer=setTimeout(()=>setReady(true),delay);return()=>clearTimeout(timer)},[result])
  const rows=result.data,total=rows.reduce((sum,row)=>sum+row.sales,0)
  const recent=rows.slice(-7).reduce((sum,row)=>sum+row.sales,0)
  const highest=rows.reduce((best,row)=>row.sales>best.sales?row:best,rows[0])
  const facts=[['Days of sales history',String(rows.length)],['Historical sales',money(total)],['Average daily sales',money(total/rows.length)],['Most recent seven days',money(recent)],['Highest daily sales',money(highest.sales)]]
  return <div className="sales-reveal"><small>{demo?'FICTIONAL RESTAURANT · SYNTHETIC DATA':result.report?.source||'YOUR SALES DATA'}</small><h2>{demo?'Juniper Table':result.report?.business_name||'Your business, at a glance.'}</h2><p>{demo?'Imagine this is your restaurant. Here is the sales history we will use.':'Here is the sales history imported for your forecast.'}</p><div className="reveal-facts">{facts.map(([label,value],i)=><div key={label} className="reveal-fact" style={{animationDelay:`${i*.4}s`}}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="reveal-action">{ready&&<button className="button enter" onClick={onView}>View prediction</button>}</div><p className="reveal-caption">These figures describe past sales. The prediction appears on the next screen.</p></div>
}

export default function SalesReveal({result,onView,onClose}) {
  const dialog=useRef(null)
  useEffect(()=>{dialog.current.showModal()},[])
  const demo=result.report?.source==='Synthetic demonstration'
  return <dialog ref={dialog} className="forecast-theatre sales-reveal-dialog" onCancel={onClose} aria-label="Sales overview"><header><small>YOUR SALES OVERVIEW</small><button className="quiet" onClick={onClose}>Close</button></header><SalesFacts result={result} demo={demo} onView={onView}/></dialog>
}
