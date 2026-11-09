import type { PlannerAdjustmentApi, CreatePlannerAdjustmentInput } from "./api";
export type Conversation = { id:string; title:string|null; created_at:string; updated_at:string };
export type CoachProposal = {
  id:string; status:"pending_user_confirmation"|"confirmed_for_planner_preview"|"rejected"|"expired"|"stale";
  expires_at:string; payload:CreatePlannerAdjustmentInput;
};
export type CoachResult = {
  answer:string; actions:CoachProposal[];
  citations?:{supplied_chunk_ids:string[];cited_chunk_ids:string[]};
  retrieval?:{matches:{id:string;title:string;citations?:{title:string;url?:string}[]}[]};
  generation?:{stopped_at_eos?:boolean}|null;
  grounding?:{status:string};
};
export type CoachReply = {session_id:string;request_id:string;result:CoachResult;planner_previews?:PlannerAdjustmentApi[]};
export type HistoryMessage = {id:string;role:"user"|"assistant";content:string;created_at:string;
  metadata?:{request_id?:string;response?:CoachReply}};
export type ChatMessage = {id:string;role:"user"|"assistant";content:string;reply?:CoachReply;live?:boolean;pending?:boolean};
export type SendCoachInput = {request_id:string;text:string;proposal_id?:string};
export interface CoachTransport {
  conversations(offset?:number):Promise<Conversation[]>;
  create():Promise<{session_id:string}>;
  messages(id:string,offset?:number):Promise<HistoryMessage[]>;
  send(id:string,body:SendCoachInput):Promise<CoachReply>;
  rename(id:string,title:string):Promise<Conversation>;
  remove(id:string):Promise<unknown>;
  preview(id:string):Promise<PlannerAdjustmentApi>;
  decide(conversation:string,id:string,operation:"apply"|"reject"|"revert"):Promise<PlannerAdjustmentApi>;
}
