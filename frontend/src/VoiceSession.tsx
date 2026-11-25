import { useCallback, useEffect, useRef, useState } from 'react';
import { ConnectionState, Room, RoomEvent, Track } from 'livekit-client';
import {
  Headphones, Mic, MicOff, Radio, Users, Volume2, VolumeX, Wifi, WifiOff,
} from 'lucide-react';
import { post, request } from './api';

type NearbyPlayer = {
  id: string;
  name: string;
  connected: boolean;
  speaking: boolean;
  muted: boolean;
  locally_muted: boolean;
  distance: number | null;
  same_dimension: boolean;
  in_group: boolean;
  can_hear: boolean;
};
type GroupInfo = {
  id: string;
  name: string;
  code: string;
  members: number;
  joined: boolean;
  active: boolean;
  is_private: boolean;
  is_owner: boolean;
  max_members: number;
};
type VoiceToken = {
  server_url: string;
  token: string;
  player_name: string;
  muted: boolean;
  deafened: boolean;
  expires_in_minutes: number;
};
type NearbyResponse = {
  players: NearbyPlayer[];
  deafened: boolean;
  active_group_id: string | null;
  max_distance: number;
};
type SinkCapableAudio = HTMLAudioElement & {
  setSinkId?: (deviceId: string) => Promise<void>;
};
type Props = {
  playerName: string;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
};

