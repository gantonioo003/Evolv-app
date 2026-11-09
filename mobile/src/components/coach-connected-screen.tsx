import { useEffect,useMemo,useRef,useState,useSyncExternalStore,type ReactNode } from "react";
import { ActivityIndicator,Keyboard,KeyboardAvoidingView,Linking,Modal,Platform,ScrollView,StyleSheet,Text,TextInput,View } from "react-native";
import { History,Plus,Send,X,Pencil,Trash2 } from "lucide-react-native";
import * as Crypto from "expo-crypto";
import { TouchFeedback as Pressable } from "@/components/touch-feedback";
import { AppScreen,CinematicHero,PageHeader } from "@/components/ui";
import { colors } from "@/constants/theme";
import { useImagePreferences } from "@/context/image-preferences-context";
import { useAppTheme,type AppThemePalette } from "@/context/theme-context";
import { useAuth } from "@/context/auth-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { coachImages,pickWeeklyImage } from "@/data/image-library";
import { quickCoachPrompts } from "@/data/mock-data";
import { CoachApi } from "@/services/coach-api";
import { CoachSession,coachDisplayText } from "@/lib/coach-session";
import type { Conversation,ChatMessage } from "@/types/coach";

export default function CoachScreen(){
  const {user}=useAuth();
  return <ConnectedCoach key={user?.id??"guest"}/>;
}
function ConnectedCoach(){
  const {palette}=useAppTheme(),images=useImagePreferences(),{user,session}=useAuth(),data=useEvolvData();
  const token=session?.access_token??"",owner=user?.id??"";
  const store=useMemo(()=>new CoachSession(new CoachApi(""),()=>Crypto.randomUUID(),owner),[owner]);
  const prior=useRef(store);
  useEffect(()=>{
    if(prior.current!==store)prior.current.dispose();
    prior.current=store;
    store.setTransport(new CoachApi(token));
    if(token&&owner&&!store.getSnapshot().conversations.length)void store.loadConversations();
  },[store,token,owner]);
  const state=useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot);
  const [draft,setDraft]=useState(""),[history,setHistory]=useState(false),[keyboard,setKeyboard]=useState(false);
  const [editing,setEditing]=useState<Conversation|null>(null),[title,setTitle]=useState("");
  const [deleting,setDeleting]=useState<Conversation|null>(null);
  const [now,setNow]=useState(()=>Date.now());
  const styles=useMemo(()=>createStyles(palette),[palette]);
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),15000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    const a=Keyboard.addListener("keyboardDidShow",()=>setKeyboard(true)),b=Keyboard.addListener("keyboardDidHide",()=>setKeyboard(false));
    return()=>{a.remove();b.remove();};
  },[]);
  const disabled=state.busy||!token||Boolean(state.failedSend);
  const active=state.conversations.find(c=>c.id===state.conversationId);
  function send(text=draft){if(disabled||!text.trim())return;setDraft("");void store.send(text);}
  async function decide(operation:"apply"|"reject"|"revert"){
    await store.decide(operation);
    if(!store.getSnapshot().error)await data.refresh();
  }
  function button(label:string,action:()=>void,secondary=false,blocked=state.busy){
    return <Pressable accessibilityRole="button" accessibilityState={{disabled:blocked}} disabled={blocked}
      onPress={action} style={[styles.button,secondary&&styles.secondary,blocked&&styles.disabled]}>
      <Text style={[styles.buttonText,secondary&&{color:palette.text}]}>{label}</Text></Pressable>;
  }
  function dialog(visible:boolean,label:string,onClose:()=>void,children:ReactNode){
    return <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}><View style={styles.sheet} accessibilityViewIsModal>
        <View style={styles.row}><Text style={styles.title}>{label}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Fechar" onPress={onClose} disabled={state.busy} style={styles.icon}>
            <X color={palette.text} size={22}/></Pressable></View>{children}</View></View></Modal>;
  }
  function message(row:ChatMessage){
    const reply=row.reply,cited=reply?.result.citations?.cited_chunk_ids??[],matches=reply?.result.retrieval?.matches??[];
    const pending=reply?.result.actions?.find(a=>a.status==="pending_user_confirmation");
    const previews=reply?.planner_previews??[];
    const copy=pending?row.live?"Há uma proposta de mudança para você revisar. Seu plano ainda não foi alterado.":
      "Esta conversa registrou uma proposta de mudança. Peça uma nova proposta para continuar.":
      previews.length?!row.live?"Prévia registrada nesta conversa. Abra para consultar o estado atual.":
      previews.some(p=>p.reverted_at)?"A alteração foi desfeita. Você pode consultar os detalhes abaixo.":
      previews.some(p=>p.status==="applied")?"A alteração foi aplicada. Confira os detalhes abaixo.":
      previews.some(p=>p.status==="pending")?"Confira abaixo o que muda e o que permanece. Nada foi aplicado ainda.":
      "A prévia foi encerrada. Você pode consultar os detalhes abaixo.":
      row.role==="assistant"?coachDisplayText(row.content):row.content;
    const visibleMatches=cited.length||reply?.result.grounding?matches.filter(m=>cited.includes(m.id)):matches;
    const sources=[...new Map(visibleMatches
      .flatMap(m=>m.citations??[]).filter(s=>s.url?.startsWith("https://")).map(s=>[s.url,s])).values()];
    return <View key={row.id} style={[styles.bubble,row.role==="user"?styles.user:styles.assistant]}>
      <Text style={[styles.label,row.role==="user"&&{color:"#EBC7C2"}]}>{row.role==="user"?"Você":"Coach Evolv"}</Text>
      <Text selectable style={[styles.text,row.role==="user"&&{color:colors.text}]}>{copy}</Text>
      {row.pending?<Text style={styles.hint}>{state.busy?"Enviando…":"Envio não confirmado"}</Text>:null}
      {!reply?.result.grounding&&reply?.result.generation?.stopped_at_eos===false?<Text style={styles.hint}>A resposta foi interrompida. Você pode pedir para continuar.</Text>:null}
      {sources.length?<View style={styles.sourceList}><Text style={styles.label}>{cited.length?"Fontes citadas":"Base consultada"}</Text>
        {sources.map(s=><Pressable key={s.url} accessibilityRole="link" onPress={()=>void Linking.openURL(s.url!).catch(()=>undefined)}>
          <Text style={styles.source}>{s.title}</Text></Pressable>)}</View>:null}
      {reply?.result.actions?.filter(a=>a.status==="pending_user_confirmation").map(p=><View key={p.id} style={styles.action}>
        <Text style={styles.text}>Uma mudança foi proposta. Peça a prévia para ver o que será alterado.</Text>
        {row.live&&Date.parse(p.expires_at)>now?<View style={styles.buttons}>
          {button("Ver prévia",()=>void store.proposal(p,true),false,disabled)}
          {button("Não quero",()=>void store.proposal(p,false),true,disabled)}
        </View>:<Text style={styles.hint}>Para confirmar, peça uma nova proposta nesta conversa.</Text>}
      </View>)}
      {reply?.planner_previews?.map(p=><View key={p.id} style={styles.action}>
        <Text style={styles.text}>{p.preview.title}</Text><Text style={styles.hint}>{p.preview.summary}</Text>
        {button("Revisar ajuste",()=>void store.review(p.id),true)}</View>)}
    </View>;
  }
  const preview=state.preview;
  return <KeyboardAvoidingView style={{flex:1,backgroundColor:palette.page}} behavior={Platform.OS==="ios"?"padding":undefined}>
    <AppScreen scrollToEndKey={state.messages.at(-1)?.id}
      header={<PageHeader eyebrow="Evolv" title="Coach" actionIcon={History} actionLabel="Histórico de conversas"
        onAction={()=>{setHistory(true);void store.loadConversations();}}/>}
      footer={<View style={[styles.footer,{paddingBottom:keyboard?8:100}]}><View style={styles.footerInner}>
        <View style={styles.composer}><TextInput accessibilityLabel="Mensagem para o Coach" multiline maxLength={8000}
          placeholder="Fale com o Coach Evolv…" placeholderTextColor={palette.faint} style={styles.input}
          value={draft} onChangeText={setDraft} editable={!disabled} onSubmitEditing={()=>send()}/>
          <Pressable accessibilityRole="button" accessibilityLabel="Enviar mensagem" disabled={disabled||!draft.trim()}
            style={[styles.send,(disabled||!draft.trim())&&styles.disabled]} onPress={()=>send()}><Send size={20} color={colors.text}/></Pressable></View>
        <Text style={styles.footerNote}>Suas conversas ficam na sua conta. Conversar não treina o modelo.</Text></View></View>}>
      <View style={styles.row}><Text numberOfLines={1} style={[styles.title,{flex:1}]}>{active?.title??"Nova conversa"}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Nova conversa" disabled={disabled} onPress={()=>store.newConversation()} style={styles.icon}>
          <Plus color={palette.text} size={22}/></Pressable></View>
      {!state.messages.length?<><CinematicHero source={pickWeeklyImage(coachImages,images,"coach",0)}
        eyebrow="No seu ritmo" title="Vamos conversar." description="Treino, alimentação, recuperação. Qual é sua dúvida?" height={196} overlayOpacity={0.24}/>
        <View style={styles.prompts}>{quickCoachPrompts.map(prompt=><Pressable key={prompt} accessibilityRole="button" disabled={disabled}
          onPress={()=>send(prompt)} style={styles.prompt}><Text style={styles.hint}>{prompt}</Text></Pressable>)}</View></>:null}
      {state.hasMoreMessages?button("Mensagens anteriores",()=>void store.older(),true):null}
      <View style={styles.messages}>{state.messages.map(message)}</View>
      {state.busy?<View style={styles.row} accessibilityLiveRegion="polite"><ActivityIndicator color={colors.red}/><Text style={styles.hint}>Aguarde um instante…</Text></View>:null}
      {state.error?<View style={styles.error} accessibilityRole="alert"><Text style={styles.text}>{state.error}</Text>
        {state.failedSend?<View style={styles.buttons}>{button("Tentar novamente",()=>void store.retry())}
          {button("Consultar histórico",()=>{store.discardRetry();setHistory(true);void store.loadConversations();},true)}</View>:
          button("Atualizar histórico",()=>{setHistory(true);void store.loadConversations();},true)}</View>:null}
    </AppScreen>
    {dialog(history,"Suas conversas",()=>{if(!state.busy)setHistory(false);},<>
      {button("Nova conversa",()=>{store.newConversation();setHistory(false);},false,disabled)}
      <ScrollView style={styles.modalScroll}>{state.conversations.map(c=><View key={c.id} style={styles.historyRow}>
        <Pressable accessibilityRole="button" accessibilityLabel={"Abrir "+(c.title??"Conversa")} disabled={disabled}
          style={{flex:1}} onPress={()=>{setHistory(false);void store.select(c.id);}}>
          <Text style={styles.text}>{c.title??"Conversa"}</Text><Text style={styles.hint}>{new Date(c.updated_at).toLocaleDateString("pt-BR")}</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={"Renomear "+c.title} disabled={state.busy} style={styles.icon}
          onPress={()=>{setHistory(false);setEditing(c);setTitle(c.title??"");}}><Pencil size={18} color={palette.muted}/></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={"Excluir "+c.title} disabled={state.busy} style={styles.icon}
          onPress={()=>{setHistory(false);setDeleting(c);}}><Trash2 size={18} color={palette.muted}/></Pressable>
      </View>)}
      {!state.conversations.length?<Text style={styles.hint}>{state.busy?"Carregando…":"Suas conversas aparecerão aqui."}</Text>:null}
      {state.hasMoreConversations?button("Mais conversas",()=>void store.loadConversations(true),true):null}</ScrollView>
      {state.error?<Text style={styles.hint}>{state.error}</Text>:null}</>)}
    {dialog(Boolean(editing),"Nome da conversa",()=>setEditing(null),<>
      <TextInput accessibilityLabel="Nome da conversa" maxLength={80} value={title} onChangeText={setTitle} style={styles.input}/>
      {button("Salvar nome",()=>{if(editing)void store.rename(editing.id,title).then(()=>{if(!store.getSnapshot().error)setEditing(null);});},false,state.busy||!title.trim())}
      {state.error?<Text style={styles.hint}>{state.error}</Text>:null}</>)}
    {dialog(Boolean(deleting),"Excluir conversa?",()=>setDeleting(null),<>
      <Text style={styles.text}>As mensagens serão apagadas. Isso não desfaz alterações já aplicadas no seu plano.</Text>
      {button("Excluir conversa",()=>{if(deleting)void store.remove(deleting.id).then(()=>{if(!store.getSnapshot().error)setDeleting(null);});})}
      {button("Manter conversa",()=>setDeleting(null),true)}{state.error?<Text style={styles.hint}>{state.error}</Text>:null}</>)}
    {dialog(Boolean(preview),"Revisar alteração",()=>store.closePreview(),preview?<>
      <ScrollView style={styles.modalScroll}><Text style={styles.title}>{preview.preview.title}</Text><Text style={styles.text}>{preview.preview.summary}</Text>
        {(["changes","preserved","warnings"] as const).map(k=>preview.preview[k]?.length?<View key={k} style={styles.action}>
          <Text style={styles.label}>{{changes:"O que muda",preserved:"O que permanece",warnings:"Atenção"}[k]}</Text>
          {preview.preview[k].map((line,i)=><Text key={i} style={styles.text}>• {line}</Text>)}</View>:null)}
        <Text style={styles.hint}>{preview.reverted_at?"Alteração desfeita":preview.status==="applied"?"Alteração aplicada":preview.status==="rejected"?"Prévia descartada":"Confira a prévia antes de confirmar."}</Text></ScrollView>
      {preview.status==="pending"&&!preview.reverted_at?<View style={styles.buttons}>
        {button("Confirmar alteração",()=>void decide("apply"),false,state.busy||Date.parse(preview.expires_at)<=now)}
        {button("Descartar",()=>void decide("reject"),true)}</View>:null}
      {preview.status==="applied"&&preview.reversible&&!preview.reverted_at?button("Desfazer alteração",()=>void decide("revert"),true):null}
      {state.error?<Text style={styles.hint}>{state.error}</Text>:null}</>:null)}
  </KeyboardAvoidingView>;
}
const createStyles=(p:AppThemePalette)=>StyleSheet.create({
  row:{flexDirection:"row",alignItems:"center",gap:10},title:{color:p.text,fontSize:18,fontWeight:"600"},
  text:{color:p.text,fontSize:14,lineHeight:22},hint:{color:p.muted,fontSize:12,lineHeight:18},label:{color:p.muted,fontSize:11,fontWeight:"600",marginBottom:4},
  icon:{padding:10,minWidth:42,minHeight:42,alignItems:"center",justifyContent:"center"},
  messages:{gap:12},bubble:{maxWidth:"94%",borderRadius:16,padding:15,gap:5},user:{alignSelf:"flex-end",backgroundColor:colors.redDark},
  assistant:{alignSelf:"flex-start",backgroundColor:p.surface,borderWidth:1,borderColor:p.border},
  footer:{paddingHorizontal:20,paddingTop:10,backgroundColor:p.page,borderTopWidth:1,borderColor:p.border},
  footerInner:{width:"100%",maxWidth:760,alignSelf:"center"},
  footerNote:{color:p.faint,fontSize:10,lineHeight:15,marginTop:6},composer:{flexDirection:"row",gap:8,alignItems:"flex-end"},
  input:{flex:1,minHeight:48,maxHeight:120,borderWidth:1,borderColor:p.border,borderRadius:14,backgroundColor:p.surface,color:p.text,paddingHorizontal:14,paddingVertical:12,fontSize:14},
  send:{width:48,height:48,alignItems:"center",justifyContent:"center",borderRadius:24,backgroundColor:colors.red},
  prompts:{flexDirection:"row",flexWrap:"wrap",gap:8},prompt:{borderWidth:1,borderColor:p.border,borderRadius:20,paddingHorizontal:13,paddingVertical:10},
  button:{backgroundColor:colors.red,minHeight:44,borderRadius:22,paddingHorizontal:16,paddingVertical:12,alignItems:"center",justifyContent:"center"},
  secondary:{backgroundColor:p.elevated,borderWidth:1,borderColor:p.border},buttonText:{color:colors.text,fontSize:13,fontWeight:"600"},
  buttons:{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:8},disabled:{opacity:.45},
  action:{borderTopWidth:1,borderColor:p.border,paddingTop:12,marginTop:8,gap:6},sourceList:{marginTop:10,gap:6},
  source:{color:p.muted,fontSize:12,textDecorationLine:"underline"},
  error:{backgroundColor:p.elevated,borderLeftWidth:3,borderLeftColor:colors.red,padding:14,gap:10},
  backdrop:{flex:1,backgroundColor:"rgba(0,0,0,.65)",justifyContent:"center",padding:20},
  sheet:{backgroundColor:p.surface,borderColor:p.border,borderWidth:1,borderRadius:20,padding:20,gap:16,maxHeight:"85%",width:"100%",maxWidth:640,alignSelf:"center"},
  modalScroll:{flexGrow:0},historyRow:{flexDirection:"row",alignItems:"center",paddingVertical:12,borderBottomWidth:1,borderColor:p.border,gap:4},
});
