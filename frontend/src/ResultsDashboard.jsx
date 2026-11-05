import React, {useState} from 'react'
import ForecastAction from './ForecastAction'

const money = value => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(value)
const dateLabel = date => new Date(date+'T12:00:00').toLocaleDateString(undefined,{month:'short',day:'numeric'})

function SalesChart({history, forecast}) {
  const [selected,setSelected]=useState(null)
  const rows=[...history,...forecast], width=900,height=280,pad=35
  const maximum=Math.max(1,...rows.map(row=>row.sales))*1.1
  const x=i=>pad+i*(width-pad*2)/Math.max(rows.length-1,1)
  const y=value=>height-pad-value*(height-pad*2)/maximum
  const line=(items,start)=>items.map((row,i)=>`${x(start+i)},${y(row.sales)}`).join(' ')
  return <div className="sales-plot"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Recent daily sales and seven-day forecast">
    {[0,.25,.5,.75,1].map(p=><g key={p}><line x1={pad} x2={width-pad} y1={y(maximum*p)} y2={y(maximum*p)} className="grid-line"/><text x={pad} y={y(maximum*p)-7}>{money(maximum*p)}</text></g>)}
    <polygon points={`${x(0)},${height-pad} ${line(history,0)} ${x(history.length-1)},${height-pad}`} className="chart-area"/>
    <polyline points={line(history,0)} className="actual-line"/>
    <polyline points={line([history.at(-1),...forecast],history.length-1)} className="projection-line"/>
    {rows.map((row,i)=><circle key={row.date} cx={x(i)} cy={y(row.sales)} r="5" className="chart-point" tabIndex="0" aria-label={`${dateLabel(row.date)}: ${money(row.sales)}`} onFocus={()=>setSelected(row)} onMouseEnter={()=>setSelected(row)}><title>{dateLabel(row.date)}: {money(row.sales)}</title></circle>)}
  </svg><div className="chart-caption"><span>{selected?`${dateLabel(selected.date)} · ${money(selected.sales)}`:dateLabel(rows[0].date)}</span><span><i/> Actual sales <i className="projection-dot"/> Forecast</span><span>{dateLabel(rows.at(-1).date)}</span></div></div>
}

