import type { CoachTransport,ChatMessage,Conversation,SendCoachInput,CoachProposal } from "../types/coach";
import type { PlannerAdjustmentApi } from "../types/api";
export type CoachState = {
  conversationId:string|null;conversations:Conversation[];messages:ChatMessage[];
  busy:boolean;error:string|null;failedSend:SendCoachInput|null;
  hasMoreMessages:boolean;hasMoreConversations:boolean;preview:PlannerAdjustmentApi|null;
};
export function coachDisplayText(text:string){
  return text.replace(/\[kb:[^\]\s]+\]/g,"").replace(/\*\*([^*]+)\*\*/g,"$1").replace(/\s+([.,;:!?])/g,"$1").trim();
}
function historyReply(value:unknown){
  if(!value||typeof value!=="object")return undefined;
  const r=value as import("../types/coach").CoachReply;
  return r.result&&typeof r.result.answer==="string"&&Array.isArray(r.result.actions)?r:undefined;
}
export function coachError(error:unknown){
  const e=error as {status?:number;code?:string;message?:string};
  if(e.status===401)return "Sua sessão expirou. Entre novamente.";
  if(e.status===429)return "O Coach está ocupado. Aguarde um pouco e tente novamente.";
  if(e.status===404)return "Esta conversa ou proposta não está mais disponível. Atualize o histórico.";
  if(e.status===409)return "O plano ou a proposta mudou. Atualize a conversa antes de continuar.";
  if(e.status===503)return "O Coach está indisponível agora. Seu histórico continua disponível.";
  if(e.code==="API_TIMEOUT"||e.status===408||e.status===504)return "A resposta demorou. Tente novamente para consultar o mesmo pedido.";
  return "Não foi possível concluir. Confira sua conexão e tente novamente.";
}
export class CoachSession {
  private state:CoachState={conversationId:null,conversations:[],messages:[],busy:false,error:null,
    failedSend:null,hasMoreMessages:false,hasMoreConversations:false,preview:null};
  private listeners=new Set<()=>void>();
  private disposed=false;
  private messageOffset=0;
  private conversationOffset=0;
  private api:CoachTransport;
  private uuid:()=>string;
  readonly ownerId:string;
  constructor(api:CoachTransport,uuid:()=>string,ownerId=""){this.api=api;this.uuid=uuid;this.ownerId=ownerId;}
  setTransport(api:CoachTransport){if(!this.disposed)this.api=api;}
  getSnapshot=()=>this.state;
  subscribe=(fn:()=>void)=>{this.listeners.add(fn);return()=>this.listeners.delete(fn);};
  dispose(){this.disposed=true;this.listeners.clear();}
  private set(patch:Partial<CoachState>){if(this.disposed)return;this.state={...this.state,...patch};this.listeners.forEach(fn=>fn());}
  private async run(fn:()=>Promise<void>){
    if(this.disposed||this.state.busy)return;
    this.set({busy:true,error:null});
    try{await fn();}catch(e){this.set({error:coachError(e)});}
    finally{this.set({busy:false});}
  }
  loadConversations(more=false){return this.run(async()=>{
    const offset=more?this.conversationOffset:0;
    const rows=await this.api.conversations(offset);if(this.disposed)return;
    this.conversationOffset=offset+rows.length;
    this.set({conversations:more?unique([...this.state.conversations,...rows]):rows,hasMoreConversations:rows.length===30});
  });}
  newConversation(){
    if(this.state.busy||this.state.failedSend)return;
    this.messageOffset=0;
    this.set({conversationId:null,messages:[],preview:null,error:null,hasMoreMessages:false});
  }
  select(id:string){return this.run(async()=>{
    if(this.state.failedSend)throw new Error("Unresolved request");
    this.set({conversationId:id,messages:[],preview:null,hasMoreMessages:false});
    this.messageOffset=0;
    const rows=await this.api.messages(id);if(this.disposed)return;
    this.messageOffset=rows.length;
    this.set({messages:unique(rows.slice().reverse().map(r=>({
      id:r.id,role:r.role,content:r.content,reply:historyReply(r.metadata?.response),live:false}))),hasMoreMessages:rows.length===30});
  });}
  older(){return this.run(async()=>{
    const id=this.state.conversationId;if(!id)return;
    const rows=await this.api.messages(id,this.messageOffset);if(this.disposed)return;
    this.messageOffset+=rows.length;
    this.set({messages:unique([...rows.slice().reverse().map(r=>({
      id:r.id,role:r.role,content:r.content,reply:historyReply(r.metadata?.response),live:false})),...this.state.messages]),
      hasMoreMessages:rows.length===30});
  });}
  send(text:string,proposalId?:string){
    if(!text.trim()||text.length>8000||this.state.failedSend)return Promise.resolve();
    return this.run(()=>this.transmit({request_id:this.uuid(),text:text.trim(),...(proposalId?{proposal_id:proposalId}:{})}));
  }
  retry(){return this.run(async()=>{if(this.state.failedSend)await this.transmit(this.state.failedSend);});}
  discardRetry(){if(!this.state.busy)this.set({failedSend:null,error:null});}
  private async transmit(body:SendCoachInput){
    let id=this.state.conversationId;
    try{
      if(!this.state.messages.some(m=>m.id===body.request_id))this.set({messages:[...this.state.messages,{
        id:body.request_id,role:"user",content:body.text,pending:true}]});
      if(!id){id=(await this.api.create()).session_id;if(this.disposed)return;this.set({conversationId:id});}
      const response=await this.api.send(id,body);if(this.disposed)return;
      if(response.session_id!==id||response.request_id!==body.request_id)throw new Error("Response identity mismatch");
      this.messageOffset+=2;
      this.set({messages:[...this.state.messages.map(m=>{
        if(m.id===body.request_id)return {...m,pending:false};
        if(body.proposal_id&&m.reply)return {...m,reply:{...m.reply,result:{...m.reply.result,actions:m.reply.result.actions.map(a=>
          a.id===body.proposal_id?(response.result.actions.find(next=>next.id===a.id)??{...a,status:"stale" as const}):a)}}};
        return m;
      }),{
        id:body.request_id+":assistant",role:"assistant",content:response.result.answer,reply:response,live:true}],
        failedSend:null});
      const list=await this.api.conversations().catch(()=>null);
      if(list&&!this.disposed){this.conversationOffset=list.length;this.set({conversations:list,hasMoreConversations:list.length===30});}
    }catch(error){if(!this.disposed)this.set({failedSend:body});throw error;}
  }
  proposal(proposal:CoachProposal,confirm:boolean){
    if(proposal.status!=="pending_user_confirmation"||Date.parse(proposal.expires_at)<=Date.now())return Promise.resolve();
    return this.send(confirm?"confirmo":"rejeito",proposal.id);
  }
  rename(id:string,title:string){return this.run(async()=>{
    const clean=title.trim();if(!clean||clean.length>80)return;
    const row=await this.api.rename(id,clean);
    this.set({conversations:this.state.conversations.map(c=>c.id===id?row:c)});
  });}
  remove(id:string){return this.run(async()=>{
    await this.api.remove(id);if(this.disposed)return;
    if(this.state.conversationId===id)this.set({conversationId:null,messages:[],failedSend:null,preview:null,hasMoreMessages:false});
    this.set({conversations:this.state.conversations.filter(c=>c.id!==id)});
  });}
  review(id:string){return this.run(async()=>{const preview=await this.api.preview(id);this.set({preview});});}
  closePreview(){if(!this.state.busy)this.set({preview:null});}
  decide(operation:"apply"|"reject"|"revert"){return this.run(async()=>{
    const id=this.state.conversationId,preview=this.state.preview;if(!id||!preview)return;
    if(operation!=="revert"&&preview.status!=="pending")return;
    if(operation==="revert"&&(!preview.reversible||!preview.applied_at||preview.reverted_at))return;
    const next=await this.api.decide(id,preview.id,operation);
    this.set({preview:next,messages:this.state.messages.map(m=>m.reply?{...m,reply:{...m.reply,
      planner_previews:m.reply.planner_previews?.map(p=>p.id===next.id?next:p)}}:m)});
  });}
}
function unique<T extends {id:string}>(rows:T[]):T[]{return [...new Map(rows.map(row=>[row.id,row])).values()];}
