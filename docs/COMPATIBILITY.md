# Compatibilidade e restrições externas

## Minecraft Bedrock Dedicated Server

| Componente | Versão declarada no manifesto | Situação |
|---|---:|---|
| `@minecraft/common` | `1.3.0` | Dependência declarada |
| `@minecraft/server` | `2.11.0` | API estável declarada; confirmar no BDS instalado |
| `@minecraft/server-ui` | `2.3.0` | API de forms declarada; confirmar no BDS instalado |
| `@minecraft/server-admin` | `1.0.0-beta.1.26.70-preview.26` | Pré-lançamento / peer dependency do server-net |
| `@minecraft/server-net` | `1.0.0-beta.1.26.70-preview.26` | Pré-lançamento, exclusivo de BDS |

A documentação Microsoft informa que `@minecraft/server-net` só funciona no Bedrock Dedicated Server, não no cliente nem no Realms, e continua em pré-lançamento. A versão declarada corresponde à versão de documentação `1.26.70-preview.26`; use o BDS compatível correspondente. Isso não significa que toda versão estável ou futura do BDS seja compatível.

Referências: [server-net module](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server-net/minecraft-server-net?view=minecraft-bedrock-experimental), [server-admin module](https://learn.microsoft.com/en-us/minecraft/creator/scriptapi/minecraft/server-admin/minecraft-server-admin), [Scripting BDS permissions](https://learn.microsoft.com/en-us/minecraft/creator/documents/scriptingservers), [server-net HTTP permissions](https://learn.microsoft.com/en-us/minecraft/creator/documents/update1.26.10?view=minecraft-bedrock-stable).

### Permissão de rede necessária

O arquivo `config/default/permissions.json` do BDS precisa autorizar `@minecraft/server-net` e limitar os destinos HTTP. Exemplo de configuração (mantenha os demais módulos já existentes na sua instalação):

```json
{
  "allowed_modules": [
    "@minecraft/server-gametest",
    "@minecraft/server",
    "@minecraft/server-ui",
    "@minecraft/server-admin",
    "@minecraft/server-editor",
    "@minecraft/server-net"
  ],
  "module_permissions": {
    "@minecraft/server-net": {
      "allowed_uris": ["https://voice-horizon.online/"],
      "force_https": true,
      "max_body_bytes": 262144,
      "max_concurrent_requests": 4
    }
  }
}
```

Faça backup do arquivo original antes de alterar. A configuração acima libera somente HTTPS para o host definido; ao usar outro domínio, altere o código-fonte do add-on e a allowlist, reempacote e teste novamente.

### Comandos

Os comandos de Script API neste projeto são namespaced:

- `/horizon:voz`
- `/horizon:voz mute`
- `/horizon:voz unmute`
- `/horizon:voz ajuda`
- `/horizon:cadastrarvoice <codigo>`

Não afirmamos que o código registra o alias literal `/voz` ou `/cadastrarvoice`. A implementação usa o namespace `horizon` para evitar interceptar o chat.

### HUD e nome do jogador

O projeto altera apenas o `Entity.nameTag` para mostrar `[LINK]`, `[FALANDO]` ou `[MUDO]`. A lista de jogadores é uma interface diferente. O botão de HUD clicável não está incluído; o comando `/horizon:voz` é o fallback funcional. Os indicadores não devem sobrescrever permanentemente mudanças de prefixos aplicadas por outros add-ons.

### Identidade do jogador

A integração usa `Player.id` como chave de identidade da sessão atual do BDS. Não é XUID, Xbox account ID nem identidade persistente. Quando a entidade sai, o add-on envia um evento de saída e o pareamento deixa de estar ativo. Ao entrar novamente com um `Player.id` novo, o jogador deve parear de novo.

## Navegador

O portal exige HTTPS para acesso ao microfone em contextos não locais. Suporta navegadores atuais com WebRTC e `getUserMedia`. Seleção de dispositivo de saída depende de `HTMLMediaElement.setSinkId`, que não existe em todos os browsers.

## Backend

- Python 3.12+
- FastAPI, Pydantic 2, SQLAlchemy 2 e Alembic
- PostgreSQL em produção; SQLite apenas para testes/desenvolvimento
- Argon2 para hash de senhas de grupo/contas
- LiveKit Server e SDK Python `livekit-api`

## Voz

O áudio passa pelo LiveKit SFU. A API emite tokens curtos, restringe a publicação a microfone e mantém `autoSubscribe` desativado no browser. A API aplica subscriptions seletivas usando posições BDS, dimensão, mutes e canal de grupo. Essa implementação foi validada por testes unitários/lógicos e revisão de API documentada, mas ainda não passou por teste real de duas ou mais sessões no seu domínio e no BDS de destino.
