// Temporary test users only; credentials remain in memory and users are removed in finally.
import 'reflect-metadata';
import fs from 'node:fs';
import path from 'node:path';
import { parseEnv } from 'node:util';
import { randomUUID,randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createClient } from '@supabase/supabase-js';
import { CoachHistoryService } from '../dist/coach/coach-history.service.js';
import assert from 'node:assert/strict';
const root=path.resolve('..');
const output=path.join(root,'ai/artifacts/coach_history/remote-verification.json');
if(fs.existsSync(output))throw Error('Remote verification already recorded');
const env=parseEnv(fs.readFileSync('.env','utf8'));
const url=env.SUPABASE_URL,key=env.SUPABASE_ANON_KEY;
const ids=[];let admin;const checks=[];
const report={phase:'7.06.3',credentials_recorded:false,checks,temporary_users_created:0,
              temporary_users_deleted:0,existing_user_data_modified:false};
function client(token){return createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false},
  global:token?{headers:{Authorization:'Bearer '+token}}:undefined});}
try{
  if(!process.env.EVOLV_SUPABASE_CLI)throw Error('Missing local CLI path');
  const raw=execFileSync(process.env.EVOLV_SUPABASE_CLI,['projects','api-keys','--project-ref',
    new URL(url).hostname.split('.')[0],'--reveal','--output','json'],
    {cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:45000});
  const keys=JSON.parse(raw);
  const serviceKey=keys.find(k=>k.name==='service_role')?.api_key;
  if(!serviceKey)throw Error('Admin credential unavailable');
  admin=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
  const users=[];
  for(let i=0;i<2;i++){
    const email='coach-history-check-'+randomUUID()+'@example.com',password=randomBytes(24).toString('hex');
    const created=await admin.auth.admin.createUser({email,password,email_confirm:true,user_metadata:{full_name:'Teste temporario de historico'}});
    if(created.error)throw Error('Temporary user creation unavailable');
    const id=created.data.user.id;ids.push(id);report.temporary_users_created++;
    const login=await client().auth.signInWithPassword({email,password});
    if(login.error||!login.data.session)throw Error('Temporary login unavailable');
    users.push({id,token:login.data.session.access_token});
  }
  const [a,b]=users;
  const repo=new CoachHistoryService({forUser:token=>client(token)});
  const c=await repo.create(a.id,a.token,{});
  checks.push('create_conversation_and_config');
  const request=randomUUID(),response={session_id:c.id,result:{answer:'Resposta sintetica de teste.',actions:[]}};
  await repo.commit(a.id,a.token,c.id,request,'hash1','Duvida sintetica.',response);
  await repo.commit(a.id,a.token,c.id,request,'hash1','Duvida sintetica.',response);
  assert.equal((await repo.messages(a.id,a.token,c.id)).length,2);checks.push('atomic_pair_and_dedup');
  assert.equal((await repo.list(b.id,b.token)).some(row=>row.id===c.id),false);checks.push('other_user_list_hidden');
  await assert.rejects(repo.get(b.id,b.token,c.id));checks.push('other_user_read_denied');
  const forged=await client(b.token).from('coach_messages').insert({
    conversation_id:c.id,user_id:b.id,role:'user',content:'fixture',metadata:{}});
  assert.ok(forged.error);checks.push('cross_owner_reference_denied');
  const another=new CoachHistoryService({forUser:token=>client(token)});
  assert.equal((await another.recent(a.id,a.token,c.id)).length,2);checks.push('history_survives_repository_restart');
  assert.equal((await repo.rename(a.id,a.token,c.id,'Teste temporario'))?.title,'Teste temporario');checks.push('rename');
  await repo.remove(a.id,a.token,c.id);
  const remaining=await client(a.token).from('coach_messages').select('id').eq('conversation_id',c.id);
  assert.equal(remaining.data?.length,0);checks.push('delete_cascades_messages');
  report.status='verified';
}catch(error){
  report.status='blocked_or_failed';report.failure_type=error?.constructor?.name??'Error';
}finally{
  if(admin)for(const id of ids){
    const removed=await admin.auth.admin.deleteUser(id);
    if(!removed.error)report.temporary_users_deleted++;
  }
  report.cleanup_complete=report.temporary_users_created===report.temporary_users_deleted;
  fs.mkdirSync(path.dirname(output),{recursive:true});
  fs.writeFileSync(output,JSON.stringify(report,null,2));
}
console.log(JSON.stringify(report));
if(report.status!=='verified'||!report.cleanup_complete)process.exitCode=1;
