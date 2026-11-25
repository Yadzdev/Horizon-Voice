# Solução de problemas

## Add-on não carrega módulo

Confirme se o BDS está na versão compatível com `@minecraft/server-net` do manifesto. O módulo está em pré-lançamento e é somente BDS. Confira `config/default/permissions.json`, `allowed_modules`, `module_permissions.@minecraft/server-net.allowed_uris`, o content log e as dependências do pack.

## Comando desconhecido

Ative o Behavior Pack, reinicie o BDS e confirme suporte ao Custom Command Registry. Os nomes registrados são `/horizon:voz` e `/horizon:cadastrarvoice`; os aliases sem namespace não estão registrados.

## Ativação falha

Confirme saída HTTPS para `voice-horizon.online`, código ainda válido (15 min), server key ausente/inválida e API `/api/v1/health` saudável. Não edite manualmente a dynamic property que guarda a chave.

## Portal não encontra tenant

Confirme que o servidor está ativo, o slug está correto, o DNS wildcard aponta para a VPS, o certificado contém o wildcard e a requisição preserva `Host`/`X-Tenant-Slug`.

## Pareamento falha

Use código criado pelo mesmo subdomínio, informe antes de expirar e confira server key/clock do BDS. O código é single-use. Se o jogador saiu, gere um novo código e faça novo pareamento.

## Token de voz retorna 503

Confira `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_PUBLIC_URL`, URL interna do LiveKit, logs da API e conexão API→LiveKit. Se o LiveKit não estiver configurado, a API falha fechada em vez de emitir um token sem controle.

## Microfone não ativa

Confirme HTTPS, permissão do site, dispositivo de entrada, microfone sem uso exclusivo por outra aplicação e se a conexão WebRTC foi estabelecida. O browser só pede acesso após clique explícito. O site pode exibir “Ativar áudio recebido” caso o navegador bloqueie autoplay.

## Áudio não conecta em rede móvel/empresa

Confira UDP 50000–60000, TCP 7881, TURN/UDP 3478, TURN/TLS 443 e os ranges relay configurados. Confirme DNS/certificado de `media.voice-horizon.online` e `turn.voice-horizon.online`. HTTPS do portal sozinho não garante transporte WebRTC.

## Jogador permanece offline ou sem indicador

O add-on sincroniza posição uma vez por segundo e envia evento de saída. Confira conectividade HTTPS, chave de servidor, BDS log e API. O fallback de limpeza remove jogadores após timeout quando o evento de saída não chega.

## Deploy falha

Na VPS use `docker compose config`, `docker compose ps` e `docker compose logs -f api web livekit edge`. Confirme arquivos de certificado, `.env`, portas e permissões. Não compartilhe o `.env` ou logs com secrets.
