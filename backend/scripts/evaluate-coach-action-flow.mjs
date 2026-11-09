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
const version=process.env.EVOLV_ACTION_FLOW_VERSION||'1.0.0';
if(!/^\d+\.\d+\.\d+$/.test(version))throw Error('Invalid evaluation version');
const out=path.join(root,'ai/artifacts/coach_action_flow',version);
if(fs.existsSync(path.join(out,'results.json'))||fs.existsSync(path.join(out,'inputs.json')))
 throw Error('Evaluation exists; choose a new version');
fs.mkdirSync(out,{recursive:true});
const env=parseEnv(fs.readFileSync('.env','utf8'));
const report={phase:'7.07.5',version,started_at:new Date().toISOString(),status:'running',
 scope:'Development suite; real NestJS, FastAPI, recognition 1.9 opt-in, real entities, RAG, Supabase and Planner; LM generation disabled',
 nlp_version:'1.9.0',lm_mode:'analyze',independent_quality_benchmark:false,
 credentials_recorded:false,existing_user_data_modified:false,native_iphone_tested:false,
 checks:[],cases:[],dialogues:[],actions:[],temporary_users_created:0,temporary_users_deleted:0};

const inputFiles=['backend/scripts/evaluate-coach-action-flow.mjs','ai/scripts/serve_coach_evaluation.py','ai/src/evolv_api/app.py',
 'ai/src/evolv_nlp/recognition_pipeline.py','ai/src/evolv_rag/coach.py','ai/src/evolv_rag/safety.py',
 'ai/artifacts/baseline/1.9.0/manifest.json','ai/artifacts/baseline/1.8.0/selection_frozen.json',
 'backend/src/coach/coach.service.ts','backend/src/coach/coach-context.service.ts',
 'backend/src/planner/planner-adjustments.service.ts','mobile/src/components/coach-connected-screen.tsx',
 'mobile/src/app/adjustments/[adjustmentId].tsx'];
fs.writeFileSync(path.join(out,'inputs.json'),JSON.stringify({sha256:Object.fromEntries(inputFiles.map(f=>[
 f,createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]))},null,2));
