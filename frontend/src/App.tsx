import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import React from 'react';
import {
  Activity, ArrowRight, ChevronRight, Copy, ExternalLink,
  Headphones, ImagePlus, LockKeyhole, Mic, Radio, Server, ShieldCheck,
  Users, Wifi, X, Pickaxe, Volume2
} from 'lucide-react';
import { post, request, uploadServerImage } from './api';
import VoiceSession from './VoiceSession';
import { getTenant } from './tenant';

type PairCode = { pairing_code: string; expires_in_seconds: number; server_name: string; subdomain: string };
type PairStatus = { paired: boolean; player?: { id: string; name: string } | null };
type ServerInfo = {
  id: string; name: string; slug: string; status: string; subdomain: string;
  description?: string; image_url?: string | null;
};
type TenantInfo = {
  id: string; name: string; slug: string; description: string; status: string; image_url: string | null;
};

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_UPLOAD_BYTES = 2.5 * 1024 * 1024;

function formatStatus(status: string) {
  return status === 'active' ? 'Online' : 'Aguardando ativação';
}

async function optimizeServerImage(file: File): Promise<Blob> {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    throw new Error('Escolha uma imagem PNG, JPG ou WebP.');
  }
  if (file.size > MAX_IMAGE_BYTES) throw new Error('A imagem original deve ter até 10 MB.');
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, 1440 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Seu navegador não conseguiu preparar a imagem.');
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/webp', 0.84));
    if (!blob) throw new Error('Não foi possível otimizar a imagem.');
    if (blob.size > MAX_UPLOAD_BYTES) throw new Error('A imagem ficou maior que 2,5 MB. Escolha uma imagem menor.');
    return blob;
  } finally {
    bitmap.close();
  }
}

function BlockMark({ small = false }: { small?: boolean }) {
  return <span className={'block-mark' + (small ? ' block-mark-small' : '')} aria-hidden="true">
    <i /><i /><i /><i /><b />
  </span>;
}

function Brand({ onClick }: { onClick: () => void }) {
  return <button className="brand" type="button" onClick={onClick} aria-label="Horizon Voice — início">
    <BlockMark />
    <span className="brand-name">HORIZON <b>VOICE</b><small>VOICE CHAT FOR BEDROCK</small></span>
  </button>;
}

