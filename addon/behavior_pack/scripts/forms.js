import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import { HttpRequestMethod } from "@minecraft/server-net";
import { apiRequest, getServerSecret, saveServerSecret } from "./network.js";

function tell(player, message) {
  try { player.sendMessage(`§8[§bHorizon Voice§8] §r${message}`); } catch { /* Player may have left. */ }
}

export function showHelp(player) {
  tell(player, "Use /horizon:voz para abrir o menu, /horizon:voz grupos para gerenciar grupos e /horizon:voz mute|unmute para o microfone.");
  tell(player, "O comando exige namespace porque comandos customizados da Script API precisam dele.");
}

export async function activateServer(world, player, code) {
  try {
    const result = await apiRequest("/registration/activate", { body: { code: String(code).trim().toUpperCase() } });
    saveServerSecret(world, result.server_secret);
    tell(player, `Servidor ${result.server_name} ativado. Credencial armazenada no estado persistente do mundo.`);
  } catch (error) {
    tell(player, `Não foi possível ativar: ${error.message}`);
  }
}

export async function pairPlayer(world, player, code) {
  const secret = getServerSecret(world);
  if (!secret) {
    tell(player, "Este BDS ainda não foi ativado. Um administrador deve usar /horizon:cadastrarvoice <código>.");
    return;
  }
  const location = player.location;
  try {
    await apiRequest("/pairing/claim", {
      serverSecret: secret,
      body: {
        code: String(code).trim(),
        identity_key: player.id,
        display_name: player.name,
        dimension: player.dimension.id,
        x: location.x,
        y: location.y,
        z: location.z
      }
    });
    tell(player, "Navegador vinculado. Abra o portal, permita o microfone e clique em “Ativar áudio e microfone” para entrar na conversa.");
  } catch (error) {
    tell(player, `Falha no pareamento: ${error.message}`);
  }
}

export function showPairForm(world, player) {
  new ModalFormData()
    .title("Horizon Voice")
    .textField("Código de 6 dígitos exibido no site", "000000", "")
    .show(player)
    .then(result => {
      if (result.canceled) return;
      const code = String(result.formValues?.[0] ?? "").replace(/\D/g, "").slice(0, 6);
      if (code.length !== 6) {
        tell(player, "Digite os 6 números do código de pareamento.");
        return;
      }
      void pairPlayer(world, player, code);
    })
    .catch(() => tell(player, "Não foi possível abrir o formulário. Tente novamente."));
}

async function groupRequest(world, player, path, body, method = HttpRequestMethod.Post) {
  const secret = getServerSecret(world);
  if (!secret) throw new Error("Este BDS ainda não foi ativado.");
  return apiRequest(`/players/groups${path}`, {
    method,
    serverSecret: secret,
    body: method === HttpRequestMethod.Get ? undefined : { identity_key: player.id, ...(body || {}) }
  });
}

export async function showGroupMenu(world, player) {
  try {
    const result = await groupRequest(world, player, `?identity_key=${encodeURIComponent(player.id)}`, undefined, HttpRequestMethod.Get);
    const groups = Array.isArray(result.groups) ? result.groups : [];
    const active = groups.find(group => group.id === result.active_group_id);
    const form = new ActionFormData()
      .title("Horizon Voice • Grupos")
      .body(active
        ? `Grupo ativo: ${active.name}\nCódigo: ${active.code}\n\nSua voz está somente neste grupo. A proximidade está pausada.`
        : "Crie um grupo, entre usando um código ou escolha um grupo público. Ao entrar, a proximidade fica pausada.");
    form.button("Criar grupo");
    form.button("Entrar com código");
    if (active) form.button("Sair do grupo");
    for (const group of groups.filter(item => !item.is_private && item.id !== result.active_group_id).slice(0, 8)) {
      form.button(`Entrar: ${group.name} (${group.members}/${group.max_members})`);
    }
    form.button("Voltar");
    const response = await form.show(player);
    if (response.canceled) return;
    const selection = response.selection ?? -1;
    if (selection === 0) {
      const create = await new ModalFormData()
        .title("Criar grupo de voz")
        .textField("Nome do grupo", "Meu grupo", "")
        .dropdown("Visibilidade", ["Público", "Privado"], 0)
        .textField("Senha (obrigatória para privado)", "Mínimo 8 caracteres", "")
        .show(player);
      if (create.canceled) return showGroupMenu(world, player);
      const [name, visibility, password] = create.formValues || [];
      const isPrivate = Number(visibility) === 1;
      await groupRequest(world, player, "/create", {
        name: String(name || "").trim(), is_private: isPrivate,
        password: String(password || "") || null, max_members: 8
      });
      tell(player, "Grupo criado. Compartilhe o código exibido no menu com quem deseja convidar.");
      return showGroupMenu(world, player);
    }
    if (selection === 1) {
      const join = await new ModalFormData()
        .title("Entrar em grupo")
        .textField("Código do grupo", "ABCDEFGH", "")
        .textField("Senha (se privado)", "Senha do grupo", "")
        .show(player);
      if (join.canceled) return showGroupMenu(world, player);
      const [code, password] = join.formValues || [];
      await groupRequest(world, player, "/join", { code: String(code || "").trim().toUpperCase(), password: String(password || "") || null });
      tell(player, "Você entrou no grupo. A proximidade foi pausada.");
      return showGroupMenu(world, player);
    }
    if (active && selection === 2) {
      await groupRequest(world, player, "/leave", {});
      tell(player, "Você saiu do grupo e voltou ao modo de proximidade.");
      return showGroupMenu(world, player);
    }
    const publicStart = active ? 3 : 2;
    const publicGroups = groups.filter(item => !item.is_private && item.id !== result.active_group_id).slice(0, 8);
    const publicIndex = selection - publicStart;
    if (publicIndex >= 0 && publicIndex < publicGroups.length) {
      await groupRequest(world, player, "/join", { code: publicGroups[publicIndex].code, password: null });
      tell(player, `Você entrou em ${publicGroups[publicIndex].name}. A proximidade foi pausada.`);
      return showGroupMenu(world, player);
    }
  } catch (error) {
    tell(player, `Não foi possível gerenciar grupos: ${error.message}`);
  }
}

export function showVoiceMenu(world, player) {
  new ActionFormData()
    .title("Horizon Voice")
    .body("Vincule seu navegador para conversar por proximidade ou grupos. Depois, abra o portal e ative o microfone e o áudio recebido.")
    .button("Vincular navegador")
    .button("Grupos de voz")
    .button("Ajuda e comandos")
    .show(player)
    .then(result => {
      if (result.canceled) return;
      if (result.selection === 0) showPairForm(world, player);
      else if (result.selection === 1) void showGroupMenu(world, player);
      else showHelp(player);
    })
    .catch(() => tell(player, "Não foi possível abrir o menu. Tente novamente."));
}

export async function toggleServerMute(world, player, muted) {
  const secret = getServerSecret(world);
  if (!secret) return tell(player, "O servidor ainda não foi ativado.");
  try {
    await apiRequest("/players/self-mute", {
      serverSecret: secret,
      body: { identity_key: player.id, muted }
    });
    tell(player, muted ? "Microfone mutado." : "Microfone ativado.");
  } catch (error) {
    tell(player, `Não foi possível alterar o microfone: ${error.message}`);
  }
}
