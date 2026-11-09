const {test}=require("node:test");
const assert=require("node:assert/strict");
const {CoachSession,coachError}=require("../src/lib/coach-session.ts");
function setup(){
  let count=0,sendCalls=[],decisions=[],history=[];
  const api={
    conversations:async()=>[{id:"c1",title:"Minha conversa",updated_at:"2026-11-03",created_at:"2026-11-03"}],
    create:async()=>({session_id:"c1"}),
    messages:async()=>history,
    send:async(id,body)=>{sendCalls.push(body);return{session_id:id,request_id:body.request_id,result:{answer:"Resposta real do servidor",actions:[]}};},
    rename:async(id,title)=>({id,title}),remove:async()=>{},
    preview:async()=>({id:"p1",status:"pending",preview:{title:"Mover",summary:"Resumo",changes:[],preserved:[],warnings:[]}}),
    decide:async(c,id,op)=>{decisions.push(op);return{id,status:op==="apply"?"applied":"rejected",preview:{title:"Mover"}};},
  };
  return {api,store:new CoachSession(api,()=>"request-"+(++count)),sendCalls,decisions,setHistory(rows){history=rows;}};
}
test("envia ao servidor e nao fabrica resposta local",async()=>{
  const t=setup();await t.store.send("Minha dúvida");
  const s=t.store.getSnapshot();
  assert.equal(s.messages.length,2);assert.equal(s.messages[1].content,"Resposta real do servidor");
  assert.equal(s.conversationId,"c1");assert.equal(t.decisions.length,0);
});
test("timeout repete o mesmo request_id sem duplicar bolha do usuario",async()=>{
  const t=setup();const original=t.api.send;let fail=true;
  const observed=[];
  t.api.send=async(id,body)=>{observed.push(body.request_id);if(fail){fail=false;throw{code:"API_TIMEOUT"};}return original(id,body);};
  await t.store.send("Pergunta");
  assert.ok(t.store.getSnapshot().failedSend);
  await t.store.retry();
  assert.equal(observed[0],observed[1]);
  assert.equal(t.store.getSnapshot().messages.filter(m=>m.role==="user").length,1);
  assert.equal(t.store.getSnapshot().failedSend,null);
});
test("operacao em andamento impede duplo envio e troca de conversa",async()=>{
  const t=setup();let finish;
  t.api.send=(id,body)=>new Promise(resolve=>{finish=()=>resolve({session_id:id,request_id:body.request_id,result:{answer:"Ok",actions:[]}});});
  const sending=t.store.send("Primeira");await new Promise(resolve=>setImmediate(resolve));
  await t.store.send("Segunda");t.store.newConversation();
  assert.equal(t.store.getSnapshot().messages.length,1);
  finish();await sending;assert.equal(t.store.getSnapshot().messages.length,2);
});
test("historia e invertida para conversa e propostas antigas nao ficam vivas",async()=>{
  const t=setup();t.setHistory([{id:"a",role:"assistant",content:"Resposta",metadata:{response:{result:{actions:[]}}}},
    {id:"u",role:"user",content:"Pergunta"}]);
  await t.store.select("c1");
  assert.equal(t.store.getSnapshot().messages[0].id,"u");
  assert.equal(t.store.getSnapshot().messages[1].live,false);
});
test("proposta so pede previa e aplicacao exige metodo separado",async()=>{
  const t=setup();
  await t.store.proposal({id:"proposal",status:"pending_user_confirmation",expires_at:"2099-01-01",payload:{}},true);
  assert.equal(t.sendCalls[0].proposal_id,"proposal");assert.equal(t.decisions.length,0);
  await t.store.review("p1");assert.equal(t.decisions.length,0);
  await t.store.decide("apply");assert.deepEqual(t.decisions,["apply"]);
});
test("proposta expirada nao e enviada e previa consultada nao aplica sozinha",async()=>{
  const t=setup();await t.store.proposal({id:"p",status:"pending_user_confirmation",expires_at:"2000-01-01"},true);
  assert.equal(t.sendCalls.length,0);await t.store.review("p1");assert.equal(t.decisions.length,0);
});
test("resposta de conta anterior e ignorada apos descarte do controlador",async()=>{
  const t=setup();let finish;
  t.api.send=(id,body)=>new Promise(resolve=>{finish=()=>resolve({session_id:id,request_id:body.request_id,result:{answer:"Privado",actions:[]}});});
  const p=t.store.send("Minha mensagem");await new Promise(resolve=>setImmediate(resolve));
  t.store.dispose();finish();await p;
  assert.equal(t.store.getSnapshot().messages.some(m=>m.content==="Privado"),false);
  assert.deepEqual(setup().store.getSnapshot().messages,[]);
});
test("renova token preservando conversa e exclui apenas apos chamada explicita",async()=>{
  const t=setup();await t.store.send("Pergunta");
  const next={...t.api,remove:async()=>{next.deleted=true;}};
  t.store.setTransport(next);assert.equal(t.store.getSnapshot().conversationId,"c1");
  assert.equal(next.deleted,undefined);await t.store.remove("c1");
  assert.equal(next.deleted,true);assert.equal(t.store.getSnapshot().conversationId,null);
});
test("erros de ocupacao, auth e timeout sao explicados sem detalhes internos",()=>{
  assert.match(coachError({status:429}),/ocupado/);
  assert.match(coachError({status:401}),/sessão/);
  assert.match(coachError({code:"API_TIMEOUT"}),/mesmo pedido/);
  assert.equal(coachError(new Error("secret credential")),"Não foi possível concluir. Confira sua conexão e tente novamente.");
});
test("entrada vazia e acima do limite nao fazem requisicao",async()=>{
  const t=setup();await t.store.send(" ");await t.store.send("x".repeat(8001));
  assert.equal(t.sendCalls.length,0);
});
test("falha ao criar conversa preserva texto e id para nova tentativa",async()=>{
  const t=setup();let first=true;
  t.api.create=async()=>{if(first){first=false;throw Error("offline");}return{session_id:"c1"};};
  await t.store.send("Não perder esta pergunta");
  assert.equal(t.store.getSnapshot().messages[0].content,"Não perder esta pergunta");
  const id=t.store.getSnapshot().failedSend.request_id;
  await t.store.retry();
  assert.equal(t.sendCalls[0].request_id,id);
  assert.equal(t.store.getSnapshot().messages.length,2);
});
test("historico antigo sem envelope valido ainda mostra texto",async()=>{
  const t=setup();t.setHistory([{id:"old",role:"assistant",content:"Mensagem antiga",metadata:{response:{legacy:true}}}]);
  await t.store.select("c1");assert.equal(t.store.getSnapshot().messages[0].content,"Mensagem antiga");
  assert.equal(t.store.getSnapshot().messages[0].reply,undefined);
});
test("texto de interface remove identificadores internos sem interpretar HTML",()=>{
  const {coachDisplayText}=require("../src/lib/coach-session.ts");
  assert.equal(coachDisplayText("**Descanso** importa [kb:rest:v1:001]."),"Descanso importa.");
  assert.equal(coachDisplayText("<script>literal</script>"),"<script>literal</script>");
});