export default function VoiceSession({ playerName, onNotice, onError }: Props) {
  const roomRef = useRef<Room | null>(null);
  const audioElements = useRef<Map<string, HTMLAudioElement>>(new Map());
  const lastSpeaking = useRef(false);
  const refreshTimer = useRef<number | null>(null);
  const renewTimer = useRef<number | null>(null);
  const manuallyDisconnected = useRef(false);

  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'reconnecting'>('disconnected');
  const [muted, setMuted] = useState(false);
  const [deafened, setDeafened] = useState(false);
  const [nearby, setNearby] = useState<NearbyPlayer[]>([]);
  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [activeGroup, setActiveGroup] = useState('');
  const [maxDistance, setMaxDistance] = useState(30);
  const [groupName, setGroupName] = useState('');
  const [groupPassword, setGroupPassword] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [joinPassword, setJoinPassword] = useState('');
  const [privateGroup, setPrivateGroup] = useState(false);
  const [groupCode, setGroupCode] = useState('');
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [outputDevices, setOutputDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedMic, setSelectedMic] = useState('');
  const [selectedOutput, setSelectedOutput] = useState('');
  const [connectionQuality, setConnectionQuality] = useState('Aguardando conexão');
  const [audioUnlockNeeded, setAudioUnlockNeeded] = useState(false);

  const loadDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const all = await navigator.mediaDevices.enumerateDevices();
    const microphones = all.filter(device => device.kind === 'audioinput');
    const outputs = all.filter(device => device.kind === 'audiooutput');
    setDevices(microphones);
    setOutputDevices(outputs);
    setSelectedMic(current => current || microphones[0]?.deviceId || '');
    setSelectedOutput(current => current || outputs[0]?.deviceId || '');
  }, []);

  const refreshState = useCallback(async () => {
    try {
      const [nearbyResult, groupsResult] = await Promise.all([
        request<NearbyResponse>('/voice/nearby'),
        request<{ groups: GroupInfo[] }>('/groups'),
      ]);
      setNearby(nearbyResult.players);
      setDeafened(nearbyResult.deafened);
      setActiveGroup(nearbyResult.active_group_id || '');
      setMaxDistance(nearbyResult.max_distance || 30);
      setGroups(groupsResult.groups);
      const currentGroup = groupsResult.groups.find(group => group.id === nearbyResult.active_group_id);
      setGroupCode(currentGroup?.code || '');
      for (const player of nearbyResult.players) {
        const audio = audioElements.current.get(player.id);
        if (!audio) continue;
        audio.muted = nearbyResult.deafened || player.locally_muted;
        audio.volume = player.in_group ? 1 : attenuation(player.distance, nearbyResult.max_distance || 30);
      }
    } catch (error) {
      onError((error as Error).message);
    }
  }, [onError]);

  const refreshServerSubscriptions = useCallback(async () => {
    try {
      await post('/voice/refresh');
    } catch {
      // The next five-second heartbeat retries reconciliation.
    }
  }, []);

  const attachRemoteAudio = useCallback((track: { attach: () => HTMLMediaElement }, identity: string) => {
    const element = track.attach();
    if (!(element instanceof HTMLAudioElement)) return;
    element.autoplay = true;
    element.dataset.playerIdentity = identity;
    element.muted = deafened;
    const player = nearby.find(item => item.id === identity);
    element.volume = player?.in_group ? 1 : attenuation(player?.distance ?? null, maxDistance);
    if (selectedOutput && typeof (element as SinkCapableAudio).setSinkId === 'function') {
      void (element as SinkCapableAudio).setSinkId(selectedOutput).catch(() => undefined);
    }
    audioElements.current.set(identity, element);
    document.getElementById('horizon-audio-output')?.appendChild(element);
    void element.play().then(() => setAudioUnlockNeeded(false)).catch(() => {
      setAudioUnlockNeeded(true);
      setConnectionQuality('O navegador bloqueou a reprodução. Ative o áudio no botão abaixo.');
    });
  }, [deafened, maxDistance, nearby, selectedOutput]);

  const connect = useCallback(async () => {
    if (roomRef.current && roomRef.current.state !== ConnectionState.Disconnected) return;
    manuallyDisconnected.current = false;
    setStatus('connecting');
    setConnectionQuality('Conectando ao servidor de voz…');

    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;
    // Start the browser audio unlock directly from the player's click, before
    // awaiting the network. Some browsers otherwise block remote playback.
    const audioUnlock = room.startAudio().catch(() => undefined);

    try {
      const access = await post<VoiceToken>('/voice/token');
      room.on(RoomEvent.ConnectionStateChanged, state => {
        if (state === ConnectionState.Connected) {
          setStatus('connected');
          setConnectionQuality('Conectado ao servidor de mídia');
        } else if (state === ConnectionState.Reconnecting) {
          setStatus('reconnecting');
          setConnectionQuality('Reconectando…');
        } else if (state === ConnectionState.Disconnected) {
          setStatus('disconnected');
        }
      });
      room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
        if (track.kind === Track.Kind.Audio) attachRemoteAudio(track, participant.identity);
      });
      room.on(RoomEvent.TrackUnsubscribed, (track, _publication, participant) => {
        if (track.kind !== Track.Kind.Audio) return;
        track.detach().forEach(element => element.remove());
        audioElements.current.delete(participant.identity);
      });
      const refresh = () => {
        void refreshServerSubscriptions();
      };
      room.on(RoomEvent.ParticipantConnected, refresh);
      room.on(RoomEvent.ParticipantDisconnected, refresh);
      room.on(RoomEvent.TrackPublished, refresh);
      room.on(RoomEvent.TrackUnpublished, refresh);
      room.on(RoomEvent.ActiveSpeakersChanged, speakers => {
        const speaking = speakers.some(participant => participant.identity === room.localParticipant.identity);
        if (speaking !== lastSpeaking.current) {
          lastSpeaking.current = speaking;
          void post('/voice/speaking', { speaking }).catch(() => undefined);
        }
      });
      room.on(RoomEvent.Disconnected, () => {
        setStatus('disconnected');
        setConnectionQuality('Desconectado do servidor de voz');
        for (const element of audioElements.current.values()) element.remove();
        audioElements.current.clear();
      });

      await room.connect(access.server_url, access.token, { autoSubscribe: false });
      await audioUnlock;
      try {
        await room.startAudio();
        setAudioUnlockNeeded(false);
      } catch {
        setAudioUnlockNeeded(true);
        setConnectionQuality('Conectado. Clique em Ativar áudio para liberar a reprodução.');
      }
      if (!access.muted) {
        try {
          await room.localParticipant.setMicrophoneEnabled(true);
        } catch {
          setConnectionQuality('Conectado para ouvir. Permita o acesso ao microfone para falar.');
        }
      }
      setMuted(access.muted);
      setDeafened(access.deafened);
      await refreshServerSubscriptions();
      await refreshState();
      await loadDevices();
      setStatus('connected');
      setConnectionQuality(`Conectado • renovação automática em ${Math.max(1, access.expires_in_minutes - 2)} min`);

      if (refreshTimer.current !== null) window.clearInterval(refreshTimer.current);
      refreshTimer.current = window.setInterval(() => {
        void refreshServerSubscriptions();
        void refreshState();
      }, 5000);
      if (renewTimer.current !== null) window.clearTimeout(renewTimer.current);
      const renewalDelay = Math.max(1, access.expires_in_minutes - 2) * 60 * 1000;
      renewTimer.current = window.setTimeout(() => {
        if (manuallyDisconnected.current) return;
        setStatus('reconnecting');
        setConnectionQuality('Renovando a autorização de áudio…');
        room.disconnect();
        if (roomRef.current === room) roomRef.current = null;
        for (const element of audioElements.current.values()) element.remove();
        audioElements.current.clear();
        void connect();
      }, renewalDelay);
    } catch (error) {
      room.disconnect();
      if (roomRef.current === room) roomRef.current = null;
      setStatus('disconnected');
      const message = (error as Error).message || 'Não foi possível conectar ao áudio.';
      setConnectionQuality(message);
      onError(message);
    }
  }, [attachRemoteAudio, loadDevices, onError, refreshServerSubscriptions, refreshState]);

  const disconnect = useCallback(() => {
    manuallyDisconnected.current = true;
    if (refreshTimer.current !== null) window.clearInterval(refreshTimer.current);
    if (renewTimer.current !== null) window.clearTimeout(renewTimer.current);
    refreshTimer.current = null;
    renewTimer.current = null;
    if (lastSpeaking.current) {
      lastSpeaking.current = false;
      void post('/voice/speaking', { speaking: false }).catch(() => undefined);
    }
    roomRef.current?.disconnect();
    roomRef.current = null;
    for (const element of audioElements.current.values()) element.remove();
    audioElements.current.clear();
    setStatus('disconnected');
    setConnectionQuality('Você desconectou do áudio');
  }, []);

  useEffect(() => () => {
    manuallyDisconnected.current = true;
    if (refreshTimer.current !== null) window.clearInterval(refreshTimer.current);
    if (renewTimer.current !== null) window.clearTimeout(renewTimer.current);
    roomRef.current?.disconnect();
    for (const element of audioElements.current.values()) element.remove();
    audioElements.current.clear();
  }, []);

  async function unlockAudioPlayback() {
    try {
      await roomRef.current?.startAudio();
      await Promise.all([...audioElements.current.values()].map(element => element.play()));
      setAudioUnlockNeeded(false);
      setConnectionQuality('Reprodução de áudio liberada.');
    } catch (error) {
      onError(`Não foi possível ativar o áudio: ${(error as Error).message}`);
    }
  }



  async function toggleMute() {
    const next = !muted;
    try {
      const result = await post<{ muted: boolean }>('/voice/self-mute', { muted: next });
      setMuted(result.muted);
      if (next) await roomRef.current?.localParticipant.setMicrophoneEnabled(false);
      else if (roomRef.current && !result.muted) await roomRef.current.localParticipant.setMicrophoneEnabled(true);
      onNotice(next ? 'Microfone mutado pelo servidor.' : (result.muted ? 'O servidor ainda mantém uma moderação de mute.' : 'Microfone ativado.'));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function toggleDeafen() {
    const next = !deafened;
    try {
      const result = await post<{ deafened: boolean }>('/voice/deafen', { deafened: next });
      setDeafened(result.deafened);
      for (const element of audioElements.current.values()) element.muted = result.deafened;
      onNotice(next ? 'Áudio recebido silenciado.' : 'Áudio recebido ativado.');
      await refreshServerSubscriptions();
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function toggleLocalMute(player: NearbyPlayer) {
    try {
      await post(`/voice/local-mute/${player.id}`, { muted: !player.locally_muted });
      await refreshState();
      await refreshServerSubscriptions();
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function changeMicrophone(deviceId: string) {
    setSelectedMic(deviceId);
    if (!roomRef.current || !deviceId) return;
    try {
      await roomRef.current.switchActiveDevice('audioinput', deviceId);
      onNotice('Microfone alterado.');
    } catch (error) {
      onError(`Não foi possível trocar o microfone: ${(error as Error).message}`);
    }
  }

  async function changeOutput(deviceId: string) {
    setSelectedOutput(deviceId);
    const targets = [...audioElements.current.values()] as SinkCapableAudio[];
    if (!targets.length) return;
    if (targets.some(element => typeof element.setSinkId !== 'function')) {
      onNotice('Este navegador não permite escolher a saída de áudio. O dispositivo padrão será usado.');
      return;
    }
    try {
      await Promise.all(targets.map(element => element.setSinkId!(deviceId)));
      onNotice('Saída de áudio alterada.');
    } catch (error) {
      onError(`Não foi possível trocar a saída de áudio: ${(error as Error).message}`);
    }
  }

  async function createGroup(event: React.FormEvent) {
    event.preventDefault();
    try {
      const result = await post<{ code: string; name: string }>('/groups', {
        name: groupName,
        is_private: privateGroup,
        password: privateGroup ? groupPassword : null,
        max_members: 8,
      });
      setGroupCode(result.code);
      setGroupName('');
      setGroupPassword('');
      await refreshState();
      await refreshServerSubscriptions();
      onNotice('Grupo criado. Você está no modo de voz do grupo.');
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function joinGroup(event: React.FormEvent) {
    event.preventDefault();
    try {
      const invitationCode = joinCode.trim().toUpperCase();
      await post('/groups/join', { code: invitationCode, password: joinPassword || null });
      setGroupCode(invitationCode);
      setJoinCode('');
      setJoinPassword('');
      await refreshState();
      await refreshServerSubscriptions();
      onNotice('Você entrou no grupo. A proximidade foi pausada enquanto estiver nele.');
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function leaveGroup() {
    try {
      await post('/groups/leave');
      setGroupCode('');
      await refreshState();
      await refreshServerSubscriptions();
      onNotice('Você voltou ao modo de proximidade.');
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function deleteGroup(group: GroupInfo) {
    if (!window.confirm(`Excluir o grupo ${group.name}? Todos os membros voltarão à proximidade.`)) return;
    try {
      await request(`/groups/${group.id}`, { method: 'DELETE' });
      setGroupCode('');
      await refreshState();
      await refreshServerSubscriptions();
      onNotice('Grupo excluído. Os membros voltaram à proximidade.');
    } catch (error) {
      onError((error as Error).message);
    }
  }

  return <section className="voice-session-card">
    <div className="voice-session-header">
      <div>
        <span className="step-label">SESSÃO DE VOZ</span>
        <h3>{playerName}</h3>
        <p className="muted">O navegador transmite seu microfone ao servidor de mídia; o servidor decide quem pode ouvir.</p>
      </div>
      <span className={`voice-connection ${status}`}><i/>{status === 'connected' ? 'CONECTADO' : status === 'connecting' ? 'CONECTANDO' : status === 'reconnecting' ? 'RECONEXÃO' : 'OFFLINE'}</span>
    </div>

    <div className="voice-primary-controls">
      {status === 'connected' ? <>
        {audioUnlockNeeded && <button className="primary full" onClick={() => void unlockAudioPlayback()}><Volume2 size={17}/>Ativar áudio recebido</button>}
        <button className={`voice-action ${muted ? 'off' : ''}`} onClick={() => void toggleMute()}><span>{muted ? <MicOff/> : <Mic/>}</span>{muted ? 'Ativar microfone' : 'Mutar microfone'}</button>
        <button className={`voice-action ${deafened ? 'off' : ''}`} onClick={() => void toggleDeafen()}><span>{deafened ? <VolumeX/> : <Volume2/>}</span>{deafened ? 'Ouvir jogadores' : 'Deafen'}</button>
        <button className="voice-action danger" onClick={disconnect}><span><WifiOff/></span>Desconectar</button>
      </> : <button className="primary full" disabled={status === 'connecting'} onClick={() => void connect()}><Headphones size={17}/>{status === 'connecting' ? 'Conectando…' : 'Ativar áudio e microfone'}</button>}
    </div>

    <div className="voice-connection-note"><Wifi size={14}/>{connectionQuality}</div>

    {status === 'connected' && <>
      <div className="voice-settings">
        <label>Microfone
          <select value={selectedMic} onChange={event => void changeMicrophone(event.target.value)}>
            <option value="">Padrão do navegador</option>
            {devices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Microfone ${device.deviceId.slice(0, 6)}`}</option>)}
          </select>
        </label>
        <label>Saída de áudio
          <select value={selectedOutput} onChange={event => void changeOutput(event.target.value)}>
            <option value="">Padrão do navegador</option>
            {outputDevices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Saída ${device.deviceId.slice(0, 6)}`}</option>)}
          </select>
        </label>
      </div>

      <div className="voice-section-heading"><span><Users size={15}/> Jogadores próximos</span><small>{nearby.length} online • {maxDistance} blocos</small></div>
      <div className="nearby-list">
        {nearby.length === 0 ? <p className="muted">Nenhum outro jogador online no momento.</p> : nearby.map(player => <div className="nearby-player" key={player.id}>
          <span className={`player-state ${player.speaking ? 'speaking' : player.connected ? 'connected' : ''}`}/>
          <span className="nearby-player-info"><b>{player.name}</b><small>{player.in_group ? 'Mesmo grupo' : player.same_dimension ? (player.distance === null ? 'Distância indisponível' : `${player.distance.toFixed(1)} blocos`) : 'Outra dimensão'}{player.speaking ? ' • falando' : player.muted ? ' • mutado' : ''}{!player.connected ? ' • sem voz' : ''}</small></span>
          <button className={`local-mute ${player.locally_muted ? 'active' : ''}`} title={player.locally_muted ? 'Desmutar localmente' : 'Mutar somente para você'} onClick={() => void toggleLocalMute(player)}>{player.locally_muted ? <VolumeX size={15}/> : <Volume2 size={15}/>}</button>
        </div>)}
      </div>

      <div className="voice-section-heading"><span><Radio size={15}/> Grupos de voz</span><small>{activeGroup ? 'MODO DE GRUPO' : 'MODO PROXIMIDADE'}</small></div>
      {activeGroup ? <div className="active-group-box"><b>Grupo: {groups.find(group => group.id === activeGroup)?.name || 'Grupo ativo'}</b><small>Somente participantes no mesmo grupo recebem sua voz. A proximidade está pausada.</small>{groupCode && <div className="group-code-result">Código para convidar: <b>{groupCode}</b><button className="text-button" onClick={() => { void navigator.clipboard?.writeText(groupCode).then(() => onNotice('Código do grupo copiado.')).catch(() => onNotice(`Copie o código: ${groupCode}`)); }}>Copiar</button></div>}<button className="ghost full" onClick={() => void leaveGroup()}>Sair do grupo e voltar à proximidade</button>{groups.find(group => group.id === activeGroup)?.is_owner && <button className="disconnect full" onClick={() => void deleteGroup(groups.find(group => group.id === activeGroup)!)}>Excluir grupo</button>}</div> : <>
        <form className="group-form" onSubmit={createGroup}>
          <input value={groupName} onChange={event => setGroupName(event.target.value)} minLength={2} maxLength={48} required placeholder="Nome do novo grupo"/>
          <label className="inline-check"><input type="checkbox" checked={privateGroup} onChange={event => setPrivateGroup(event.target.checked)}/> Privado</label>
          {privateGroup && <input type="password" value={groupPassword} onChange={event => setGroupPassword(event.target.value)} minLength={8} maxLength={128} required placeholder="Senha (mínimo 8 caracteres)"/>}
          <button className="ghost" type="submit">Criar grupo</button>
        </form>
        {groupCode && <div className="group-code-result">Código de convite: <b>{groupCode}</b></div>}
        <form className="group-form join" onSubmit={joinGroup}>
          <input value={joinCode} onChange={event => setJoinCode(event.target.value)} minLength={6} maxLength={12} required placeholder="Código do grupo"/>
          <input type="password" value={joinPassword} onChange={event => setJoinPassword(event.target.value)} placeholder="Senha (se privado)"/>
          <button className="ghost" type="submit">Entrar</button>
        </form>
        {groups.map(group => <div className="group-list-item" key={group.id}><span><b>{group.name}</b><small>{group.members} membro(s) • {group.code}</small></span>{group.joined ? <small>Você é membro</small> : <button className="text-button" onClick={() => setJoinCode(group.code)}>Usar código</button>}</div>)}
      </>}
    </>}
    <div id="horizon-audio-output" className="audio-output" aria-hidden="true"/>
  </section>;
}

function attenuation(distance: number | null, maximum: number): number {
  if (distance === null || distance <= 5) return 1;
  if (distance <= 10) return 0.8;
  if (distance <= 20) return 0.55;
  if (distance <= maximum) return 0.25;
  return 0;
}
