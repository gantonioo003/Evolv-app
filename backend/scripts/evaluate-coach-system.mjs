// Real services, real models, real Supabase and Planner. Only temporary users.
// Never log, export or persist credentials. Run from backend/ after npm run build.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { once } from 'node:events';
import { parseEnv } from 'node:util';
import { createRequire } from 'node:module';
import { randomUUID, randomBytes, createHash } from 'node:crypto';
import { spawn, execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { createClient } from '@supabase/supabase-js';

const root=path.resolve('..');
const version=process.env.EVOLV_EVALUATION_VERSION||'1.0.0';
if(!/^\d+\.\d+\.\d+$/.test(version))throw Error('Invalid evaluation version');
const out=path.join(root,'ai/artifacts/system_evaluation',version);
if(fs.existsSync(path.join(out,'results.json'))||fs.existsSync(path.join(out,'inputs.json')))
 throw Error('Evaluation exists; choose a new version');
fs.mkdirSync(out,{recursive:true});
const env=parseEnv(fs.readFileSync('.env','utf8'));
const suiteFile=process.env.EVOLV_EVALUATION_SUITE||'ai/data/evaluation/coach_system.v1.json';
const suitePath=path.resolve(root,suiteFile);
if(path.dirname(suitePath)!==path.join(root,'ai','data','evaluation'))
 throw Error('Evaluation suite must be in ai/data/evaluation');
const suite=JSON.parse(fs.readFileSync(suitePath,'utf8'));
const subset=process.env.EVOLV_EVALUATION_CASE_IDS?.split(',').filter(Boolean);
const cases=subset?suite.cases.filter(c=>subset.includes(c.id)):suite.cases;
if(subset&&cases.length!==subset.length)throw Error('Unknown case filter');
const dialogues=subset?[]:suite.dialogues;
const report={phase:suite.phase||'7.06.5',version,started_at:new Date().toISOString(),status:'running',
 scope:'Development suite; real NestJS, FastAPI, frozen NLP, RAG, Qwen original, Supabase and Planner',
 suite_sha256:createHash('sha256').update(fs.readFileSync(suitePath)).digest('hex'),
 credentials_recorded:false,existing_user_data_modified:false,native_iphone_tested:false,
 checks:[],cases:[],dialogues:[],actions:[],temporary_users_created:0,temporary_users_deleted:0};
report.case_filter=subset??null;
const inputFiles=[path.relative(root,suitePath),'ai/scripts/serve_coach_evaluation.py',
 'ai/src/evolv_rag/grounding.py','ai/src/evolv_api/app.py','ai/configs/retrieval.runtime.v1.json',
 'ai/src/evolv_rag/retrieval_runtime.py','ai/src/evolv_rag/retrieval_hydration.py',
 ...(process.env.EVOLV_AI_NLP_VERSION==='1.9.0'?['ai/artifacts/baseline/1.9.0/manifest.json']:[]),
 'backend/scripts/evaluate-coach-system.mjs','ai/src/evolv_rag/coach.py','ai/src/evolv_rag/safety.py',
 'ai/configs/openlm.v1.json','ai/artifacts/baseline/1.8.0/selection_frozen.json',
 'backend/src/coach/coach.service.ts','backend/src/coach/coach-context.service.ts',
 'backend/src/planner/planner-adjustments.service.ts','mobile/src/components/coach-connected-screen.tsx',
 'mobile/src/app/adjustments/[adjustmentId].tsx'];
fs.writeFileSync(path.join(out,'inputs.json'),JSON.stringify({sha256:Object.fromEntries(inputFiles.map(f=>[
 f,createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]))},null,2));
const children=[],testUsers=[],users=[];
let admin,staticServer,browser,base='http://127.0.0.1:3199',aiBase,serviceKey;
const backendErrors=[];
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(report,null,2));
function check(name,ok,detail){report.checks.push({name,passed:Boolean(ok),...(detail?{detail}:{})});save();}
function publicClient(token){return createClient(env.SUPABASE_URL,env.SUPABASE_ANON_KEY,{
 auth:{persistSession:false,autoRefreshToken:false},
 ...(token?{global:{headers:{Authorization:'Bearer '+token}}}:{}),
});}
async function request(route,body,token=users[0]?.session.access_token,method=body===undefined?'GET':'POST'){
 const start=performance.now();
 const r=await fetch(base+'/api'+route,{method,headers:{'Content-Type':'application/json',
  ...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body),
  signal:AbortSignal.timeout(230000)});
 const text=await r.text();return{status:r.status,body:text?JSON.parse(text):null,seconds:(performance.now()-start)/1000};
}
async function until(fn,seconds=180){const start=performance.now();while(performance.now()-start<seconds*1000){
 if(await fn().catch(()=>false))return (performance.now()-start)/1000;
 if(children.some(p=>p.exitCode!==null))throw Error('Evaluation service exited');
 await new Promise(r=>setTimeout(r,500));
}throw Error('Service readiness timeout');}
async function createConversation(){const r=await request('/coach/sessions',{});assert.equal(r.status,201);return r.body.session_id;}
async function message(id,text,proposal_id,request_id=randomUUID()){
 const response=await request('/coach/sessions/'+id+'/messages',{request_id,text,...(proposal_id?{proposal_id}:{})});
 return {...response,request_id};
}
async function removeConversation(id){if(id)await request('/coach/sessions/'+id,undefined,users[0].session.access_token,'DELETE');}
function diagnostic(test,response){const result=response.body?.result;
 return {...test,http_status:response.status,total_seconds:response.seconds,result,
  checks:{http_ok:response.status===201,no_unknown_citations:result?.citations?.unknown_chunk_ids?.length===0,
   no_automatic_action:result?.planner?.writes_allowed===false,
   generated:Boolean(result?.generation),completed_generation:result?.generation?.stopped_at_eos??null,
   expected_risk_detected:test.expected_risk?(result?.analysis?.risk?.labels||[]).includes(test.expected_risk):null}};
}
async function targetState(kind){
 if(kind==='move_workout_day'){
  const plan=await request('/planner/plans/'+report.test_plan_id);
  return plan.body?.workout_days?.map(d=>[d.id,d.weekday]).sort();
 }
 const r=await publicClient(users[0].session.access_token).from('daily_activity_overrides')
  .select('activity_date,activity_type,nutrition_day_type').eq('user_id',testUsers[0]).order('activity_date');
 if(r.error)throw Error('Cannot inspect temporary activity state');return r.data;
}
async function exerciseAction(sid,proposal,test){
 const kind=proposal.payload.kind,before=await targetState(kind);
 const expected=test.expected_payload;
 if(expected){
  const paramsMatch=Object.entries(expected).every(([key,value])=>proposal.payload[key]===value);
  const originMatches=kind!=='move_workout_day'||(
   proposal.payload.workout_plan_id===report.test_plan_id&&
   before?.some(([id,weekday])=>id===proposal.payload.workout_day_id&&weekday==='tuesday'));
  check(test.id+'_exact_proposal',paramsMatch&&originMatches);
  if(!paramsMatch||!originMatches)return;
 }
 const confirmed=await message(sid,'confirmo',proposal.id);
 const p=confirmed.body?.planner_previews?.[0];
 const record={case_id:test.id,origin:'real_coach',kind,preview_http:confirmed.status,preview_created:Boolean(p)};
 report.actions.push(record);save();
 if(!p)return;
 check('preview_leaves_plan_unchanged_'+kind,JSON.stringify(before)===JSON.stringify(await targetState(kind)));
 const denied=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:false});
 check('false_confirmation_denied_'+kind,denied.status===400);
 const foreign=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true},users[1].session.access_token);
 check('other_user_cannot_apply_'+kind,foreign.status===404);
 const applied=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true});
 const after=await targetState(kind);
 record.apply_http=applied.status;record.state_changed=JSON.stringify(before)!==JSON.stringify(after);
 record.expected_state=expected?(kind==='move_workout_day'?
  after?.some(([id,weekday])=>id===proposal.payload.workout_day_id&&weekday===expected.target_weekday):
  after.some(r=>r.activity_date===expected.activity_date&&r.activity_type===expected.activity_type)):null;
 check('real_apply_changes_state_'+kind,applied.status===201&&record.state_changed&&record.expected_state!==false);
 const duplicate=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true});
 check('second_apply_denied_'+kind,[400,409].includes(duplicate.status));
 const reverted=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/revert',{confirmed:true});
 record.revert_http=reverted.status;record.original_state_restored=JSON.stringify(before)===JSON.stringify(await targetState(kind));
 check('real_revert_restores_state_'+kind,reverted.status===201&&record.original_state_restored);
}
try{
 if(!process.env.EVOLV_TEST_PYTHON||!process.env.EVOLV_SUPABASE_CLI)throw Error('Missing evaluation runtime paths');
 const keys=JSON.parse(execFileSync(process.env.EVOLV_SUPABASE_CLI,['projects','api-keys','--project-ref',
  new URL(env.SUPABASE_URL).hostname.split('.')[0],'--reveal','--output','json'],
  {cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:45000}));
 const adminKey=keys.find(k=>k.name==='service_role')?.api_key;
 if(!adminKey)throw Error('Temporary user administration unavailable');
 admin=createClient(env.SUPABASE_URL,adminKey,{auth:{persistSession:false,autoRefreshToken:false}});
 for(let i=0;i<2;i++){
  const email='coach-system-'+randomUUID()+'@example.com',password=randomBytes(24).toString('hex');
  const created=await admin.auth.admin.createUser({email,password,email_confirm:true,user_metadata:{full_name:'Avaliacao temporaria'}});
  if(created.error)throw Error('Temporary user creation unavailable');
  testUsers.push(created.data.user.id);report.temporary_users_created++;
  const login=await publicClient().auth.signInWithPassword({email,password});
  if(login.error)throw Error('Temporary user login unavailable');users.push({id:created.data.user.id,session:login.data.session});
 }
 console.log('temporary_users_ready');save();
 const web=process.env.EVOLV_EVALUATION_WEB||path.join(root,'ai/artifacts/mobile_coach/1.0.1/web');
 staticServer=http.createServer((req,res)=>{
  const raw=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  let file=path.resolve(web,'.'+raw);
  if(!file.startsWith(path.resolve(web)+path.sep)){res.writeHead(404).end();return;}
  if(!fs.existsSync(file))file=path.resolve(web,'.'+raw+'.html');
  if(!fs.existsSync(file)&&/^\/adjustments\/[^/]+$/.test(raw))file=path.join(web,'adjustments/[adjustmentId].html');
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(web,'index.html');
  const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.png':'image/png','.jpg':'image/jpeg','.ttf':'font/ttf'};
  res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);
 });
 staticServer.listen(0,'127.0.0.1');await once(staticServer,'listening');
 const origin='http://127.0.0.1:'+staticServer.address().port;
 const reserve=http.createServer();reserve.listen(0,'127.0.0.1');await once(reserve,'listening');
 const aiPort=reserve.address().port;await new Promise(r=>reserve.close(r));aiBase='http://127.0.0.1:'+aiPort;
 serviceKey=randomBytes(32).toString('hex');
 const backend=spawn(process.execPath,['dist/main.js'],{cwd:path.join(root,'backend'),windowsHide:true,
  env:{...process.env,PORT:'3199',COACH_AI_ENABLED:'true',COACH_AI_URL:aiBase,
   COACH_AI_SERVICE_KEY:serviceKey,SWAGGER_ENABLED:'false',CORS_ORIGINS:origin},stdio:['ignore','ignore','pipe']});
 backend.stderr.on('data',d=>{backendErrors.push(String(d));if(backendErrors.length>20)backendErrors.shift();});children.push(backend);
 const launch=performance.now();
 const python=spawn(process.env.EVOLV_TEST_PYTHON,[path.join(root,'ai/scripts/serve_coach_evaluation.py'),
  '--port',String(aiPort),'--metrics',path.join(out,'resources.json'),'--backend-pid',String(backend.pid)],
  {cwd:root,windowsHide:true,env:{...process.env,EVOLV_AI_SERVICE_KEY:serviceKey,EVOLV_AI_VARIANT:'original',
   EVOLV_AI_MODE:'generate',HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1'},stdio:['ignore','ignore','pipe']});
 python.stderr.on('data',d=>{backendErrors.push(String(d));if(backendErrors.length>20)backendErrors.shift();});children.push(python);
 await until(async()=>{
  const response=await fetch(aiBase+'/health/ready',{headers:{Authorization:'Bearer '+serviceKey},signal:AbortSignal.timeout(1500)});
  if(!response.ok)return false;
  report.ai_runtime=await response.json();
  return true;
 },240);
 report.cold_start_seconds=(performance.now()-launch)/1000;
 await until(async()=> (await request('/health/ready')).status===200,30);
 console.log('real_services_ready');save();
 await request('/profiles/me');
 const profile=await request('/profiles/me',{full_name:'Avaliacao temporaria',onboarding_status:'skipped',training_level:'beginner',
  available_training_days:['tuesday']},undefined,'PATCH');
 check('temporary_profile_ready',profile.status===200);
 const plan=await request('/planner/plans/generate',{name:'Plano temporario de avaliacao',goal:'hypertrophy',level:'beginner',
  available_days:['tuesday'],session_minutes:45,desired_weekly_frequency:1,activate:true});
 report.plan_generation_status=plan.status;
 if(plan.status===201)report.test_plan_id=plan.body.id;
 check('real_planner_generates_temporary_plan',Boolean(report.test_plan_id));
 check('unauthenticated_coach_denied',(await request('/coach/sessions',{},null)).status===401);
 check('client_cannot_choose_owner',(await request('/coach/sessions',{user_id:testUsers[1]})).status===400);
 const internal=await fetch(aiBase+'/v1/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
 check('internal_api_requires_key',internal.status===401||internal.status===403);
 const raw=await fetch(aiBase+'/v1/sessions',{method:'POST',headers:{Authorization:'Bearer '+serviceKey,'X-Evolv-User-ID':testUsers[0],
  'Content-Type':'application/json'},body:'{}'});const rawSession=await raw.json();
 if(raw.ok){const forbidden=await fetch(aiBase+'/v1/sessions/'+rawSession.session_id,{method:'DELETE',headers:{
  Authorization:'Bearer '+serviceKey,'X-Evolv-User-ID':testUsers[1]}});
  check('internal_cross_user_denied',forbidden.status===404);
  await fetch(aiBase+'/v1/sessions/'+rawSession.session_id,{method:'DELETE',headers:{Authorization:'Bearer '+serviceKey,'X-Evolv-User-ID':testUsers[0]}});}
 for(const test of cases){
  let sid;
  try{
   sid=await createConversation();
   const response=await message(sid,test.text);
   report.cases.push(diagnostic(test,response));save();
   console.log(JSON.stringify({case:test.id,status:response.status,route:response.body?.result?.analysis?.route,
    generated:Boolean(response.body?.result?.generation),seconds:Number(response.seconds.toFixed(2))}));
   if(test.category==='privacy')check(test.id+'_persistence_truth',response.body?.result?.privacy?.history==='supabase_user_scoped'&&
    response.body?.result?.answer.includes('salvas na sua conta'));
   if(test.category==='action'){
    const proposal=response.body?.result?.actions?.find(a=>a.status==='pending_user_confirmation');
    if(proposal&&proposal.payload.kind===test.expected_kind)await exerciseAction(sid,proposal,test);
   }
   if(test.id==='education-01'){
    const replay=await message(sid,test.text,undefined,response.request_id);
    check('durable_same_request_deduplicated',replay.status===201&&JSON.stringify(replay.body)===JSON.stringify(response.body));
    const conflict=await message(sid,'Conteudo diferente',undefined,response.request_id);
    check('same_id_different_content_denied',conflict.status===409);
    const foreign=await request('/coach/sessions/'+sid+'/messages',undefined,users[1].session.access_token);
    check('remote_history_cross_user_denied',foreign.status===404);
    const history=await request('/coach/sessions/'+sid+'/messages');
    check('remote_message_pair_persisted',history.body?.length===2);
    const rls=await publicClient(users[1].session.access_token).from('coach_messages').select('id').eq('conversation_id',sid);
    check('direct_supabase_rls_hides_other_user_messages',!rls.error&&rls.data.length===0);
   }
   if(test.id==='privacy-02'){
    const history=await request('/coach/sessions/'+sid+'/messages');
    check('asking_deletion_does_not_delete',history.body?.length===2);
   }
  }catch(error){report.cases.push({...test,failure_type:error.constructor.name});save();console.log('case_failed:'+test.id);}
  finally{await removeConversation(sid).catch(()=>undefined);}
 }
 for(const test of dialogues){let sid;try{
  sid=await createConversation();const turns=[];
  for(const text of test.turns){const r=await message(sid,text);turns.push(diagnostic({text},r));}
  report.dialogues.push({...test,results:turns});save();console.log('dialogue_done:'+test.id);
 }finally{await removeConversation(sid).catch(()=>undefined);}}
 // Domain mutations are also tested directly when NLU abstains. Reported separately.
 const before=await targetState('set_day_activity');
 const manual=await request('/planner/adjustments/preview',{kind:'set_day_activity',source:'manual',
  reason:'Teste temporario explicito',activity_date:'2026-11-07',activity_type:'rest'});
 const aid=manual.body?.id;
 check('direct_planner_preview_created',manual.status===201&&Boolean(aid));
 if(aid){
  check('direct_preview_does_not_mutate',JSON.stringify(before)===JSON.stringify(await targetState('set_day_activity')));
  const applied=await request('/planner/adjustments/'+aid+'/apply',{});
  check('direct_real_planner_apply',applied.status===201&&JSON.stringify(before)!==JSON.stringify(await targetState('set_day_activity')));
  const reverted=await request('/planner/adjustments/'+aid+'/revert',{});
  check('direct_real_planner_revert',reverted.status===201&&JSON.stringify(before)===JSON.stringify(await targetState('set_day_activity')));
  report.actions.push({origin:'direct_planner_not_nlu',kind:'set_day_activity',apply_http:applied.status,revert_http:reverted.status});
 }
 const require=createRequire(import.meta.url);const {chromium}=require('playwright');
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const desktop=suite.phase==='7.07.11';
 const viewport=desktop?{width:1366,height:900}:{width:430,height:932};
 const context=await browser.newContext({viewport,colorScheme:'dark'});
 const key='sb-'+new URL(env.SUPABASE_URL).hostname.split('.')[0]+'-auth-token';
 await context.addInitScript(({key,session})=>{localStorage.setItem(key,JSON.stringify(session));localStorage.setItem('@evolv/theme-preference','dark');},
  {key,session:users[0].session});
 const page=await context.newPage(),errors=[],observed=[];
 page.on('pageerror',e=>errors.push({name:e.name,message:e.message.slice(0,500),stack:e.stack?.split('\n').slice(0,3)}));
 page.on('response',r=>{if(r.url().startsWith(base+'/api/coach/'))observed.push({path:new URL(r.url()).pathname,status:r.status()});});
 await page.goto(origin+'/coach');
 const input=page.getByLabel('Mensagem para o Coach',{exact:true});await input.waitFor({timeout:45000});
 await input.fill('Minhas conversas entram automaticamente no treinamento?');
 await page.getByRole('button',{name:'Enviar mensagem',exact:true}).click();
 await page.getByText(/No aplicativo, suas conversas são salvas na sua conta/).waitFor({timeout:230000});
 check('mobile_real_message_reaches_real_services',observed.some(r=>r.path.endsWith('/messages')&&r.status===201));
 await page.screenshot({path:path.join(out,desktop?'coach-desktop.png':'coach-real-mobile.png')});
 await page.getByRole('button',{name:'Histórico de conversas',exact:true}).click();
 await page.getByRole('button',{name:'Abrir Nova conversa',exact:true}).click();
 await page.getByText('Suas conversas',{exact:true}).waitFor({state:'hidden'});
 await page.getByText(/No aplicativo, suas conversas são salvas na sua conta/).waitFor();
 check('mobile_real_history_reopened',observed.some(r=>r.path.endsWith('/messages')&&r.status===200));
 if(desktop){
  await page.getByRole('button',{name:'Nova conversa',exact:true}).click();
  const hydration=subset?.length===1&&cases[0]?.id==='education-11';
  await input.fill(hydration?cases[0].text:'O que comer antes de treinar de manhã?');
  await page.getByRole('button',{name:'Enviar mensagem',exact:true}).click();
  await page.getByText('Fontes citadas',{exact:true}).waitFor({timeout:45000});
  check('desktop_grounded_reply_displays_a_source',await page.getByRole('link').count()>0);
  if(hydration){
   const response=await page.getByText(/Necessidade de liquido varia com clima/).count();
   const source=await page.getByRole('link',{name:'Nutrition and Athletic Performance',exact:true}).count();
   check('desktop_hydration_reply_and_source',response===1&&source===1);
  }
  await page.screenshot({path:path.join(out,'coach-desktop-grounded.png')});
 }
 const initialDays=await targetState('move_workout_day');
 const day=initialDays?.find(d=>d[1]==='tuesday');
 if(day){
  const move=await request('/planner/adjustments/preview',{kind:'move_workout_day',source:'manual',
   reason:'Confirmacao visual em conta temporaria',workout_plan_id:report.test_plan_id,
   workout_day_id:day[0],target_weekday:'thursday'});
  check('mobile_action_preview_created',move.status===201);
  if(move.status===201){
   await page.goto(origin+'/adjustments/'+move.body.id);
   await page.getByRole('button',{name:'Confirmar',exact:true}).waitFor({timeout:45000});
   check('direct_link_waits_for_auth_without_stale_error',await page.getByText('Entre na sua conta primeiro.',{exact:true}).count()===0);
   check('mobile_preview_has_no_automatic_write',JSON.stringify(initialDays)===JSON.stringify(await targetState('move_workout_day')));
   await page.screenshot({path:path.join(out,desktop?'planner-desktop-preview.png':'planner-real-mobile-preview.png')});
   await page.getByRole('button',{name:'Confirmar',exact:true}).click();
   await page.getByRole('button',{name:'Desfazer alteração',exact:true}).waitFor({timeout:45000});
   check('mobile_click_applies_real_plan',JSON.stringify(initialDays)!==JSON.stringify(await targetState('move_workout_day')));
   await page.getByRole('button',{name:'Desfazer alteração',exact:true}).click();
   await page.getByRole('button',{name:'Desfazer alteração',exact:true}).waitFor({state:'hidden',timeout:45000});
   check('mobile_click_restores_real_plan',JSON.stringify(initialDays)===JSON.stringify(await targetState('move_workout_day')));
   report.actions.push({origin:'real_mobile_manual_planner_not_nlu',kind:'move_workout_day',confirmed_in_browser:true});
  }
 }
 check('mobile_no_javascript_errors',errors.length===0);
 report.browser={version:browser.version(),viewport,network_mocked:false,auth_mocked:false,requests:observed,page_error_types:errors};
 report.status='evaluation_completed';
}catch(error){
 report.status='evaluation_failed';report.failure_type=error.constructor.name;
 // Only fixed diagnostics, never exception strings that could contain secrets.
 report.failure_hint=String(error.message).slice(0,180).replace(/Bearer\s+\S+/gi,'[redacted]');
 console.log(JSON.stringify({status:report.status,failure_type:report.failure_type}));
}finally{
 if(browser)await browser.close().catch(()=>undefined);
 if(staticServer)await new Promise(r=>staticServer.close(r));
 for(const child of children.reverse())if(child.exitCode===null){child.kill();await Promise.race([once(child,'exit'),new Promise(r=>setTimeout(r,3000))]);}
 for(const id of testUsers)if(admin){const deleted=await admin.auth.admin.deleteUser(id);if(!deleted.error)report.temporary_users_deleted++;}
 report.cleanup_complete=report.temporary_users_created===report.temporary_users_deleted;
 report.completed_at=new Date().toISOString();
 const latencies=report.cases.filter(r=>r.http_status===201).map(r=>r.total_seconds).sort((a,b)=>a-b);
 const percentile=p=>latencies[Math.max(0,Math.ceil(latencies.length*p)-1)]??null;
 report.summary={completed_cases:report.cases.filter(r=>r.http_status===201).length,total_cases:cases.length,
  generated:report.cases.filter(r=>r.result?.generation).length,
  truncated:report.cases.filter(r=>r.result?.generation?.stopped_at_eos===false).length,
  proposed_actions:report.cases.filter(r=>r.result?.actions?.some(a=>a.status==='pending_user_confirmation')).length,
  real_coach_action_cycles:report.actions.filter(r=>r.origin==='real_coach'&&r.original_state_restored).length,
  checks_passed:report.checks.filter(c=>c.passed).length,checks_failed:report.checks.filter(c=>!c.passed).length,
  warm_request_p50_seconds:percentile(.5),warm_request_p95_seconds:percentile(.95)};
 // Logs are deliberately not persisted; full responses contain synthetic test content only.
 report.service_error_observed=backendErrors.some(s=>/Traceback|ERROR/.test(s));
 save();console.log(JSON.stringify({status:report.status,...report.summary,cleanup_complete:report.cleanup_complete}));
}
if(report.status!=='evaluation_completed'||!report.cleanup_complete)process.exitCode=1;
