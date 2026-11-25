# Horizon Voice BDS add-on (preview)

O pacote contém Behavior Pack e Resource Pack opcionais. Foi montado para teste em um Bedrock Dedicated Server compatível com o `@minecraft/server-net` de pré-lançamento declarado no manifesto. Não é um pacote universal para qualquer BDS estável.

## Dependências

- `@minecraft/common` 1.3.0
- `@minecraft/server` 2.11.0
- `@minecraft/server-ui` 2.3.0
- `@minecraft/server-admin` 1.0.0-beta.1.26.70-preview.26
- `@minecraft/server-net` 1.0.0-beta.1.26.70-preview.26

O `server-net` só funciona no BDS e continua em pré-lançamento. Use o BDS compatível correspondente, preserve o backup e habilite a permissão/allowlist descrita em `../docs/COMPATIBILITY.md`.

## Comandos registrados

- `/horizon:voz` — abre o menu de voz.
- `/horizon:voz mute` — desativa publicação do microfone no servidor.
- `/horizon:voz unmute` — solicita reativação, sujeita a mute administrativo.
- `/horizon:voz ajuda` — informações e comandos.
- `/horizon:voz grupos` — abre os formulários de grupo público/privado, entrada por código e saída.
- `/horizon:cadastrarvoice <codigo>` — ativa o BDS com código de uso único; requer Admin.

O Script API Command Registry usa nome namespaced. Os aliases sem namespace `/voz` e `/cadastrarvoice` não são declarados.

## Integração

- Usa `Player.id` como identidade de sessão do BDS, sem alegar que seja XUID persistente.
- Guarda a server key como dynamic property do mundo.
- Envia lotes de posições aproximadamente a cada segundo quando há movimento/alteração, com heartbeat e retry exponencial.
- Informa a saída de uma entidade para a API e remove a presença/participante LiveKit associado.
- Atualiza o `Entity.nameTag` sem alterar a lista de jogadores: `[LINK]`, `[FALANDO]`, `[MUDO]`.
- Não implementa botão clicável do HUD; `/horizon:voz` é o fallback.
- O portal solicita microfone e áudio após ação do usuário. A voz WebRTC passa pelo LiveKit; a API decide inscrições por posição, dimensão, mute, deafen e grupo ativo.

## Instalação

Siga `../docs/INSTALLATION.md`. A API/LiveKit precisam estar em execução antes de ativar o add-on. O endereço central atualmente está configurado no arquivo `behavior_pack/scripts/network.js` como `https://voice-horizon.online/api/v1`.