export default function ResultsDashboard({result,onBack,onDisconnect,onResult}) {
  const [question,setQuestion]=useState('Summarize the sales history.'),[answer,setAnswer]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[range,setRange]=useState(60)
  const data=result.data, report=result.report||{}, forecast=result.forecast
  const horizon=forecast.length
  const total=data.reduce((sum,row)=>sum+row.sales,0), future=forecast.reduce((sum,row)=>sum+row.sales,0)
  const lastWeek=data.slice(-horizon).reduce((sum,row)=>sum+row.sales,0), change=lastWeek?100*(future-lastWeek)/lastWeek:null
  const days=Array.from({length:7},(_,day)=>{const values=data.filter(row=>new Date(row.date+'T12:00:00').getDay()===day);return {label:['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][day],value:values.reduce((s,row)=>s+row.sales,0)/(values.length||1)}})
  const maxDay=Math.max(1,...days.map(day=>day.value)), maxForecast=Math.max(1,...forecast.map(row=>row.sales))
  const synthetic=report.source==='Synthetic demonstration'
  const request=async(url,options)=>{const response=await fetch(url,{...options,signal:AbortSignal.timeout(30000)});if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('The server is unavailable. Please try again.');const body=await response.json();if(!response.ok)throw new Error(body.detail||'Request failed.');return body}
  const ask=async q=>{setQuestion(q);setBusy(true);setError('');try{setAnswer(await request('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,data})}))}catch(e){setError(e.message)}finally{setBusy(false)}}
  const scenario=async value=>{setBusy(true);setError('');try{onResult(await request(`/api/demo?scenario=${value}`))}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <main className="results enter">
    <header className="results-nav"><button className="wordmark" onClick={onBack}>ForecastOps <span>AI</span></button><nav><span className="source-chip">{synthetic?'Synthetic dataset':report.source?.startsWith('Square')?'Square connection':'CSV dataset'}</span><button className="quiet" onClick={onBack}>Change data</button>{report.source?.startsWith('Square')&&<button className="quiet" onClick={onDisconnect}>Disconnect</button>}</nav></header>
    <div className="results-title"><div><p className="eyebrow">SALES WORKSPACE</p><h1>Your sales, in perspective.</h1><p>{dateLabel(data[0].date)} – {dateLabel(data.at(-1).date)} · {data.length} daily observations</p></div><ForecastAction data={data} onResult={next=>onResult({...next,report:{...report,...next.report,source:report.source}})}/></div>
    {synthetic&&<div className="scenario-strip"><span>Explore a scenario</span>{[['normal','Normal week'],['weekend','Weekend heavy'],['growth','Growing sales'],['seasonal','Seasonal'],['change','Demand shift']].map(([id,label])=><button key={id} aria-pressed={(report.scenario||'normal')===id} disabled={busy} onClick={()=>scenario(id)}>{label}</button>)}</div>}
    {error&&<p className="error notice" role="alert">{error}</p>}
    <section className="kpi-grid" aria-label="Sales metrics">{[['Historical sales',money(total),'Across the loaded dataset'],['Daily average',money(total/data.length),'Actual sales per calendar day'],[`Next ${horizon} ${horizon===1?'day':'days'}`,money(future),change===null?'No previous-week comparison':`${change>=0?'+':''}${change.toFixed(1)}% vs the previous period`],['Model error',money(result.metrics.model_mae),'MAE on chronological holdout']].map(([label,value,note])=><article className="kpi" key={label}><small>{label}</small><strong>{value}</strong><span>{note}</span></article>)}</section>
    <section className="panel trajectory"><div className="panel-head"><div><small>SALES TRAJECTORY</small><h2>History meets the next week</h2></div><div className="range-tabs">{[30,60,90].map(n=><button aria-pressed={range===n} key={n} onClick={()=>setRange(n)}>{n} days</button>)}</div></div><SalesChart history={data.slice(-range)} forecast={forecast}/></section>
    <div className="analytics-grid"><section className="panel forecast-panel"><div className="panel-head"><div><small>{horizon}-DAY OUTLOOK</small><h2>Plan the week ahead</h2></div><span>Estimates, not guarantees</span></div>{forecast.map(row=><div className="forecast-row" key={row.date}><span>{new Date(row.date+'T12:00:00').toLocaleDateString(undefined,{weekday:'short'})}<small>{dateLabel(row.date)}</small></span><div className="forecast-track"><div style={{transform:`scaleX(${row.sales/maxForecast})`}}/></div><strong>{money(row.sales)}</strong></div>)}</section>
    <section className="panel weekday-panel"><small>WEEKLY RHYTHM</small><h2>When your business is busiest</h2><div className="weekday-bars">{days.map(day=><div key={day.label}><span>{money(day.value)}</span><div className="weekday-track"><i style={{transform:`scaleY(${day.value/maxDay})`}}/></div><small>{day.label}</small></div>)}</div><p>Average daily sales by weekday across the loaded history.</p></section></div>
    <div className="analytics-grid"><section className="panel analyst"><div className="panel-head"><div><small>AI ANALYST</small><h2>A closer look at the numbers</h2></div><span>{answer?.mode==='openai'?'OpenAI response':'Offline examples available'}</span></div><p>Ask about this dataset or the computed forecast.</p><div className="prompts">{['Summarize the sales history.','What is the seven-day forecast?'].map(q=><button disabled={busy} key={q} onClick={()=>ask(q)}>{q}</button>)}</div><div className="analyst-response" aria-live="polite">{busy?'Calculating…':answer?.answer||'Choose a question to begin. Answers use the loaded dataset.'}</div><form onSubmit={e=>{e.preventDefault();ask(question)}}><input aria-label="Question for analyst" value={question} onChange={e=>setQuestion(e.target.value)}/><button disabled={busy||!question.trim()}>Ask analyst</button></form></section>
    <section className="panel evaluation"><small>MODEL CHECK</small><h2>Keep the baseline in view</h2><div className="comparison"><div><span>Selected model</span><strong>{money(result.metrics.model_mae)}</strong></div><div><span>Repeat last week</span><strong>{money(result.metrics.baseline_mae)}</strong></div></div><p>MAE measures the average absolute sales error on held-out dates. Lower is better. A simple baseline can outperform the model.</p></section></div>
    <section className="panel pipeline-panel"><div><small>DATA PIPELINE</small><h2>What happened under the hood</h2><p>Measured data transformations and model configuration. No simulated AI reasoning.</p></div><div className="pipeline-stages">{[['01','Normalize',`${data.length} daily records`],['02','Prepare',`${report.duplicate_rows_aggregated||0} duplicate rows aggregated`],['03','Fit',report.model||'Forecast model'],['04','Evaluate',`Holdout starts ${report.evaluation_start||'at the latest period'}`],['05','Forecast',`${horizon} future days`]].map(([number,label,detail])=><div key={number}><small>{number}</small><h3>{label}</h3><p>{detail}</p></div>)}</div><details><summary>Data quality and limitations</summary><p>{report.missing_days_filled||0} missing days filled. Sales retain the meaning of the selected source column. Forecasts cannot anticipate unexpected events; Square estimates may differ from accounting reports.</p></details></section>
    <footer>ForecastOps AI · Built with Python and Pandas. Forecasts are estimates.</footer>
  </main>
}
