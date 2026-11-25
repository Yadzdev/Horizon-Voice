# Modelo de segurança

## Controles presentes no código

- Senhas de conta/grupo com Argon2.
- JWT de proprietário com issuer, expiração e JTI.
- Credencial do servidor BDS aleatória, emitida uma vez e armazenada como hash SHA-256.
- Códigos de ativação e pareamento com expiração e uso único.
- Sessão do navegador em cookie HttpOnly; o banco guarda hash do token.
- Resolução de tenant por subdomínio/slug e validação das relações de servidor nas operações.
- Token LiveKit curto com permissão de publicação controlada e `can_subscribe=false` para impedir assinatura livre no browser.
- `autoSubscribe:false` no cliente; a API concede as inscrições de tracks com RoomService depois de avaliar as permissões.
- Mute de publicação e tracks aplicados pela API ao SFU.
- Deafen e mute local removem a permissão de escuta correspondente na reconciliação.
- Grupo ativo exclusivo da proximidade: não há vazamento automático da conversa do grupo para jogadores próximos.
- Webhooks LiveKit validados com assinatura e hash do corpo bruto.
- Nenhum recurso de gravação de áudio está incluído.

## Requisitos e riscos ainda abertos

1. **BDS networking:** `@minecraft/server-net` permanece pré-lançamento; testar cada versão e substituir quando houver uma API estável apropriada.
2. **Identidade:** `Player.id` é identidade de entidade/sessão; não usar como identidade persistente de conta. O projeto exige novo pareamento ao reconectar com outra entidade.
3. **Rate limiting:** limites atuais são em memória por processo. Redis ainda não alimenta os buckets da FastAPI. Mantenha uma réplica e endureça antes de uso público amplo.
4. **Presença/coordenação:** caches de subscriptions e reconciliação são locais. Não escale o número de workers/replicas sem coordenação distribuída.
5. **Credenciais:** ainda não há rotação automatizada de server key, LiveKit key nem revogação global de sessões.
6. **Conta:** recuperação de senha, verificação de e-mail, gestão de sessão e MFA não estão implementados.
7. **CSRF/XSS:** o JWT do proprietário é armazenado em `sessionStorage`; revise o modelo de ameaça e prefira cookie seguro/HttpOnly com CSRF para uma plataforma pública.
8. **Dashboard:** o painel é uma primeira versão. Testar autorização em cada operação de administração e adicionar auditoria/fluxo completo antes da abertura.
9. **Moderação:** mute é aplicado no SFU e o estado de speaking é visual. Não usar o indicador de fala como autenticação nem como controle de permissão.
10. **Infraestrutura:** validar TLS, wildcard DNS, TURN, firewall, backups, restore, limites de recursos e logs no provedor real.
11. **Privacidade:** publicar política de privacidade, moderação e retenção. Nunca gravar áudio sem consentimento separado, explícito e apropriado.

## Segredos

Nunca commitar `.env`, chaves TLS, `LIVEKIT_API_SECRET`, `JWT_SECRET`, senhas PostgreSQL/Redis ou credencial BDS. Use GitHub Actions Secrets apenas para parâmetros de deploy, e os segredos da aplicação exclusivamente no `.env` protegido da VPS.

## Política de lançamento

Só marcar release como produção depois que CI, build Docker, BDS real, múltiplos browsers, proximidade, isolamento de dimensão/tenant, grupos, mute/deafen, TURN em rede restrita, restauração de backup e revisão independente de segurança tiverem sido verificados.
