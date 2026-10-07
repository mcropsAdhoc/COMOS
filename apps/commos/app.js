const el=id=>document.getElementById(id);
const cfg=window.COMMOS_CONFIG||{};
const demo={
  metrics:{lots:148,runs:32,pending_approvals:5,trades:18,skills:8},
  agents:[
    {name:"Market Agent",purpose:"Price discovery, spreads and market context",status:"READY"},
    {name:"Trade Agent",purpose:"Buyer matching, offers and execution plans",status:"GUARDED"},
    {name:"Finance Agent",purpose:"Inventory, warehouse and pre-export finance",status:"READY"},
    {name:"Risk Agent",purpose:"Price, collateral and counterparty exposure",status:"READY"},
    {name:"Compliance Agent",purpose:"Traceability, EUDR and policy checks",status:"READY"},
    {name:"Settlement Agent",purpose:"Programmable settlement through AgPay",status:"GUARDED"}
  ],
  lot:{lot_id:"agros:lot:UG:COFFEE-00142",commodity:"Arabica coffee",quantity:12500,unit:"kg",grade:"AA",origin:"Bushenyi, Uganda",owner:"Kyamuhunga Cooperative",warehouse:"WH-BSH-04",eudr:"Ready",status:"Available"},
  skills:[
    {name:"commodity.lot.create",risk:"low",approval:false},
    {name:"market.quote",risk:"low",approval:false},
    {name:"trade.propose",risk:"medium",approval:false},
    {name:"finance.assess",risk:"medium",approval:false},
    {name:"risk.assess",risk:"medium",approval:false},
    {name:"compliance.check",risk:"medium",approval:false},
    {name:"trade.execute",risk:"critical",approval:true},
    {name:"settlement.execute",risk:"critical",approval:true}
  ],
  events:[
    {time:"16:51:19",type:"commos.run.created",entity:"CM-8D17A3",result:"Intent: sell"},
    {time:"16:50:44",type:"market.quote.generated",entity:"COFFEE-00142",result:"Reference value $54,375"},
    {time:"16:49:21",type:"compliance.check.completed",entity:"COFFEE-00142",result:"EUDR ready"},
    {time:"16:47:55",type:"trade.proposed",entity:"trade_4092",result:"Awaiting approval"},
    {time:"16:42:13",type:"commodity.lot.created",entity:"COFFEE-00142",result:"12,500 kg · AA"}
  ]
};
const capabilities=[
  ["01","PostgreSQL commodity state","Persistent lots, runs, trades & market observations"],
  ["02","MCP / Agent Gateway","JSON-RPC discovery and governed tool invocation"],
  ["03","Deterministic planner","Structured intent → fixed skill dependency graph"],
  ["04","Commodity Order Book","Bid, offer, RFQ, acceptance and execution objects"],
  ["05","Warehouse Receipts","Custody, ownership, liens and collateral value"],
  ["06","Buyer Connectors","Exporter, processor and roaster adapter contracts"],
  ["07","Market Adapters","International + Uganda/East Africa normalized feeds"],
  ["08","Forwards & Hedge","Forward contracts and hedge coverage primitives"],
  ["09","EUDR Evidence","Lot-linked evidence packs and risk status"],
  ["10","AgPay Settlement","Approved settlement instruction bridge into AgrOS"],
  ["11","OPA Policy","Institutional policy evaluation with local fallback"],
  ["12","Agent Observability","Trace, latency, failure, exposure and provenance"]
];
const plans={
 sell:["market.quote","risk.assess","compliance.check","trade.propose","trade.execute","settlement.execute"],
 finance:["market.quote","risk.assess","finance.assess"],
 hedge:["market.quote","risk.assess","trade.propose"],
 assess:["market.quote","risk.assess","compliance.check"],
 settle:["compliance.check","settlement.execute"]
};
let approved=false;
let currentIntent="sell";
function badge(skill){
  const s=demo.skills.find(x=>x.name===skill)||{risk:"low",approval:false};
  return `<span class="badge ${s.risk==='critical'?'critical':''}">${s.approval?'APPROVAL':'AUTO'} · ${s.risk.toUpperCase()}</span>`;
}
function render(){
  const m=demo.metrics;
  el("metrics").innerHTML=[
    ["DIGITAL LOTS",m.lots,"canonical commodity assets"],
    ["AGENT RUNS",m.runs,"intent orchestration"],
    ["APPROVALS",m.pending_approvals,"value-moving actions"],
    ["TRADES",m.trades,"proposals & executions"],
    ["SKILLS",m.skills,"governed capabilities"]
  ].map(x=>`<div class="metric"><label>${x[0]}</label><strong>${x[1]}</strong><small>${x[2]}</small></div>`).join("");
  el("agents").innerHTML=demo.agents.map((a,i)=>`<div class="agent"><div class="agent-icon">0${i+1}</div><h3>${a.name}</h3><p>${a.purpose}</p><b class="${a.status==='GUARDED'?'guarded':''}">${a.status}</b></div>`).join("");
  const l=demo.lot;
  el("lot").innerHTML=`<div class="lot-id">${l.lot_id}</div><div class="lot-main"><h3>${l.commodity}</h3><strong>${l.quantity.toLocaleString()} ${l.unit}</strong></div><div class="lot-grid">${[["OWNER",l.owner],["ORIGIN",l.origin],["GRADE",l.grade],["WAREHOUSE",l.warehouse],["EUDR",l.eudr],["STATUS",l.status]].map(x=>`<div class="lot-field"><span>${x[0]}</span><b>${x[1]}</b></div>`).join("")}</div>`;
  el("capabilities").innerHTML=capabilities.map(x=>`<div class="skill"><code>${x[0]} · ${x[1]}</code><div class="skill-meta"><span>IMPLEMENTED</span><span>${x[2]}</span></div></div>`).join("");
  el("skills").innerHTML=demo.skills.map(s=>`<div class="skill"><code>${s.name}</code><div class="skill-meta"><span>${s.risk.toUpperCase()}</span><span>${s.approval?'HUMAN GATE':'AUTOMATED'}</span></div></div>`).join("");
  el("events").innerHTML=demo.events.map(e=>`<div class="event"><code>${e.time}</code><div><b>${e.type}</b><small>${e.entity}</small></div><span>${e.result}</span></div>`).join("");
  el("substrate").innerHTML=[
    ["01","AgrOS ID","Canonical actors, institutions and commodity ownership"],
    ["02","AgrOS Graph","Lot → farm → owner → warehouse → buyer → finance"],
    ["03","Skills + Policy","Typed capabilities with permission and approval checks"],
    ["04","AgPay + Ledger","Settlement, waterfall instructions and balanced records"],
    ["05","Audit Events","Immutable execution and provenance trail"]
  ].map(x=>`<div class="substrate-row"><span>${x[0]}</span><div><b>${x[1]}</b><p>${x[2]}</p></div></div>`).join("");
  renderPlan(currentIntent);
}
function renderPlan(intent){
  currentIntent=intent; approved=false;
  const steps=plans[intent];
  const needs=steps.some(s=>(demo.skills.find(x=>x.name===s)||{}).approval);
  el("plan").innerHTML=steps.map((s,i)=>`<div class="plan-step"><span>0${i+1}</span><b>${s}</b>${badge(s)}</div>`).join("");
  el("trace").innerHTML=steps.map((s,i)=>`<div class="trace-row"><span>0${i+1}</span><b>${s}</b><small>${(demo.skills.find(x=>x.name===s)||{}).approval?'WAITING HUMAN':'READY'}</small></div>`).join("");
  el("run-state").textContent=needs?"APPROVAL REQUIRED":"READY";
  el("run-state").className="badge "+(needs?"guarded":"");
  el("approve").style.display=needs?"block":"none";
}
el("intent").addEventListener("change",e=>currentIntent=e.target.value);
el("plan-button").addEventListener("click",()=>renderPlan(el("intent").value));
el("approve").addEventListener("click",()=>{
  approved=true; el("run-state").textContent="APPROVED";el("run-state").className="badge";
  el("approve").textContent="✓ Approved · execute via AgrOS";el("approve").disabled=true;
  document.querySelectorAll(".trace-row small").forEach(x=>x.textContent="AUTHORIZED");
  setTimeout(()=>{el("approve").textContent="Approve value-moving steps";el("approve").disabled=false},1800);
});
el("run-demo").addEventListener("click",()=>{el("intent").value="sell";renderPlan("sell");el("run-demo").textContent="✓ Sell flow planned";setTimeout(()=>el("run-demo").textContent="Run commodity flow",1500)});
async function connect(){
  render();
  if(!cfg.apiUrl)return;
  try{
    const base=cfg.apiUrl.replace(/\/$/,"");
    const r=await fetch(base+"/v1/commos/dashboard");
    if(!r.ok)throw new Error("offline");
    const live=await r.json();
    demo.metrics={lots:live.lots,runs:live.runs,pending_approvals:live.pending_approvals,trades:live.trades,skills:live.skills};
    if(live.agents) demo.agents=live.agents.map(a=>({name:a.name,purpose:a.purpose,status:a.status.toUpperCase()}));
    el("connection").textContent="LIVE COMMOS API";
    render();
  }catch(e){el("connection").textContent="DEMO · API OFFLINE"}
}
connect();