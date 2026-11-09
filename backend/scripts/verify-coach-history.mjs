// Real HTTP integration with explicit NLU/DB fixtures; never connects to Supabase.
import 'reflect-metadata';
import { Module, ValidationPipe, UnauthorizedException, ConflictException } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { randomUUID, randomBytes, createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { CoachController } from '../dist/coach/coach.controller.js';
import ts from 'typescript';
import { CoachHistoryService } from '../dist/coach/coach-history.service.js';
import { CoachService } from '../dist/coach/coach.service.js';
import { CoachAiClient } from '../dist/coach/coach-ai.client.js';
import { CoachContextService } from '../dist/coach/coach-context.service.js';
import { PlannerAdjustmentsService } from '../dist/planner/planner-adjustments.service.js';
import { SupabaseService } from '../dist/supabase/supabase.service.js';
import { SupabaseAuthGuard } from '../dist/auth/supabase-auth.guard.js';
import { RequestTimeoutInterceptor } from '../dist/common/interceptors/request-timeout.interceptor.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const output=path.join(root,'ai/artifacts/coach_history/1.0.1');
if(fs.existsSync(output))throw Error('Verification already exists');
const python=process.env.EVOLV_TEST_PYTHON;
if(!python)throw Error('Set EVOLV_TEST_PYTHON to the existing model environment executable');
const reserve=createServer();reserve.listen(0,'127.0.0.1');await once(reserve,'listening');
const port=reserve.address().port;await new Promise(r=>reserve.close(r));
const key=randomBytes(32).toString('hex');
const child=spawn(python,[path.join(root,'ai/tests/fixtures/serve_coach_api.py'),String(port)],
  {cwd:root,env:{...process.env,EVOLV_AI_SERVICE_KEY:key},stdio:'ignore',windowsHide:true});
let app;
const helper=path.join(root,'backend/node_modules/.cache/evolv-history-fixture.mjs');
fs.mkdirSync(path.dirname(helper),{recursive:true});
fs.writeFileSync(helper,ts.transpileModule(fs.readFileSync(path.join(root,'backend/test/fixtures/coach-postgres.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2023}}).outputText);
const {coachDatabase}=await import('file:///'+helper.replaceAll('\\','/'));
const fixture=await coachDatabase();
let revision='v1';
const user=randomUUID(),other=randomUUID(),plan=randomUUID(),day=randomUUID();
const rows=new Map();let previewCalls=0,applyCalls=0;
await fixture.user(user);await fixture.user(other);
const checks=[];
function check(name,condition){assert.ok(condition,name);checks.push(name);}
try{
  let ready=false;
  for(let i=0;i<100;i++){
    if(child.exitCode!==null)throw Error('Fixture exited');
    try{ready=(await fetch('http://127.0.0.1:'+port+'/health/ready',
      {headers:{Authorization:'Bearer '+key},signal:AbortSignal.timeout(1000)})).ok;}catch{}
    if(ready)break;
    await new Promise(r=>setTimeout(r,200));
  }
  assert.ok(ready,'Python fixture readiness');
  const config={get:(name,fallback)=>({
    COACH_AI_ENABLED:true,COACH_AI_SERVICE_KEY:key,COACH_AI_URL:'http://127.0.0.1:'+port,
    COACH_AI_TIMEOUT_MS:5000,COACH_REQUEST_TIMEOUT_MS:15000
  }[name]??fallback)};
  const context={build:async(owner)=>({actor_id:owner,revision,workout_plan_id:plan,diet_plan_id:null,
    days:[{id:day,weekday:'tuesday'}],workout_exercises:[],exercises:[],meal_items:[],foods:[]})};
  const planner={
    preview:async(owner,token,dto)=>{assert.equal(owner,user);assert.equal(token,'fixture-user');
      previewCalls++;const row={id:randomUUID(),user_id:owner,status:'pending',dto};rows.set(row.id,row);await fixture.db.query('insert into planner_adjustments(id,user_id,status,reason,source,requested_change) values ($1,$2,$3,$4,$5,$6::jsonb)',[row.id,owner,'pending',dto.reason,'coach',JSON.stringify(dto)]);return row;},
    get:async(owner,_token,id)=>{assert.equal(rows.get(id)?.user_id,owner);return rows.get(id);},
    apply:async(owner,_token,id)=>{const r=rows.get(id);assert.equal(r?.user_id,owner);
      if(r.status!=='pending')throw new ConflictException('not_pending');applyCalls++;r.status='applied';return r;},
    reject:async(_owner,_token,id)=>{const r=rows.get(id);r.status='rejected';return r;},
    revert:async(_owner,_token,id)=>{const r=rows.get(id);r.status='reverted';return r;},
  };
  class TestModule {}
  Module({controllers:[CoachController],providers:[CoachService,CoachAiClient,CoachHistoryService,SupabaseAuthGuard,
    {provide:ConfigService,useValue:config},{provide:CoachContextService,useValue:context},
    {provide:PlannerAdjustmentsService,useValue:planner},{provide:SupabaseService,useValue:{
      forUser:(token)=>fixture.supabase.forUser(token==='fixture-user'?user:other),
      getUser:async(token)=>{if(token==='fixture-user')return{id:user};
        if(token==='fixture-other')return{id:other};throw new UnauthorizedException();}
    }}]})(TestModule);
  app=await NestFactory.create(TestModule,{logger:false});
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  app.useGlobalInterceptors(new RequestTimeoutInterceptor(config));
  await app.listen(0,'127.0.0.1');
  let base=await app.getUrl();
  async function request(route,body,token='fixture-user',method='POST'){
    const r=await fetch(base+'/api/coach/'+route,{method,
      headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),
        'X-Evolv-User-ID':other},body:body===undefined?undefined:JSON.stringify(body)});
    const text=await r.text();return {status:r.status,body:text?JSON.parse(text):null};
  }
  check('unauthenticated_denied',(await request('sessions',{},null)).status===401);
  check('client_identity_rejected',(await request('sessions',{user_id:other})).status===400);
  const created=await request('sessions',{});check('session_created',created.status===201);
  const sid=created.body.session_id;
  const ask=await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'Mova o treino de 03/11/2026 para 05/11/2026'});
  const proposal=ask.body.result.actions[0];
  check('typed_pending_proposal',proposal.status==='pending_user_confirmation');
  check('proposal_not_applied',previewCalls===0&&applyCalls===0);
  const confirm={request_id:randomUUID(),text:'confirmo',proposal_id:proposal.id};
  const preview=await request('sessions/'+sid+'/messages',confirm);
  check('planner_preview_created',preview.body.planner_previews.length===1&&previewCalls===1&&applyCalls===0);
  const aid=preview.body.planner_previews[0].id;
  await request('sessions/'+sid+'/messages',confirm);
  check('preview_not_duplicated',previewCalls===1);
  check('false_confirmation_rejected',(await request('sessions/'+sid+'/adjustments/'+aid+'/apply',{confirmed:false})).status===400&&applyCalls===0);
  check('other_user_denied',(await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'Oi'},'fixture-other')).status===404);
  const applied=await request('sessions/'+sid+'/adjustments/'+aid+'/apply',{confirmed:true});
  check('explicit_apply_only',applied.status===201&&applyCalls===1);
  check('unrelated_adjustment_denied',(await request('sessions/'+sid+'/adjustments/'+randomUUID()+'/apply',{confirmed:true})).status===404);
  const again=await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'Mova o treino de 03/11/2026 para 05/11/2026'});
  revision='v2';
  const stale=await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'confirmo',proposal_id:again.body.result.actions[0].id});
  check('stale_snapshot_not_previewed',stale.body.planner_previews.length===0&&previewCalls===1);
  const listing=await request('sessions',undefined,'fixture-user','GET');
  check('conversation_persisted',listing.body.some(c=>c.id===sid));
  const page=await request('sessions/'+sid+'/messages',undefined,'fixture-user','GET');
  check('message_pairs_persisted',page.body.length===8);
  await app.close();
  app=await NestFactory.create(TestModule,{logger:false});
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  await app.listen(0,'127.0.0.1');base=await app.getUrl();
  const restoredList=await request('sessions',undefined,'fixture-user','GET');
  check('conversation_survives_nest_restart',restoredList.body.some(c=>c.id===sid));
  const cachedTurn=await request('sessions/'+sid+'/messages',confirm);
  check('durable_request_dedup_after_restart',cachedTurn.status===201&&previewCalls===1);
  const restoredTurn=await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'Preciso de ajuda'});
  check('context_restored_to_new_ai_session',restoredTurn.status===201&&restoredTurn.body.result.analysis.fixture_context_received.includes('Mova'));
  const foreignHistory=await request('sessions/'+sid+'/messages',undefined,'fixture-other','GET');
  check('history_owner_isolation',foreignHistory.status===404);
  check('session_deleted',(await request('sessions/'+sid,undefined,'fixture-user','DELETE')).status===200);
  check('deleted_session_not_found',(await request('sessions/'+sid+'/messages',{request_id:randomUUID(),text:'Oi'})).status===404);
  fs.mkdirSync(output,{recursive:true});
  fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({phase:'7.06.3',real_nest_fastapi_http:true,
    production_auth_guard_executed:true,supabase_auth_is_fixture:true,database:'embedded_postgresql_actual_rls',
    nlp_intent_is_explicit_fixture:true,real_entity_extractor:true,real_lm_used:false,
    checks_passed:checks.length,checks,preview_calls:previewCalls,apply_fixture_calls:applyCalls,
    remote_database_writes:0,local_postgresql_persistence_tested:true},null,2));
  const files=['backend/src/coach/coach-history.service.ts','backend/test/fixtures/coach-postgres.ts','backend/src/coach/coach.service.ts','backend/src/coach/coach-ai.client.ts',
    'backend/src/coach/coach.controller.ts','backend/src/coach/coach-context.service.ts',
    'ai/src/evolv_api/app.py','ai/tests/fixtures/serve_coach_api.py','backend/scripts/verify-coach-history.mjs'];
  const hashes=Object.fromEntries(files.map(f=>[f,createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]));
  fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify({code:hashes},null,2));
  console.log(JSON.stringify({checks_passed:checks.length,real_http:true,database:'embedded_postgresql'}));
}finally{
  if(app)await app.close();
  child.kill();
  await fixture.db.close();
  fs.unlinkSync(helper);
}