function PixelButton({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={'pixel-button ' + (props.className || '')}>{children}</button>;
}

function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return <div className="skeleton-list" aria-label="Carregando conteúdo" role="status">
    {Array.from({ length: rows }, (_, i) => <div className="skeleton-row" key={i}>
      <span className="skeleton-square" /><span className="skeleton-lines"><i /><i /></span>
    </div>)}
  </div>;
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
  const [serversLoading, setServersLoading] = useState(false);
  const [tenantInfo, setTenantInfo] = useState<TenantInfo | null>(null);
  const [tenantLoading, setTenantLoading] = useState(Boolean(tenant));
  const [serverName, setServerName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [serverImage, setServerImage] = useState<File | null>(null);
  const [serverImagePreview, setServerImagePreview] = useState('');
  const [activation, setActivation] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyStage, setBusyStage] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token || view !== 'dashboard') return;
    setServersLoading(true);
    request<{ servers: ServerInfo[] }>('/dashboard/servers', {}, token)
      .then(result => setServers(result.servers || []))
      .catch(e => {
        setError((e as Error).message);
        setToken('');
        sessionStorage.removeItem('hv_access_token');
      })
      .finally(() => setServersLoading(false));
  }, [token, view]);

  useEffect(() => {
    if (!tenant) return;
    let cancelled = false;
    setTenantLoading(true);
    request<TenantInfo>('/public/servers/' + encodeURIComponent(tenant))
      .then(result => { if (!cancelled) setTenantInfo(result); })
      .catch(e => { if (!cancelled) setError((e as Error).message || 'Servidor não encontrado.'); })
      .finally(() => { if (!cancelled) setTenantLoading(false); });
    return () => { cancelled = true; };
  }, [tenant]);

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
      } catch (e) {
        if (!stopped) setError((e as Error).message);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2500);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [pair]);

  useEffect(() => {
    if (!serverImage) { setServerImagePreview(''); return; }
    const url = URL.createObjectURL(serverImage);
    setServerImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [serverImage]);

  async function startPairing() {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await post<PairCode>('/pairing/codes');
      setPair(result); setPaired(null);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const result = await post<{ access_token: string }>(
        authMode === 'register' ? '/auth/register' : '/auth/login',
        { email, password }
      );
      setToken(result.access_token);
      sessionStorage.setItem('hv_access_token', result.access_token);
      setView('dashboard');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null;
    setError('');
    if (file && !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setError('Formato inválido. Envie PNG, JPG ou WebP.');
      event.target.value = '';
      return;
    }
    if (file && file.size > MAX_IMAGE_BYTES) {
      setError('A imagem original deve ter até 10 MB.');
      event.target.value = '';
      return;
    }
    setServerImage(file);
  }

  async function createServer(event: FormEvent) {
    event.preventDefault(); setBusy(true); setBusyStage('Criando servidor'); setError(''); setNotice(''); setActivation('');
    try {
      const result = await post<{ server_id: string; activation_code: string; subdomain: string }>(
        '/servers', { name: serverName, slug, description }, token
      );
      setActivation(result.activation_code);
      let imageWasSaved = true;
      if (serverImage) {
        try {
          setBusyStage('Otimizando e enviando imagem');
          const optimizedImage = await optimizeServerImage(serverImage);
          await uploadServerImage(result.server_id, optimizedImage, token);
        } catch (imageError) {
          imageWasSaved = false;
          setError('Servidor criado, mas a imagem não foi enviada: ' + (imageError as Error).message);
        }
      }
      setBusyStage('Atualizando lista');
      const refreshed = await request<{ servers: ServerInfo[] }>('/dashboard/servers', {}, token);
      setServers(refreshed.servers || []);
      setServerName(''); setSlug(''); setDescription(''); setServerImage(null);
      if (imageWasSaved) setNotice('Servidor criado em ' + result.subdomain + '. Guarde o código de ativação.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false); setBusyStage('');
    }
  }

  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setNotice('Copiado para a área de transferência.'); }
    catch { setNotice('Copie manualmente: ' + value); }
  }

  function logout() {
    setToken(''); sessionStorage.removeItem('hv_access_token');
    setView('portal'); setServers([]); setActivation('');
  }

  const playerServerName = tenantInfo?.name || tenant;
  const playerServerDescription = tenantInfo?.description || 'Conecte seu jogador Bedrock e fale com sua comunidade.';

  return <div className={'app-shell ' + (tenant ? 'is-player-site' : 'is-official-site')}>
    <div className="world-background" aria-hidden="true"><span /><span /><span /></div>
    <header className="topbar">
      <Brand onClick={() => setView('portal')} />
      <div className="top-actions">
        {tenant ? <span className="realm-chip"><i /> PORTAL DO SERVIDOR</span> :
          <span className="status-pill"><i /> MINECRAFT BEDROCK / VOICE</span>}
        {view === 'dashboard' ?
          <button className="top-link" onClick={logout}>Sair <X size={14} /></button> :
          <button className="top-link" onClick={() => { setView('auth'); setAuthMode('login'); }}>
            Painel do servidor <ArrowRight size={15} />
          </button>}
      </div>
    </header>

    {view === 'portal' && <main className={'hero-layout ' + (tenant ? 'tenant-layout' : 'home-layout')}>
      <section className="hero-copy">
        {tenant ? <>
          <div className="eyebrow"><span className="eyebrow-square" /> MUNDO BEDROCK / ÁREA DE VOZ</div>
          <div className="server-cover" aria-label={'Imagem de ' + playerServerName}>
            {tenantInfo?.image_url && <img src={tenantInfo.image_url} alt={'Capa de ' + playerServerName} loading="eager" decoding="async" />}
            <div className="cover-overlay" />
            <div className="cover-coordinates"><span>REALM ENTRY</span><b>BEDROCK EDITION</b></div>
            {!tenantInfo?.image_url && <div className="cover-fallback"><BlockMark /><span>WORLD<br />SPAWN</span></div>}
          </div>
          <div className="server-identity">
            <span className="server-kicker"><i /> {tenantLoading ? 'LOCALIZANDO SERVIDOR…' : 'SERVIDOR REGISTRADO'}</span>
            <h1>{tenantLoading ? 'Carregando mundo' : playerServerName}</h1>
            <p>{tenantLoading ? 'Buscando as informações do servidor.' : playerServerDescription}</p>
            <div className="server-address"><span>ENDEREÇO DO PORTAL</span><code>{tenant}.voice-horizon.online</code></div>
          </div>
        </> : <>
          <div className="eyebrow"><span className="eyebrow-square" /> HORIZON VOICE / MINECRAFT BEDROCK</div>
          <div className="home-title-wrap"><span className="home-stamp">BDS<br />VOICE<br />MOD</span><h1>Chega mais.<br /><em>A conversa é no jogo.</em></h1></div>
          <p className="hero-lead">Voz por proximidade e grupos para servidores Bedrock. Seu jogador continua no mundo enquanto o navegador cuida do áudio.</p>
          <div className="feature-row">
            <div><span><Radio size={18} /></span><b>Proximidade</b><small>Até onde você alcança</small></div>
            <div><span><Users size={18} /></span><b>Grupos</b><small>Na sua party</small></div>
            <div><span><ShieldCheck size={18} /></span><b>Controle</b><small>Regras do servidor</small></div>
          </div>
          <div className="trust-note"><LockKeyhole size={14} /> O microfone só é solicitado quando você ativa o áudio.</div>
        </>}
      </section>

      <section className="connect-card">
        {tenant ? <>
          <div className="card-top"><div><span className="step-label">PORTAL DO JOGADOR</span><h2>Entrar na voz</h2></div><div className="card-icon"><Headphones size={22} /></div></div>
          {tenantLoading ? <LoadingSkeleton rows={3} /> : <>
            <p className="muted">Gere um código e confirme o vínculo no chat do Minecraft. Não precisa criar uma conta.</p>
            {!pair ? <PixelButton className="primary full" disabled={busy} onClick={startPairing}>
              {busy ? 'Gerando código…' : 'Gerar código de conexão'} <ChevronRight size={17} />
            </PixelButton> : <div className="pair-panel">
              {!paired?.paired && <>
                <span className="step-label">CÓDIGO TEMPORÁRIO</span>
                <div className="pair-code">{pair.pairing_code}<button aria-label="Copiar código" onClick={() => void copy(pair.pairing_code)}><Copy size={16} /></button></div>
                <div className="command-row"><code>/horizon:voz</code><button onClick={() => void copy('/horizon:voz')}><Copy size={14} /></button></div>
                <p className="muted tiny">No Minecraft, execute o comando e escolha “Vincular navegador”. O código expira em {pair.expires_in_seconds} segundos.</p>
              </>}
              <div className={'pair-status ' + (paired?.paired ? 'success' : '')}><i />{paired?.paired ? 'Vinculado: ' + paired.player?.name : 'Aguardando confirmação no Minecraft…'}</div>
              {paired?.paired && <VoiceSession playerName={paired.player?.name || 'Jogador'} onNotice={setNotice} onError={setError} />}
              {!paired?.paired && <button className="ghost full" onClick={() => { setPair(null); setPaired(null); }}>Gerar outro código</button>}
            </div>}
            <div className="steps"><b>Dentro do jogo</b><ol>
              <li>Gere o código neste portal.</li><li>Abra o menu Horizon Voice no Minecraft.</li>
              <li>Informe o código para vincular seu jogador.</li><li>Ative o microfone e converse.</li>
            </ol></div>
          </>}
        </> : <>
          <div className="card-top"><div><span className="step-label">HORIZON VOICE</span><h2>Seu mundo, sua voz</h2></div><div className="card-icon"><Pickaxe size={22} /></div></div>
          <p className="muted">O portal do jogador fica no endereço do próprio servidor. A equipe cadastra o BDS e recebe o link para compartilhar com a comunidade.</p>
          <PixelButton className="primary full" onClick={() => { setView('auth'); setAuthMode('register'); }}>
            Cadastrar meu servidor <ChevronRight size={17} />
          </PixelButton>
          <button className="ghost full margin-top" onClick={() => { setView('auth'); setAuthMode('login'); }}>Acessar painel do proprietário</button>
          <div className="steps"><b>Como funciona</b>
            <div className="stack-line"><Wifi size={15} /> Entre no portal do seu servidor</div>
            <div className="stack-line"><Mic size={15} /> Vincule pelo comando no jogo</div>
            <div className="stack-line"><Volume2 size={15} /> Fale com quem está por perto</div>
          </div>
        </>}
      </section>
    </main>}

    {view === 'auth' && <main className="single-layout">
      <section className="connect-card auth-card">
        <div className="card-top"><div><span className="step-label">ACESSO DA EQUIPE</span><h2>{authMode === 'login' ? 'Entrar no painel' : 'Criar conta de proprietário'}</h2></div><div className="card-icon"><Server size={21} /></div></div>
        <p className="muted">Gerencie os servidores Bedrock vinculados à sua conta.</p>
        <form onSubmit={submitAuth} className="form-stack">
          <label>E-mail<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" placeholder="voce@exemplo.com" /></label>
          <label>Senha<input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={authMode === 'register' ? 12 : 1} maxLength={128} autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} placeholder={authMode === 'register' ? 'Mínimo de 12 caracteres' : 'Sua senha'} /></label>
          <PixelButton className="primary full" disabled={busy}>{busy ? 'Aguarde…' : authMode === 'login' ? 'Entrar' : 'Criar conta'} <ChevronRight size={17} /></PixelButton>
        </form>
        <button className="text-button" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
          {authMode === 'login' ? 'Ainda não tem conta? Criar conta' : 'Já possui conta? Entrar'}
        </button>
        <button className="ghost full margin-top" onClick={() => setView('portal')}>Voltar ao início</button>
      </section>
    </main>}

    {view === 'dashboard' && <main className="dashboard-layout">
      <div className="dashboard-heading">
        <div><span className="eyebrow"><span className="eyebrow-square" /> ÁREA DO PROPRIETÁRIO</span>
          <h1>Seus mundos.</h1><p className="muted">Cadastre seu servidor Bedrock, escolha uma capa e compartilhe o portal com seus jogadores.</p></div>
        <div className="dashboard-stat"><Server size={19} /><b>{servers.length}</b><small>SERVIDORES</small></div>
      </div>
      <div className="dashboard-grid">
        <section className="connect-card create-card">
          <div className="card-top"><div><span className="step-label">NOVO SERVIDOR</span><h2>Adicionar mundo</h2></div><div className="card-icon"><Pickaxe size={21} /></div></div>
          <form onSubmit={createServer} className="form-stack">
            <label>Nome do servidor<input value={serverName} onChange={e => setServerName(e.target.value)} required minLength={2} maxLength={80} placeholder="Ex.: Sobrevivência SMP" /></label>
            <label>Endereço do portal<div className="slug-input"><input value={slug} onChange={e => setSlug(e.target.value.toLowerCase())} required minLength={3} maxLength={50} pattern="[a-z0-9]+([a-z0-9-]*[a-z0-9])?" placeholder="meuservidor" /><span>.voice-horizon.online</span></div><small className="field-hint">Use letras minúsculas, números e hífen.</small></label>
            <label>Descrição do servidor<textarea value={description} onChange={e => setDescription(e.target.value)} maxLength={240} rows={3} placeholder="Conte aos jogadores um pouco sobre o seu mundo." /></label>
            <div className="upload-field">
              <div className="upload-heading"><span>ÍCONE / CAPA DO SERVIDOR</span><small>OPCIONAL · PNG, JPG OU WEBP</small></div>
              <label className="image-picker" htmlFor="server-image">
                {serverImagePreview ? <img src={serverImagePreview} alt="Prévia da imagem escolhida" /> : <span className="image-placeholder"><ImagePlus size={24} /><b>Escolher imagem</b><small>Máximo 10 MB · será otimizada ao enviar</small></span>}
                <span className="image-picker-action">{serverImagePreview ? 'Trocar imagem' : 'Selecionar arquivo'}</span>
              </label>
              <input id="server-image" className="file-input" type="file" accept="image/png,image/jpeg,image/webp" onChange={handleImageChange} />
              {serverImage && <button type="button" className="remove-image" onClick={() => setServerImage(null)}><X size={13} /> Remover imagem</button>}
            </div>
            <PixelButton className="primary full" disabled={busy}>
              {busy ? <><span className="button-spinner" /> {busyStage || 'Salvando…'}</> : 'Criar servidor'} <ChevronRight size={17} />
            </PixelButton>
          </form>
          {activation && <div className="activation">
            <span className="step-label">CÓDIGO PARA O CONSOLE DO BDS</span><code>{activation}</code>
            <p>Execute o comando abaixo no ambiente administrativo do seu mundo.</p>
            <button className="ghost full" onClick={() => void copy('/horizon:cadastrarvoice ' + activation)}><Copy size={14} /> Copiar comando de ativação</button>
          </div>}
        </section>

        <section className="connect-card server-list">
          <div className="card-top"><div><span className="step-label">SUA REDE</span><h2>Servidores cadastrados</h2></div><div className="card-icon"><Activity size={21} /></div></div>
          {serversLoading ? <LoadingSkeleton rows={4} /> :
            servers.length === 0 ? <div className="empty"><BlockMark /><b>Nenhum mundo cadastrado</b><span>Seu primeiro servidor vai aparecer aqui.</span></div> :
              <div className="server-grid">{servers.map(server => <article className="server-item" key={server.id}>
                <div className="server-thumb">
                  {server.image_url ? <img src={server.image_url} alt="" loading="lazy" decoding="async" /> : <div className="server-thumb-fallback"><BlockMark small /></div>}
                  <span className={'status-tag ' + server.status}>{formatStatus(server.status)}</span>
                </div>
                <div className="server-meta"><b>{server.name}</b><small>{server.slug}.voice-horizon.online</small><p>{server.description || 'Servidor Minecraft Bedrock'}</p></div>
                <a className="server-open" href={server.subdomain} target="_blank" rel="noreferrer">Abrir portal <ExternalLink size={13} /></a>
              </article>)}</div>}
        </section>
      </div>
    </main>}

    {(notice || error) && <div className={'toast ' + (error ? 'error' : '')} role="status" aria-live="polite">
      <span>{error || notice}</span><button aria-label="Fechar aviso" onClick={() => { setError(''); setNotice(''); }}><X size={16} /></button>
    </div>}

    <footer className="footer">
      <div className="footer-brand"><BlockMark small /><span>HORIZON VOICE<small>BY HORIZON STUDIOS</small></span></div>
      <span>Projeto independente para Minecraft Bedrock.</span>
      <span className="footer-disclaimer">Não afiliado à Mojang ou Microsoft.</span>
    </footer>
  </div>;
}
