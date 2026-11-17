import { ApiClient } from "@/services/api-client";
import { localDateOnly } from "@/lib/local-date";
import type { CoachTransport,Conversation,HistoryMessage,CoachReply,SendCoachInput } from "@/types/coach";
import type { PlannerAdjustmentApi } from "@/types/api";
export class CoachApi implements CoachTransport {
  private client:ApiClient;
  constructor(token:string){this.client=new ApiClient(token,240_000);}
  conversations(offset=0){return this.client.get<Conversation[]>("/coach/sessions?limit=30&offset="+offset);}
  create(){return this.client.post<{session_id:string}>("/coach/sessions",{});}
  memory(){return this.client.get<{id:string;category:string;content:string}[]>("/coach/memory");}
  forget(id:string){return this.client.delete("/coach/memory/"+encodeURIComponent(id));}
  messages(id:string,offset=0){return this.client.get<HistoryMessage[]>("/coach/sessions/"+encodeURIComponent(id)+"/messages?limit=30&offset="+offset);}
  send(id:string,body:SendCoachInput){return this.client.post<CoachReply>("/coach/sessions/"+encodeURIComponent(id)+"/messages",{ ...body, local_date: localDateOnly(new Date()) });}
  rename(id:string,title:string){return this.client.patch<Conversation>("/coach/sessions/"+encodeURIComponent(id),{title});}
  remove(id:string){return this.client.delete("/coach/sessions/"+encodeURIComponent(id));}
  preview(id:string){return this.client.get<PlannerAdjustmentApi>("/planner/adjustments/"+encodeURIComponent(id));}
  decide(conversation:string,id:string,operation:"apply"|"reject"|"revert"){
    return this.client.post<PlannerAdjustmentApi>("/coach/sessions/"+encodeURIComponent(conversation)+"/adjustments/"+encodeURIComponent(id)+"/"+operation,{confirmed:true});
  }
}
