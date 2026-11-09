// Browser contract fixture; no real accounts, inference or Planner mutations.
const {chromium}=require("playwright");
const fs=require("node:fs"),path=require("node:path"),http=require("node:http"),assert=require("node:assert/strict");
const root=path.resolve(__dirname,"../.."),out=path.join(root,"ai/artifacts/mobile_coach/1.0.1");
const web=path.join(out,"web");
const env=fs.readFileSync(path.join(root,"mobile/.env.local"),"utf8");
const url=env.match(/^EXPO_PUBLIC_SUPABASE_URL=(.*)$/m)[1].trim().replace(/['"]/g,"");
const key="sb-"+new URL(url).hostname.split(".")[0]+"-auth-token";
const user={id:"11111111-1111-4111-8111-111111111111",aud:"authenticated",role:"authenticated",
  email:"mobile-fixture@example.com",created_at:"2026-11-03T00:00:00Z",app_metadata:{},user_metadata:{}};
const encode=value=>Buffer.from(JSON.stringify(value)).toString("base64url");
const token=encode({alg:"HS256",typ:"JWT"})+"."+encode({sub:user.id,exp:4102444800,role:"authenticated",aud:"authenticated"})+".fixture";
const session={access_token:token,refresh_token:"fixture-refresh",expires_at:4102444800,expires_in:3600,token_type:"bearer",user};
const cid="22222222-2222-4222-8222-222222222222",pid="33333333-3333-4333-8333-333333333333",aid="44444444-4444-4444-8444-444444444444";
const conversations=new Map([["55555555-5555-4555-8555-555555555555",{id:"55555555-5555-4555-8555-555555555555",title:"Treino anterior",created_at:"2026-11-03",updated_at:"2026-11-03"}]]);
const history=new Map(),requests=[],checks=[];
let failedOnce=false,applies=0,reverts=0,deletes=0;
const preview={id:aid,status:"pending",adjustment_kind:"move_workout_day",source:"coach",reason:"Pedido",
  preview:{title:"Mover treino",summary:"Terça passa para quinta.",changes:["Treino de terça para quinta"],preserved:["Exercícios e cargas"],warnings:[]},
  reversible:true,expires_at:"2099-01-01T00:00:00Z",applied_at:null,reverted_at:null};
function check(name,ok){assert.ok(ok,name);checks.push(name);}
const server=http.createServer((req,res)=>{
  const raw=decodeURIComponent(new URL(req.url,"http://localhost").pathname);
  let file=path.join(web,raw);
  if(!path.resolve(file).startsWith(path.resolve(web)+path.sep)){res.writeHead(404).end();return;}
  if(!fs.existsSync(file))file=path.join(web,raw+".html");
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(web,"index.html");
  const mime={".html":"text/html",".js":"text/javascript",".json":"application/json",".css":"text/css",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".ttf":"font/ttf"};
  res.setHeader("Content-Type",mime[path.extname(file)]||"application/octet-stream");fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(r=>server.listen(0,"127.0.0.1",r));
  const browser=await chromium.launch({headless:true,executablePath:"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"});
  try{
    const context=await browser.newContext({viewport:{width:430,height:932},colorScheme:"dark"});
    await context.addInitScript(({key,session})=>{
      localStorage.setItem(key,JSON.stringify(session));localStorage.setItem("@evolv/theme-preference","dark");
    },{key,session});
    const page=await context.newPage(),errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    await page.route("**/*",async route=>{
      const request=route.request(),u=new URL(request.url()),method=request.method();
      if(u.hostname==="127.0.0.1"&&u.port===String(server.address().port))return route.continue();
      const json=async(body,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(body),headers:{
        "access-control-allow-origin":"*","access-control-allow-headers":"authorization,content-type","access-control-allow-methods":"GET,POST,PATCH,DELETE,OPTIONS"}});
      if(method==="OPTIONS")return json({},204);
      if(u.pathname.startsWith("/auth/v1"))return json(user);
      const p=u.pathname.replace(/^\/api/,""),body=request.postDataJSON?.()||{};
      if(p==="/profiles/me")return json({id:user.id,full_name:"Teste Mobile",onboarding_status:"completed"});
      if(p==="/coach/sessions"&&method==="GET")return json([...conversations.values()]);
      if(p==="/coach/sessions"&&method==="POST"){
        conversations.set(cid,{id:cid,title:"Nova conversa",created_at:"2026-11-03",updated_at:"2026-11-03"});
        return json({session_id:cid,conversation_id:cid},201);
      }
      if(p.match(/\/coach\/sessions\/[^/]+\/messages$/)){
        const id=p.split("/")[3];
        if(method==="GET")return json((history.get(id)||[]).slice().reverse());
        requests.push(body);
        if(body.text==="Como recuperar melhor?"&&!failedOnce){failedOnce=true;return json({message:"COACH_AI_UNAVAILABLE"},503);}
        const result={answer:"Resposta recebida do Coach.",actions:[],citations:{cited_chunk_ids:[],supplied_chunk_ids:[]}};
        let previews=[];
        if(body.text.startsWith("Mova")){
          result.answer="Proposta preparada";result.actions=[{id:pid,status:"pending_user_confirmation",expires_at:"2099-01-01",payload:{kind:"move_workout_day"}}];
        }else if(body.proposal_id){
          result.actions=[{id:pid,status:"confirmed_for_planner_preview",expires_at:"2099-01-01",payload:{kind:"move_workout_day"}}];previews=[{...preview}];
        }
        const response={session_id:id,request_id:body.request_id,result,planner_previews:previews};
        const rows=history.get(id)||[];
        if(!rows.some(r=>r.metadata?.request_id===body.request_id)){
          rows.push({id:body.request_id,role:"user",content:body.text,metadata:{request_id:body.request_id}});
          rows.push({id:body.request_id+":a",role:"assistant",content:result.answer,metadata:{request_id:body.request_id,response}});
          history.set(id,rows);
        }
        return json(response,201);
      }
      if(p==="/planner/adjustments/"+aid)return json(preview);
      if(p.includes("/adjustments/"+aid+"/apply")){applies++;preview.status="applied";preview.applied_at="2026-11-03";return json(preview);}
      if(p.includes("/adjustments/"+aid+"/revert")){reverts++;preview.reverted_at="2026-11-03";return json(preview);}
      if(p.match(/^\/coach\/sessions\/[^/]+$/)){
        const id=p.split("/")[3];
        if(method==="PATCH"){const c=conversations.get(id);c.title=body.title;return json(c);}
        if(method==="DELETE"){deletes++;conversations.delete(id);history.delete(id);return json({});}
      }
      return json(/\/(plans|entries|logs|suggestions|exercises)$/.test(p)||p.includes("/progress")?[]:null);
    });
    await page.goto("http://127.0.0.1:"+server.address().port+"/coach");
    await page.getByLabel("Mensagem para o Coach",{exact:true}).waitFor({timeout:30000});
    check("connected_screen_loaded",await page.getByText("Vamos conversar.",{exact:true}).isVisible());
    const input=page.getByLabel("Mensagem para o Coach",{exact:true});
    await input.fill("Como recuperar melhor?");await page.getByRole("button",{name:"Enviar mensagem",exact:true}).click();
    await page.getByRole("button",{name:"Tentar novamente",exact:true}).waitFor();
    await page.getByRole("button",{name:"Tentar novamente",exact:true}).click();
    await page.getByText("Resposta recebida do Coach.",{exact:true}).waitFor();
    check("retry_reuses_request_id",requests[0].request_id===requests[1].request_id);
    await input.fill("Mova meu treino de terça para quinta");await page.getByRole("button",{name:"Enviar mensagem",exact:true}).click();
    await page.getByRole("button",{name:"Ver prévia",exact:true}).click();
    check("proposal_does_not_apply",applies===0);
    await page.getByRole("button",{name:"Revisar ajuste",exact:true}).click();
    await page.getByText("O que muda",{exact:true}).waitFor();
    check("preview_does_not_apply",applies===0);
    await page.getByRole("button",{name:"Confirmar alteração",exact:true}).click();
    await page.getByText("Alteração aplicada",{exact:true}).waitFor();
    check("apply_requires_explicit_button",applies===1);
    check("background_refresh_keeps_preview",await page.getByText("Revisar alteração",{exact:true}).isVisible());
    await page.getByRole("button",{name:"Desfazer alteração",exact:true}).click();
    await page.getByText("Alteração desfeita",{exact:true}).waitFor();
    check("explicit_revert",reverts===1);
    await page.getByRole("button",{name:"Fechar",exact:true}).click();
    await page.getByRole("button",{name:"Histórico de conversas",exact:true}).click();
    await page.getByRole("button",{name:"Renomear Nova conversa",exact:true}).click();
    await page.getByLabel("Nome da conversa",{exact:true}).fill("Plano da semana");
    await page.getByRole("button",{name:"Salvar nome",exact:true}).click();
    await page.getByRole("button",{name:"Histórico de conversas",exact:true}).click();
    await page.getByRole("button",{name:"Abrir Plano da semana",exact:true}).click();
    await page.getByText("Suas conversas",{exact:true}).waitFor({state:"hidden"});
    await page.getByText("Como recuperar melhor?",{exact:true}).waitFor();
    check("history_reopens_saved_messages",true);
    check("historical_proposal_is_not_live",await page.getByRole("button",{name:"Ver prévia",exact:true}).count()===0);
    await page.screenshot({path:path.join(out,"coach-mobile.png")});
    const bounds=await input.boundingBox();
    check("mobile_composer_visible",bounds&&bounds.y>=0&&bounds.y+bounds.height<932-70);
    check("mobile_no_horizontal_overflow",await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(out,"coach-desktop.png")});
    check("desktop_no_horizontal_overflow",await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole("button",{name:"Histórico de conversas",exact:true}).click();
    await page.getByRole("button",{name:"Excluir Plano da semana",exact:true}).click();
    check("delete_not_automatic",deletes===0);
    await page.getByRole("button",{name:"Manter conversa",exact:true}).click();
    check("cancel_delete_preserves_history",conversations.has(cid));
    await page.getByRole("button",{name:"Histórico de conversas",exact:true}).click();
    await page.getByRole("button",{name:"Excluir Plano da semana",exact:true}).click();
    await page.getByRole("button",{name:"Excluir conversa",exact:true}).click();
    await page.getByText("Vamos conversar.",{exact:true}).waitFor();
    check("confirmed_delete_removes_conversation",deletes===1&&!conversations.has(cid));
    check("no_browser_runtime_errors",errors.length===0);
    fs.writeFileSync(path.join(out,"ui-verification.json"),JSON.stringify({phase:"7.06.4",checks_passed:checks.length,checks,
      browser:browser.version(),scope:"real exported Mobile web UI, network/auth/Planner fixtures; no real mutations",
      native_iphone_tested:false},null,2));
    console.log(JSON.stringify({checks_passed:checks.length,browser_errors:errors}));
  }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