function protectedHashes(){
 const files=[];
 function walk(dir){for(const entry of fs.readdirSync(path.join(root,dir),{withFileTypes:true})){
  const name=path.join(dir,entry.name);if(entry.isDirectory())walk(name);else files.push(name);
 }}
 for(const dir of ['ai/data/releases/1.8.0','ai/data/releases/1.9.0','ai/artifacts/baseline/1.8.0','ai/artifacts/baseline/1.9.0'])walk(dir);
 return Object.fromEntries(files.sort().map(f=>[f,createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]));
}
const protectedBefore=protectedHashes();
fs.writeFileSync(path.join(out,'protected_before.json'),JSON.stringify(protectedBefore,null,2));
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
 if(kind==='replace_exercise'){
  const plan=await request('/planner/plans/'+report.test_plan_id);
  return plan.body.workout_days.flatMap(d=>d.workout_day_exercises.map(e=>({id:e.id,exercise_id:e.exercise_id,
   sets:e.sets,reps:e.reps,rest_seconds:e.rest_seconds,position:e.position}))).sort((a,b)=>a.id.localeCompare(b.id));
 }
 if(kind==='replace_meal_item'){
  const plan=await request('/planner/nutrition-plans/'+report.test_diet_id);
  return plan.body.meals.flatMap(m=>m.meal_items.map(e=>Object.fromEntries(Object.entries(e)
   .filter(([k])=>!['created_at','updated_at','foods'].includes(k))))).sort((a,b)=>a.id.localeCompare(b.id));
 }
 const r=await publicClient(users[0].session.access_token).from('daily_activity_overrides')
  .select('activity_date,activity_type,nutrition_day_type').eq('user_id',testUsers[0]).order('activity_date');
 if(r.error)throw Error('Cannot inspect temporary activity state');return r.data;
}
async function exerciseAction(sid,proposal,test){
 const kind=proposal.payload.kind,before=await targetState(kind);
 const confirmed=await message(sid,'confirmo',proposal.id);
 const p=confirmed.body?.planner_previews?.[0];
 const record={origin:'real_coach',kind,preview_http:confirmed.status,preview_created:Boolean(p)};
 report.actions.push(record);save();
 if(!p)return;
 record.preview_id=p.id;
 check('preview_has_expected_kind_'+kind,p.adjustment_kind===kind);
 record.preview={kind:p.adjustment_kind,before:p.before_snapshot,after:p.after_snapshot};
 check('preview_leaves_plan_unchanged_'+kind,JSON.stringify(before)===JSON.stringify(await targetState(kind)));
 const denied=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:false});
 check('false_confirmation_denied_'+kind,denied.status===400);
 const foreign=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true},users[1].session.access_token);
 check('other_user_cannot_apply_'+kind,foreign.status===404);
 const applied=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true});
 const after=await targetState(kind);
 record.apply_http=applied.status;record.apply_error=applied.status===201?null:applied.body;record.state_changed=JSON.stringify(before)!==JSON.stringify(after);
 record.before=before;record.after=after;
 check('real_apply_changes_state_'+kind,applied.status===201&&record.state_changed);
 if(kind==='move_workout_day')check('applied_requested_weekday_'+test.id,after.find(d=>d[0]===proposal.payload.workout_day_id)?.[1]===test.expected.target_weekday);
 if(kind==='set_day_activity')check('applied_requested_activity_'+test.id,after.some(d=>d.activity_date===test.expected.activity_date&&d.activity_type===test.expected.activity_type));
 if(kind==='replace_exercise')check('applied_requested_exercise_'+test.id,after.find(e=>e.id===test.expected.workout_day_exercise_id)?.exercise_id===test.expected.replacement_exercise_id);
 if(kind==='replace_meal_item')check('applied_requested_food_'+test.id,after.find(e=>e.id===test.expected.meal_item_id)?.food_id===test.expected.replacement_food_id);
 const duplicate=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/apply',{confirmed:true});
 record.second_apply_http=duplicate.status;
 check('second_apply_denied_without_mutation_'+kind,[400,409].includes(duplicate.status)&&JSON.stringify(after)===JSON.stringify(await targetState(kind)));
 const reverted=await request('/coach/sessions/'+sid+'/adjustments/'+p.id+'/revert',{confirmed:true});
 record.revert_http=reverted.status;record.revert_error=reverted.status===201?null:reverted.body;record.original_state_restored=JSON.stringify(before)===JSON.stringify(await targetState(kind));
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
 const web=process.env.EVOLV_EVALUATION_WEB||path.join(root,'ai/artifacts/system_evaluation/1.0.2/web');
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
   EVOLV_AI_MODE:'analyze',EVOLV_AI_NLP_VERSION:'1.9.0',HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1'},stdio:['ignore','ignore','pipe']});
 python.stderr.on('data',d=>{backendErrors.push(String(d));if(backendErrors.length>20)backendErrors.shift();});children.push(python);
 await until(async()=> (await fetch(aiBase+'/health/ready',{headers:{Authorization:'Bearer '+serviceKey},signal:AbortSignal.timeout(1500)})).ok,240);
 const runtime=await (await fetch(aiBase+'/health/ready',{headers:{Authorization:'Bearer '+serviceKey}})).json();
 check('explicit_nlp_runtime_selected',runtime.nlp_version==='1.9.0'&&runtime.mode==='analyze');
 report.cold_start_seconds=(performance.now()-launch)/1000;
 await until(async()=> (await request('/health/ready')).status===200,30);
 console.log('real_services_ready');
 await request('/profiles/me');
 const profile=await request('/profiles/me',{full_name:'Avaliacao temporaria',onboarding_status:'skipped',training_level:'beginner',
  available_training_days:['tuesday'],birth_date:'1996-01-01',height_cm:175,current_weight_kg:75},undefined,'PATCH');
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
 const diet=await request('/planner/nutrition-plans/generate',{name:'Dieta temporaria de avaliacao',
  phase:'maintenance',estimated_maintenance_calories:2400,meals_per_day:3,rotate_menus:false,activate:true});
 check('real_diet_generated',diet.status===201, diet.status===201?undefined:diet.body);
 if(diet.status===201)report.test_diet_id=diet.body.id;
 const catalog=await publicClient(users[0].session.access_token).from('exercises')
  .select('id,name,muscle_group,movement_pattern,training_kind').order('name');
 if(catalog.error)throw Error('Temporary plan catalog unavailable');
 const items=plan.body.workout_days.flatMap(d=>d.workout_day_exercises);
 const pair=items.flatMap(item=>catalog.data.filter(e=>e.id!==item.exercise_id&&
  e.training_kind===item.exercises.training_kind&&
  (e.muscle_group===item.exercises.muscle_group||e.movement_pattern===item.exercises.movement_pattern)&&
  !items.some(i=>i.exercise_id===e.id)).map(e=>({old:item.exercises.name,replacement:e.name,
   item_id:item.id,replacement_id:e.id})))[0];
 const meals=diet.status===201?diet.body.meals.flatMap(m=>m.meal_items):[];
 const food=meals.find(item=>meals.filter(i=>i.food_id===item.food_id).length===1&&item.substitutions?.length);
 const tests=[
  {id:'move-explicit',text:'Mova meu treino de 03/11/2026 para 05/11/2026.',kind:'move_workout_day',expected:{workout_plan_id:report.test_plan_id,workout_day_id:plan.body.workout_days[0].id,target_weekday:'thursday'}},
  {id:'move-weekdays',text:'Troque o treino de terça para quinta nesta semana.',kind:'move_workout_day',expected:{workout_plan_id:report.test_plan_id,workout_day_id:plan.body.workout_days[0].id,target_weekday:'thursday'}},
  {id:'rest',text:'Defina 05/11/2026 como dia de descanso.',kind:'set_day_activity',expected:{activity_date:'2026-11-05',activity_type:'rest'}},
  {id:'cardio',text:'Coloque cardio no dia 06/11/2026.',kind:'set_day_activity',expected:{activity_date:'2026-11-06',activity_type:'cardio'}},
  ...(pair?[{id:'exercise',text:`Troque ${pair.old} por ${pair.replacement}.`,kind:'replace_exercise',expected:{
   workout_plan_id:report.test_plan_id,workout_day_exercise_id:pair.item_id,replacement_exercise_id:pair.replacement_id}}]:[]),
  ...(food?[{id:'food',text:`Troque ${food.name} por ${food.substitutions[0].name}.`,kind:'replace_meal_item',expected:{
   diet_plan_id:report.test_diet_id,meal_item_id:food.id,replacement_food_id:food.substitutions[0].food_id}}]:[]),
  {id:'missing-destination',text:'Mova meu treino de terça.',must_abstain:true},
  {id:'missing-replacement',text:'Troque o supino reto.',must_abstain:true},
  {id:'missing-date',text:'Quero definir descanso.',must_abstain:true},
  {id:'negated',text:'Não mova meu treino de terça para quinta.',must_abstain:true},
  {id:'hypothetical',text:'Talvez eu troque meu treino de terça para quinta.',must_abstain:true},
  {id:'unsafe-pain',text:'Estou com dor no peito e falta de ar.',must_abstain:true},
 ];
 report.planned_cases=tests;report.catalog_pair_selection='First compatible unused catalog exercise; first unique meal item with approved substitution; chosen without inspecting model predictions';save();
 check('all_four_action_kinds_have_test_input',Boolean(pair&&food));
 for(const test of tests){let sid;try{
  sid=await createConversation();
  const before=await targetState(test.kind||'move_workout_day');
  const response=await message(sid,test.text);
  const result=response.body?.result;
  const proposal=result?.actions?.find(a=>a.status==='pending_user_confirmation');
  const record={...test,http_status:response.status,seconds:response.seconds,result,
   outcome:proposal?'proposal':result?.clarification?'clarification':'no_proposal'};
  report.cases.push(record);save();
  check(test.id+'_http_ok',response.status===201);
  check(test.id+'_no_automatic_mutation',JSON.stringify(before)===JSON.stringify(await targetState(test.kind||'move_workout_day')));
  if(test.must_abstain)check(test.id+'_blocked',!proposal);
  if(proposal){
   check(test.id+'_correct_kind',proposal.payload.kind===test.kind&&!test.must_abstain);
   const expected=Object.entries(test.expected??{}).every(([key,value])=>proposal.payload[key]===value);
   check(test.id+'_exact_requested_payload',expected);
   if(proposal.payload.kind===test.kind&&!test.must_abstain&&expected)await exerciseAction(sid,proposal,test);
  }
  const history=await request('/coach/sessions/'+sid+'/messages');
  check(test.id+'_history_saved',history.status===200&&history.body.length>=2);
  console.log(JSON.stringify({id:test.id,outcome:record.outcome,intent:result?.analysis?.intent?.label,
   confident:result?.analysis?.intent?.confident,clarification:result?.clarification?.reason}));
 }catch(error){report.case_failures??=[];report.case_failures.push({id:test.id,failure_type:error.constructor.name});
  check(test.id+'_completed_without_exception',false);save();}
 finally{await removeConversation(sid);}}
 // Rejection and stale snapshots are exercised using a naturally recognized request, without injected intent.
 const successful=report.cases.find(c=>c.id==='move-explicit'&&c.outcome==='proposal');
 if(successful){let sid;try{
  sid=await createConversation();const first=await message(sid,successful.text);
  const proposal=first.body?.result?.actions?.[0];assert(proposal);
  const before=await targetState('move_workout_day');
  const unrelated=await message(sid,'confirmo',randomUUID());
  check('wrong_proposal_id_no_preview',unrelated.body?.planner_previews?.length===0);
  const reject=await message(sid,'rejeito',proposal.id);
  check('proposal_rejection_no_preview',reject.body?.result?.actions?.[0]?.status==='rejected'&&reject.body.planner_previews.length===0);
  check('rejection_preserves_plan',JSON.stringify(before)===JSON.stringify(await targetState('move_workout_day')));
  const replay=await message(sid,'confirmo',proposal.id);
  check('rejected_proposal_cannot_be_confirmed',replay.body?.planner_previews?.length===0);
 }finally{await removeConversation(sid);}
 let staleSid;try{
  staleSid=await createConversation();const first=await message(staleSid,successful.text);
  const proposal=first.body?.result?.actions?.[0];assert(proposal);
  const before=await targetState('move_workout_day');
  const direct=await request('/planner/adjustments/preview',{kind:'move_workout_day',source:'manual',
   reason:'Teste de plano desatualizado',workout_plan_id:report.test_plan_id,workout_day_id:before[0][0],target_weekday:'wednesday'});
  assert.equal(direct.status,201);
  try{
   assert.equal((await request('/planner/adjustments/'+direct.body.id+'/apply',{})).status,201);
   const stale=await message(staleSid,'confirmo',proposal.id);
   check('changed_plan_invalidates_old_proposal',stale.body?.planner_previews?.length===0);
  }finally{
   const reverted=await request('/planner/adjustments/'+direct.body.id+'/revert',{});
   check('stale_test_restores_plan',reverted.status===201&&JSON.stringify(before)===JSON.stringify(await targetState('move_workout_day')));
  }
 }finally{await removeConversation(staleSid);}
 }
 // Same real Coach flow through the current Mobile web UI; never a manual preview or network mock.
 if(successful){
  const require=createRequire(import.meta.url);const {chromium}=require('playwright');
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const context=await browser.newContext({viewport:{width:430,height:932},colorScheme:'dark'});
  const key='sb-'+new URL(env.SUPABASE_URL).hostname.split('.')[0]+'-auth-token';
  await context.addInitScript(({key,session})=>{localStorage.setItem(key,JSON.stringify(session));
   localStorage.setItem('@evolv/theme-preference','dark');},{key,session:users[0].session});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.name));
  await page.goto(origin+'/coach');
  const input=page.getByLabel('Mensagem para o Coach',{exact:true});await input.waitFor({timeout:45000});
  const before=await targetState('move_workout_day');
  await input.fill(successful.text);await page.getByRole('button',{name:'Enviar mensagem',exact:true}).click();
  await page.getByRole('button',{name:'Ver prévia',exact:true}).last().waitFor({timeout:60000});
  await page.screenshot({path:path.join(out,'01-coach-proposta.png')});
  await page.getByRole('button',{name:'Ver prévia',exact:true}).last().click();
  await page.getByRole('button',{name:'Revisar ajuste',exact:true}).last().waitFor({timeout:60000});
  check('browser_proposal_preview_does_not_mutate',JSON.stringify(before)===JSON.stringify(await targetState('move_workout_day')));
  await page.getByRole('button',{name:'Revisar ajuste',exact:true}).last().click();
  await page.getByRole('button',{name:'Confirmar alteração',exact:true}).waitFor({timeout:45000});
  await page.screenshot({path:path.join(out,'02-coach-previa.png')});
  await page.getByRole('button',{name:'Confirmar alteração',exact:true}).click();
  await page.getByRole('button',{name:'Desfazer alteração',exact:true}).waitFor({timeout:45000});
  const appliedDays=await targetState('move_workout_day');
  check('browser_confirmation_changes_real_plan',JSON.stringify(before)!==JSON.stringify(appliedDays)&&appliedDays.find(d=>d[0]===before[0][0])?.[1]==='thursday');
  await page.screenshot({path:path.join(out,'03-coach-aplicado.png')});
  await page.getByRole('button',{name:'Desfazer alteração',exact:true}).click();
  await page.getByRole('button',{name:'Desfazer alteração',exact:true}).waitFor({state:'hidden',timeout:45000});
  check('browser_undo_restores_real_plan',JSON.stringify(before)===JSON.stringify(await targetState('move_workout_day')));
  await page.screenshot({path:path.join(out,'04-coach-desfeito.png')});
  check('browser_no_javascript_errors',errors.length===0);
  report.browser={network_mocked:false,real_nlp:true,real_authenticated_session:true,error_types:errors};
 }
 report.status='evaluation_completed';
}catch(error){
 report.status='evaluation_failed';report.failure_type=error.constructor.name;
 report.failure_hint=String(error.message).slice(0,200).replace(/Bearer\s+\S+/gi,'[redacted]');
 console.log(JSON.stringify({status:report.status,failure_type:report.failure_type}));
}finally{
 if(browser)await browser.close().catch(()=>undefined);
 if(staticServer)await new Promise(r=>staticServer.close(r));
 for(const child of children.reverse())if(child.exitCode===null){child.kill();await Promise.race([once(child,'exit'),new Promise(r=>setTimeout(r,3000))]);}
 for(const id of testUsers)if(admin){const deleted=await admin.auth.admin.deleteUser(id);if(!deleted.error)report.temporary_users_deleted++;}
 report.cleanup_complete=report.temporary_users_created===report.temporary_users_deleted;
 check('frozen_datasets_models_and_thresholds_unchanged',JSON.stringify(protectedBefore)===JSON.stringify(protectedHashes()));
 report.completed_at=new Date().toISOString();
 report.summary={completed_cases:report.cases.filter(r=>r.http_status===201).length,
  requested_action_cases:report.cases.filter(r=>r.kind).length,
  proposed_actions:report.cases.filter(r=>r.outcome==='proposal').length,
  real_coach_action_cycles:report.actions.filter(r=>r.origin==='real_coach'&&r.original_state_restored).length,
  checks_passed:report.checks.filter(c=>c.passed).length,checks_failed:report.checks.filter(c=>!c.passed).length};
 report.service_error_observed=backendErrors.some(s=>/Traceback|ERROR/.test(s));
 save();console.log(JSON.stringify({status:report.status,...report.summary,cleanup_complete:report.cleanup_complete}));
}
if(report.status!=='evaluation_completed'||!report.cleanup_complete||report.summary.checks_failed)process.exitCode=1;
