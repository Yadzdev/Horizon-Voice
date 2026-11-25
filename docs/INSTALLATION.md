# Instalação do add-on BDS (preview)

## Requisitos

- Bedrock Dedicated Server compatível com as versões `@minecraft/server-net` e `@minecraft/server-admin` do manifesto.
- A versão do módulo `server-net` está em pré-lançamento; use BDS preview compatível e mundo de teste com backup.
- Saída HTTPS do BDS liberada para `voice-horizon.online`.
- Permissão `@minecraft/server-net` habilitada em `config/default/permissions.json`, com allowlist de URI conforme [COMPATIBILITY.md](COMPATIBILITY.md).
- Plataforma web/API/LiveKit já publicada na VPS antes de ativar o add-on.

## Importar

1. Baixe `HorizonVoice-BDS-PREVIEW.mcaddon` da página Releases ou gere localmente com `python scripts/package_addon.py`.
2. Importe o `.mcaddon` no ambiente de teste ou copie os packs para as pastas Behavior Packs e Resource Packs do BDS.
3. Ative o Behavior Pack e o Resource Pack no mundo.
4. Confirme que a dependência Script API está instalada e que não há erro de manifesto no content log.
5. Reinicie o BDS.

## Registrar o servidor

1. Crie uma conta no portal e registre um servidor.
2. Copie o código de ativação, válido por 15 minutos.
3. No console administrativo do BDS, execute `/horizon:cadastrarvoice <codigo>`.
4. A API devolve a credencial do servidor uma vez; o add-on grava em dynamic property do mundo.
5. Não divulgue nem cole a credencial em chat, Issue ou screenshot.

## Parear jogador

1. Abra `https://<slug>.voice-horizon.online`.
2. Clique em gerar código de conexão.
3. No Bedrock, execute `/horizon:voz` e escolha “Vincular navegador”.
4. Informe o código de seis dígitos exibido no portal.
5. Quando o jogador estiver pareado, clique em “Ativar áudio e microfone” no portal e permita o uso do microfone.
6. Se o jogador sair e voltar com outro ID de entidade, gere outro código e faça novo pareamento.

## Comandos

- `/horizon:voz` — abre o menu.
- `/horizon:voz mute` — muta seu microfone.
- `/horizon:voz unmute` — ativa seu microfone, salvo mute administrativo.
- `/horizon:voz grupos` — abre formulários para criar grupo público/privado, entrar por código ou sair do grupo.
- `/horizon:voz ajuda` — mostra ajuda.
- `/horizon:cadastrarvoice <codigo>` — ativa o servidor (nível Admin).

## Atualização

Faça backup do mundo. Substitua os packs e reinicie o BDS seguindo as regras da versão Minecraft instalada. Não assuma compatibilidade retroativa; valide manifests e módulos. A atualização automática de scripts a partir de URLs arbitrárias não é executada.
