import { useEffect,useMemo,useRef,useState,useSyncExternalStore,type ReactNode } from "react";
import { ActivityIndicator,Keyboard,KeyboardAvoidingView,Linking,Modal,Platform,ScrollView,StyleSheet,Text,TextInput,View } from "react-native";
import { History, Plus, Send, X, Pencil, Trash2 } from "lucide-react-native";
import * as Crypto from "expo-crypto";
import { TouchFeedback as Pressable } from "@/components/touch-feedback";
import { AppScreen } from "@/components/ui";
import { colors, typography } from "@/constants/theme";
import { useAppTheme,type AppThemePalette } from "@/context/theme-context";
import { useAuth } from "@/context/auth-context";
import { useEvolvData } from "@/context/evolv-data-context";
import { quickCoachPrompts } from "@/data/mock-data";
import { CoachApi } from "@/services/coach-api";
import { CoachSession,coachDisplayText,coachLimitMessage } from "@/lib/coach-session";
import type { Conversation,ChatMessage } from "@/types/coach";

export default function CoachScreen(){
  const {user}=useAuth();
  return <ConnectedCoach key={user?.id??"guest"}/>;
}
function conversationTitle(conversation?: Conversation) {
  return conversation?.title?.trim() || "Conversa sem título";
}

function ConnectedCoach(){
  const {palette}=useAppTheme(),{user,session}=useAuth(),data=useEvolvData();
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
  const [composerFocused, setComposerFocused] = useState(false);
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
  const lastReply=[...state.messages].reverse().find(m=>m.reply)?.reply;
  const appliedRequest = lastReply?.result.planner?.applied &&
    state.messages.some(message => message.live && message.reply === lastReply)
    ? lastReply.request_id : null;
  const refreshData = data.refresh;
  useEffect(() => {
    if (appliedRequest) void refreshData();
  }, [appliedRequest, refreshData]);
  const memory=lastReply?.result.conversation_memory;
  const memoryUsage=memory?.limit?memory.used/memory.limit:0;
  const reachedLimit=memoryUsage>=1||state.error===coachLimitMessage;
  function startFresh(){
    if(state.failedSend){setDraft(state.failedSend.text);store.discardRetry();}
    store.newConversation();
  }
  const active=state.conversations.find(c=>c.id===state.conversationId);
  function send(text=draft){if(disabled||reachedLimit||!text.trim())return;setDraft("");void store.send(text);}
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
  function avatar(small = false) {
    return <View accessible={false} aria-hidden style={[styles.avatar, small && styles.avatarSmall]}>
      <Text style={[styles.avatarMark, small && styles.avatarMarkSmall]}>E<Text style={styles.avatarDot}>.</Text></Text>
    </View>;
  }
  function message(row:ChatMessage){
    const reply=row.reply,cited=reply?.result.citations?.cited_chunk_ids??[],matches=reply?.result.retrieval?.matches??[];
    const pending=reply?.result.actions?.find(a=>a.status==="pending_user_confirmation");
    const previews=reply?.planner_previews??[];
    const copy=pending?row.live?"Há uma proposta de mudança para você revisar. Seu plano ainda não foi alterado.":
      "Esta conversa registrou uma proposta de mudança. Peça uma nova proposta para continuar.":
      previews.length?!row.live?"Ajuste registrado nesta conversa. Abra para consultar o estado atual.":
      previews.some(p=>p.reverted_at)?"A alteração foi desfeita. Você pode consultar os detalhes abaixo.":
      previews.some(p=>p.status==="applied")?(reply?.result.planner?.applied?coachDisplayText(row.content):"A alteração foi aplicada. Confira os detalhes abaixo."):
      previews.some(p=>p.status==="pending")?"Confira abaixo o que muda e o que permanece. Nada foi aplicado ainda.":
      "A prévia foi encerrada. Você pode consultar os detalhes abaixo.":
      row.role==="assistant"?coachDisplayText(row.content):row.content;
    const visibleMatches=cited.length||reply?.result.grounding?matches.filter(m=>cited.includes(m.id)):matches;
    const sources=[...new Map(visibleMatches
      .flatMap(m=>m.citations??[]).filter(s=>s.url?.startsWith("https://")).map(s=>[s.url,s])).values()];
    const fromUser = row.role === "user";
    return <View key={row.id} style={[styles.messageRow, fromUser && styles.messageRowUser]}>
      {fromUser ? null : avatar(true)}
      <View style={[styles.bubble, fromUser ? styles.user : styles.assistant]}>
        <Text selectable accessibilityLabel={`${fromUser ? "Você" : "Coach Evolv"}: ${copy}`}
          style={[styles.messageText, fromUser && styles.userText]}>{copy}</Text>
        {row.pending ? <Text style={[styles.hint, styles.userStatus]}>
          {state.busy ? "Enviando…" : "Envio não confirmado"}
        </Text> : null}
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
          {button(p.status==="applied"&&!p.reverted_at?"Ver ajuste e desfazer":"Revisar ajuste",()=>void store.review(p.id),true)}</View>)}
      </View>
    </View>;
  }
  const preview=state.preview;
  const sendDisabled = disabled || reachedLimit || !draft.trim();
  const isOpening = state.busy && Boolean(state.conversationId) && !state.messages.length;
  const isResponding = state.busy && state.messages.at(-1)?.pending;
  const chatHeader = (
    <View style={styles.header} testID="coach-top-bar">
      <View style={styles.headerInner}>
        <Pressable accessibilityRole="button" accessibilityLabel="Histórico de conversas" style={styles.headerButton}
          onPress={() => { setHistory(true); void store.loadConversations(); }}>
          <History color={palette.text} size={20} />
        </Pressable>
        {avatar()}
        <View style={styles.headerIdentity}>
          <Text accessibilityRole="header" numberOfLines={1} style={styles.headerTitle}>Coach Evolv</Text>
          <Text numberOfLines={1} style={styles.headerSubtitle}>{state.conversationId ? conversationTitle(active) : "Nova conversa"}</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Nova conversa" disabled={disabled}
          onPress={startFresh} style={[styles.headerButton, disabled && styles.disabled]}>
          <Plus color={palette.text} size={21} />
        </Pressable>
      </View>
    </View>
  );
  const composer = (
    <View style={[styles.footer, { paddingBottom: keyboard ? 8 : 100 }]}>
      <View style={styles.footerInner}>
        <View style={styles.composer}>
          <TextInput accessibilityLabel="Mensagem para o Coach" multiline numberOfLines={1} maxLength={8000}
            placeholder="Escreva uma mensagem…" placeholderTextColor={palette.faint}
            style={[styles.input, composerFocused && styles.inputFocused]}
            value={draft} onChangeText={setDraft} editable={!disabled && !reachedLimit}
            onFocus={() => setComposerFocused(true)} onBlur={() => setComposerFocused(false)}
            onSubmitEditing={() => send()} />
          <Pressable accessibilityRole="button" accessibilityLabel="Enviar mensagem" disabled={sendDisabled}
            style={[styles.send, sendDisabled && styles.sendDisabled]} onPress={() => send()}>
            <Send size={20} color={sendDisabled ? palette.faint : palette.onPrimary} strokeWidth={1.8} />
          </Pressable>
        </View>
        <Text style={styles.footerNote}>Suas conversas ficam na sua conta. Conversar não treina o modelo.</Text>
      </View>
    </View>
  );

  return <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === "ios" ? "padding" : undefined}>
    <AppScreen scrollToEndKey={state.messages.at(-1)?.id} fixedHeader={chatHeader} footer={composer} contentStyle={styles.thread}>
      {!state.messages.length && !isOpening ? <>
        <View style={styles.messageRow}>
          {avatar(true)}
          <View style={[styles.bubble, styles.assistant]}>
            <Text style={styles.messageText}>Oi! Posso ajudar com seu treino ou sua alimentação. Por onde quer começar?</Text>
          </View>
        </View>
        <View style={styles.prompts}>
          {quickCoachPrompts.map(prompt => (
            <Pressable key={prompt} accessibilityRole="button" disabled={disabled}
              onPress={() => send(prompt)} style={[styles.prompt, disabled && styles.disabled]}>
              <Text style={styles.promptText}>{prompt}</Text>
            </Pressable>
          ))}
        </View>
      </> : null}
      {state.hasMoreMessages?button("Mensagens anteriores",()=>void store.older(),true):null}
      {state.messages.length ? <View style={styles.messages}>{state.messages.map(message)}</View> : null}
      {reachedLimit?<View style={styles.error}>
        <Text style={styles.text}>{coachLimitMessage}</Text>
        {button("Abrir nova conversa",startFresh)}
      </View>:memoryUsage>=0.8?
        <Text style={styles.hint}>O contexto desta conversa está chegando ao limite.</Text>:null}
      {isOpening || isResponding ? <View style={styles.messageRow} accessibilityLiveRegion="polite">
        {avatar(true)}
        <View style={[styles.bubble, styles.assistant, styles.typing]}>
          <ActivityIndicator size="small" color={palette.accentText} />
          <Text style={styles.hint}>{isOpening ? "Abrindo conversa…" : "Coach respondendo…"}</Text>
        </View>
      </View> : null}
      {state.error&&state.error!==coachLimitMessage?<View style={styles.error} accessibilityRole="alert"><Text style={styles.text}>{state.error}</Text>
        {state.failedSend?<View style={styles.buttons}>{button("Tentar novamente",()=>void store.retry())}
          {button("Consultar histórico",()=>{store.discardRetry();setHistory(true);void store.loadConversations();},true)}</View>:
          button("Atualizar histórico",()=>{setHistory(true);void store.loadConversations();},true)}</View>:null}
    </AppScreen>
    {dialog(history,"Suas conversas",()=>{if(!state.busy)setHistory(false);},<>
      {button("Nova conversa",()=>{store.newConversation();setHistory(false);},false,disabled)}
      <ScrollView style={styles.modalScroll}>{state.conversations.map(c=><View key={c.id} style={styles.historyRow}>
        <Pressable accessibilityRole="button" accessibilityLabel={"Abrir " + conversationTitle(c)} disabled={disabled}
          style={{flex:1}} onPress={()=>{setHistory(false);void store.select(c.id);}}>
          <Text style={styles.text}>{conversationTitle(c)}</Text><Text style={styles.hint}>{new Date(c.updated_at).toLocaleDateString("pt-BR")}</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={"Renomear " + conversationTitle(c)} disabled={state.busy} style={styles.icon}
          onPress={()=>{setHistory(false);setEditing(c);setTitle(c.title??"");}}><Pencil size={18} color={palette.muted}/></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={"Excluir " + conversationTitle(c)} disabled={state.busy} style={styles.icon}
          onPress={()=>{setHistory(false);setDeleting(c);}}><Trash2 size={18} color={palette.muted}/></Pressable>
      </View>)}
      {!state.conversations.length?<Text style={styles.hint}>{state.busy?"Carregando…":"Suas conversas aparecerão aqui."}</Text>:null}
      {state.hasMoreConversations?button("Mais conversas",()=>void store.loadConversations(true),true):null}</ScrollView>
      {state.error?<Text style={styles.hint}>{state.error}</Text>:null}</>)}
    {dialog(Boolean(editing),"Renomear conversa",()=>setEditing(null),<>
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
  screen: { flex: 1, backgroundColor: p.page },
  header: { backgroundColor: p.page, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: p.border },
  headerInner: { width: "100%", maxWidth: 760, alignSelf: "center", flexDirection: "row",
    alignItems: "center", gap: 10, paddingVertical: 9, paddingHorizontal: 16 },
  headerButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center",
    borderRadius: 22, backgroundColor: p.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: p.border },
  avatar: { flexShrink: 0, width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center", backgroundColor: p.primary },
  avatarSmall: { width: 30, height: 30, borderRadius: 9 },
  avatarMark: { fontFamily: typography.display, fontWeight: "800", fontSize: 23, lineHeight: 27, color: p.onPrimary, letterSpacing: -1 },
  avatarMarkSmall: { fontSize: 17, lineHeight: 20 },
  avatarDot: { color: "#A8D5FF" },
  headerIdentity: { flex: 1, minWidth: 0, gap: 2 },
  headerTitle: { color: p.text, fontSize: 15, lineHeight: 19, fontWeight: "700" },
  headerSubtitle: { color: p.muted, fontSize: 12, lineHeight: 16 },
  thread: { paddingTop: 20, paddingBottom: 20, gap: 16 },
  messages: { gap: 16 },
  messageRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  messageRowUser: { justifyContent: "flex-end", paddingLeft: 38 },
  bubble: { maxWidth: "100%", flexShrink: 1, minWidth: 0, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 11, gap: 6 },
  user: { backgroundColor: p.primary, borderBottomRightRadius: 5 },
  assistant: { backgroundColor: p.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: p.border, borderTopLeftRadius: 5 },
  messageText: { color: p.text, fontSize: 15, lineHeight: 23 },
  userText: { color: p.onPrimary },
  userStatus: { color: p.onPrimary, opacity: 0.9 },
  typing: { flexDirection: "row", alignItems: "center", gap: 8 },
  footer: { paddingHorizontal: 16, paddingTop: 10, backgroundColor: p.page, borderTopWidth: StyleSheet.hairlineWidth, borderColor: p.border },
  footerInner: { width: "100%", maxWidth: 728, alignSelf: "center" },
  footerNote: { color: p.faint, fontSize: 10, lineHeight: 15, marginTop: 6 },
  composer: { flexDirection: "row", gap: 9, alignItems: "center" },
  input: { flex: 1, minWidth: 0, minHeight: 46, maxHeight: 120, borderWidth: 1, borderColor: p.border,
    borderRadius: 23, backgroundColor: p.surface, color: p.text, paddingHorizontal: 15, paddingVertical: 10, fontSize: 14, lineHeight: 22 },
  inputFocused: { borderColor: p.accentText },
  send: { width: 46, height: 46, alignItems: "center", justifyContent: "center", borderRadius: 23, backgroundColor: p.primary },
  sendDisabled: { backgroundColor: p.elevated },
  prompts: { alignItems: "flex-end", gap: 9, paddingLeft: 38 },
  prompt: { maxWidth: "100%", minHeight: 44, justifyContent: "center", backgroundColor: p.accentSoft,
    borderRadius: 22, paddingHorizontal: 15, paddingVertical: 9 },
  promptText: { color: p.accentText, fontSize: 14, lineHeight: 20, fontWeight: "600" },
  button:{backgroundColor:p.primary,minHeight:44,borderRadius:22,paddingHorizontal:16,paddingVertical:12,alignItems:"center",justifyContent:"center"},
  secondary:{backgroundColor:p.elevated,borderWidth:1,borderColor:p.border},buttonText:{color:p.onPrimary,fontSize:13,fontWeight:"600"},
  buttons:{flexDirection:"row",flexWrap:"wrap",gap:8,marginTop:8},disabled:{opacity:.45},
  action:{borderTopWidth:1,borderColor:p.border,paddingTop:12,marginTop:8,gap:6},sourceList:{marginTop:10,gap:6},
  source:{color:p.muted,fontSize:12,textDecorationLine:"underline"},
  error:{backgroundColor:p.elevated,borderLeftWidth:3,borderLeftColor:colors.red,padding:14,gap:10},
  backdrop:{flex:1,backgroundColor:"rgba(0,0,0,.65)",justifyContent:"center",padding:20},
  sheet:{backgroundColor:p.surface,borderColor:p.border,borderWidth:1,borderRadius:24,padding:20,gap:16,maxHeight:"85%",width:"100%",maxWidth:640,alignSelf:"center"},
  modalScroll:{flexGrow:0},historyRow:{flexDirection:"row",alignItems:"center",paddingVertical:12,borderBottomWidth:1,borderColor:p.border,gap:4},
});
