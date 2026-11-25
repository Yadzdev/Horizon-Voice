import { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowUpRight, AudioLines, ChevronRight, Copy, Headphones, LockKeyhole, Mic, Radio, Server, ShieldCheck, Users, Wifi } from 'lucide-react';
import { post, request } from './api';
import VoiceSession from './VoiceSession';

type PairCode = { pairing_code: string; expires_in_seconds: number; server_name: string; subdomain: string };
type PairStatus = { paired: boolean; player?: { id: string; name: string } | null };
type ServerInfo = { id: string; name: string; slug: string; status: string; subdomain: string };

function getTenant() {
  const query = new URLSearchParams(window.location.search).get('tenant');
  if (query) return query;
  const host = window.location.hostname.toLowerCase();
  const suffix = '.voice-horizon.online';
  return host.endsWith(suffix) ? host.slice(0, -suffix.length) : '';
}

export default function App() {
  const tenant = useMemo(getTenant, []);
  const [view, setView] = useState<'portal' | 'auth' | 'dashboard'>('portal');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState(sessionStorage.getItem('hv_access_token') || '');
  const [pair, setPair] = useState<PairCode | null>(null);
  const [paired, setPaired] = useState<PairStatus | null>(null);
  const [servers, setServers] = useState<ServerInfo[]>([]);
  const [serverName, setServerName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [activation, setActivation] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token || view !== 'dashboard') return;
    request<{servers: ServerInfo[]}>('/dashboard/servers', {}, token).then(x => setServers(x.servers)).catch(e => {
      setError(e.message); setToken(''); sessionStorage.removeItem('hv_access_token');
    });
  }, [token, view]);

  useEffect(() => {
    if (!tenant || pair) return;
    let cancelled = false;
    request<PairStatus>('/pairing/status').then(result => {
      if (cancelled || !result.paired) return;
      setPair({ pairing_code: '', expires_in_seconds: 0, server_name: tenant, subdomain: tenant });
      setPaired(result);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [tenant, pair]);

  useEffect(() => {
    if (!pair) return;
    let stopped = false;
    const poll = async () => {
      try {
        const status = await request<PairStatus>('/pairing/status');
        if (!stopped) {
          setPaired(status);
          if (!status.paired) {
            setPair(null);
            setPaired(null);
          }
        }
      } catch (e) { if (!stopped) setError((e as Error).message); }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2500);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [pair]);

  async function startPairing() {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await post<PairCode>('/pairing/codes');
      setPair(result); setPaired(null);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await post<{access_token: string}>(authMode === 'register' ? '/auth/register' : '/auth/login', { email, password });
      setToken(result.access_token); sessionStorage.setItem('hv_access_token', result.access_token); setView('dashboard');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function createServer(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice(''); setActivation('');
    try {
      const result = await post<{activation_code: string; subdomain: string}>('/servers', { name: serverName, slug, description }, token);
      setActivation(result.activation_code); setNotice(`Servidor criado em ${result.subdomain}. Ative-o no console do BDS.`);
      const refreshed = await request<{servers: ServerInfo[]}>('/dashboard/servers', {}, token); setServers(refreshed.servers);
      setServerName(''); setSlug(''); setDescription('');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setNotice('Copiado para a área de transferência.'); }
    catch { setNotice(`Copie manualmente: ${value}`); }
  }

  function logout() {
    setToken(''); sessionStorage.removeItem('hv_access_token'); setView('portal'); setServers([]);
  }

  return <div className="app-shell">
    <div className="ambient ambient-one"/><div className="ambient ambient-two"/>
    <header className="topbar">
      <a className="brand" href="#home" onClick={() => setView('portal')}><span className="brand-mark"><AudioLines size={21}/></span><span>HORIZON<span className="brand-light">VOICE</span><small>BEDROCK COMMUNICATION</small></span></a>
      <div className="top-actions"><span className="status-pill"><i/> PLATAFORMA EM DESENVOLVIMENTO</span>{view === 'dashboard' ? <button className="ghost small" onClick={logout}>Sair</button> : <button className="ghost small" onClick={() => {setView('auth');setAuthMode('login')}}>Painel do servidor <ArrowUpRight size={14}/></button>}</div>
    </header>

    {view === 'portal' && <main className="hero-layout">
      <section className="hero-copy">
        <div className="eyebrow"><span/> VOZ EM TEMPO REAL PARA BEDROCK</div>
        <h1>Jogue junto.<br/><em>Fale de perto.</em></h1>
        <p className="hero-lead">Comunicação por voz pensada para servidores Minecraft Bedrock. Entre no mundo, conecte seu navegador e aproxime a conversa de quem está ao seu redor.</p>
        <div className="feature-row"><div><span><Radio size={18}/></span><b>Proximidade</b><small>Distância e dimensão</small></div><div><span><Users size={18}/></span><b>Grupos</b><small>Salas privadas</small></div><div><span><ShieldCheck size={18}/></span><b>Controle</b><small>Moderação do servidor</small></div></div>
        <div className="trust-note"><LockKeyhole size={14}/> O áudio não deve ser gravado. O acesso ao microfone só é solicitado após ação do jogador.</div>
      </section>
      <section className="connect-card">
        <div className="card-top"><div><span className="step-label">{tenant ? 'SERVIDOR CONECTADO AO PORTAL' : 'COMECE AQUI'}</span><h2>{tenant ? 'Conectar ao servidor' : 'Horizon Voice'}</h2></div><div className="card-icon"><Headphones size={22}/></div></div>
        {tenant ? <>
          <p className="muted">Servidor <strong className="tenant-name">{tenant}</strong>. Gere um código de uso único e vincule sua sessão pelo Minecraft.</p>
          {!pair ? <button className="primary full" disabled={busy} onClick={startPairing}>{busy ? 'Gerando código…' : 'Gerar código de conexão'} <ChevronRight size={17}/></button> : <div className="pair-panel">
            {!paired?.paired && <><span className="step-label">SEU CÓDIGO TEMPORÁRIO</span><div className="pair-code">{pair.pairing_code}<button aria-label="Copiar código" onClick={() => void copy(pair.pairing_code)}><Copy size={16}/></button></div>
            <div className="command-row"><code>/horizon:voz</code><button onClick={() => void copy('/horizon:voz')}><Copy size={14}/></button></div>
            <p className="muted tiny">No Minecraft, execute o comando e escolha “Vincular navegador”. O código expira em {pair.expires_in_seconds} segundos.</p></>}
            <div className={`pair-status ${paired?.paired ? 'success' : ''}`}><i/>{paired?.paired ? `Vinculado: ${paired.player?.name}` : 'Aguardando confirmação no Minecraft…'}</div>
            {paired?.paired && <VoiceSession playerName={paired.player?.name || 'Jogador'} onNotice={setNotice} onError={setError}/>}
            {!paired?.paired && <button className="ghost full" onClick={() => {setPair(null);setPaired(null);}}>Gerar outro código</button>}
          </div>}
          <div className="steps"><b>Como conectar</b><ol><li>Gere um código temporário aqui.</li><li>Entre no servidor Bedrock e use o comando exibido.</li><li>Informe o código no formulário do add-on.</li><li>O portal confirmará o pareamento automaticamente.</li></ol></div>
        </> : <>
          <p className="muted">Acesse o subdomínio do seu servidor para vincular seu jogador. Administradores podem criar uma conta para registrar um BDS.</p>
          <button className="primary full" onClick={() => {setView('auth');setAuthMode('register')}}>Registrar um servidor <ChevronRight size={17}/></button>
          <button className="ghost full margin-top" onClick={() => {setView('auth');setAuthMode('login')}}>Entrar no painel do proprietário</button>
          <div className="steps"><b>O que está no projeto</b><div className="stack-line"><Wifi size={15}/> API de registro e presença</div><div className="stack-line"><Activity size={15}/> Sincronização de estados do jogador</div><div className="stack-line"><Mic size={15}/> Áudio WebRTC com controle de proximidade no servidor</div></div>
        </>}
      </section>
    </main>}

    {view === 'auth' && <main className="single-layout"><section className="connect-card auth-card"><div className="card-top"><div><span className="step-label">ÁREA DO PROPRIETÁRIO</span><h2>{authMode === 'login' ? 'Bem-vindo de volta' : 'Criar conta Horizon'}</h2></div><div className="card-icon"><Server size={21}/></div></div><form onSubmit={submitAuth} className="form-stack"><label>E-mail<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email" placeholder="voce@exemplo.com"/></label><label>Senha<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={12} autoComplete={authMode==='login'?'current-password':'new-password'} placeholder="Mínimo de 12 caracteres"/></label><button className="primary full" disabled={busy}>{busy?'Aguarde…':authMode==='login'?'Entrar no painel':'Criar conta'} <ChevronRight size={17}/></button></form><button className="text-button" onClick={()=>setAuthMode(authMode==='login'?'register':'login')}>{authMode==='login'?'Ainda não tem conta? Criar conta':'Já possui conta? Entrar'}</button><button className="ghost full margin-top" onClick={()=>setView('portal')}>Voltar</button></section></main>}

    {view === 'dashboard' && <main className="dashboard-layout"><div className="dashboard-heading"><div><span className="eyebrow"><span/> PAINEL DO PROPRIETÁRIO</span><h1>Seus <em>servidores.</em></h1><p className="muted">Registre seus servidores Bedrock e acompanhe o estado de ativação.</p></div><div className="dashboard-stat"><Server size={19}/><b>{servers.length}</b><small>SERVIDORES</small></div></div><div className="dashboard-grid"><section className="connect-card"><div className="card-top"><div><span className="step-label">NOVO AMBIENTE</span><h2>Registrar servidor</h2></div><div className="card-icon"><Server size={21}/></div></div><form onSubmit={createServer} className="form-stack"><label>Nome do servidor<input value={serverName} onChange={e=>setServerName(e.target.value)} required minLength={2} maxLength={80} placeholder="Meu servidor Bedrock"/></label><label>Subdomínio<input value={slug} onChange={e=>setSlug(e.target.value.toLowerCase())} required minLength={3} maxLength={50} pattern="[a-z0-9]+([a-z0-9-]*[a-z0-9])?" placeholder="meuservidor"/><small className="field-hint">{slug || 'seuservidor'}.voice-horizon.online</small></label><label>Descrição<input value={description} onChange={e=>setDescription(e.target.value)} maxLength={240} placeholder="Opcional"/></label><button className="primary full" disabled={busy}>{busy?'Criando…':'Gerar código de ativação'} <ChevronRight size={17}/></button></form>{activation && <div className="activation"><span className="step-label">CÓDIGO PARA O CONSOLE DO BDS</span><code>{activation}</code><p>Execute <b>/horizon:cadastrarvoice {activation}</b> no ambiente administrativo do mundo.</p><button className="ghost full" onClick={()=>void copy(`/horizon:cadastrarvoice ${activation}`)}><Copy size={14}/> Copiar comando</button></div>}</section><section className="connect-card server-list"><div className="card-top"><div><span className="step-label">SEUS AMBIENTES</span><h2>Servidores registrados</h2></div><div className="card-icon"><Activity size={21}/></div></div>{servers.length===0?<div className="empty"><Server size={25}/><b>Nenhum servidor ainda</b><span>Crie seu primeiro ambiente ao lado.</span></div>:servers.map(server=><div className="server-item" key={server.id}><span className="server-avatar"><Server size={18}/></span><span className="server-meta"><b>{server.name}</b><small>{server.subdomain}</small></span><span className={`status-tag ${server.status}`}>{server.status==='active'?'ATIVO':'PENDENTE'}</span></div>)}</section></div></main>}

    {(notice || error) && <div className={`toast ${error?'error':''}`} role="status">{error || notice}<button onClick={()=>{setError('');setNotice('')}}>×</button></div>}
    <footer className="footer"><span>HORIZON VOICE <i>•</i> PROJETO EM DESENVOLVIMENTO</span><span>BEDROCK DEDICATED SERVER</span></footer>
  </div>;
}
