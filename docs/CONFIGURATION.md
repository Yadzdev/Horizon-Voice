# Configuração do Horizon Voice

## Segredos de produção

Copie `.env.example` para `.env` **na VPS**. Não publique esse arquivo. Gere valores individuais para `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET` (64 caracteres aleatórios ou mais) e `LIVEKIT_API_SECRET`. `LIVEKIT_API_KEY` é um identificador público de chave e precisa corresponder ao `webhook.api_key` em `infra/livekit/livekit.yaml`. Gere candidatos com `python scripts/generate-secrets.py`; o script apenas imprime os valores.

| Variável | Valor padrão | Uso |
|---|---|---|
| `ENVIRONMENT` | `development` | Em produção ativa validações adicionais e oculta `/docs`. |
| `DATABASE_URL` | `sqlite:///./horizon_voice.db` | Banco SQLAlchemy; produção exige PostgreSQL. |
| `JWT_SECRET` | chave de desenvolvimento | Assinatura dos tokens do painel; obrigatório trocar em produção. |
| `PUBLIC_BASE_DOMAIN` | `voice-horizon.online` | Domínio raiz dos tenants. |
| `PAIRING_CODE_SECONDS` | `180` | Validade do código de pareamento. |
| `BROWSER_SESSION_MINUTES` | `720` | Validade máxima da sessão de navegador. |
| `DEFAULT_PROXIMITY_BLOCKS` | `30` | Alcance inicial de proximidade. |
| `COOKIE_SECURE` | `false` | Deve ser `true` com HTTPS em produção. |
| `AUTO_CREATE_SCHEMA` | `true` | Desenvolvimento apenas; produção usa Alembic. |
| `REDIS_URL` | `redis://localhost:6379/0` | Disponibilizado à API para futura coordenação distribuída; presença, rate limit e WebSocket da API ainda são locais ao processo. |
| `LIVEKIT_URL` | `http://livekit:7880` | Endpoint interno da API de mídia; não expor ao navegador. |
| `LIVEKIT_PUBLIC_URL` | `wss://media.voice-horizon.online` | URL pública WSS usada pelo cliente LiveKit. |
| `LIVEKIT_API_KEY` | vazio | Identificador de API LiveKit; também usado em `--keys` e webhook. |
| `LIVEKIT_API_SECRET` | vazio | Segredo LiveKit; nunca enviar ao navegador. |
| `LIVEKIT_TOKEN_MINUTES` | `60` | Duração do token de participante (limitada pela API a 5–120 minutos). |

## TLS, TURN e proxy

Monte o certificado válido e a chave em `certs/fullchain.pem` e `certs/privkey.pem`. O certificado deve abranger `voice-horizon.online` e `*.voice-horizon.online`, pois o HAProxy encaminha por SNI `turn.voice-horizon.online` diretamente ao TURN/TLS do LiveKit. O HAProxy usa PROXY protocol v2 para preservar o IP de origem; `infra/livekit/livekit.yaml` só confia nessa informação na rede Docker `172.31.240.0/24`. Se a rede Compose for alterada, atualize simultaneamente o subnet e `turn.proxy_protocol_trusted_cidrs`.

O listener `media.voice-horizon.online` passa pela terminação TLS do Nginx e encaminha WSS para LiveKit. Portas públicas de mídia são configuradas em `docs/DEPLOYMENT.md`. HTTPS sozinho não substitui ICE/TURN.

## Add-on BDS

O endereço central está definido em `addon/behavior_pack/scripts/network.js` (`API_BASE`). Ao publicar uma infraestrutura em outro domínio, altere-o antes de gerar o `.mcaddon`. O segredo de servidor recebido após ativação é gravado como propriedade dinâmica do mundo `horizonvoice:server_secret` e enviado apenas no cabeçalho `X-Server-Key`.

A comunicação do add-on usa `@minecraft/server-net`, que é uma dependência experimental/pré-lançamento na versão documentada. O administrador precisa habilitar o módulo e restringir `allowed_uris` em `permissions.json` conforme `docs/COMPATIBILITY.md`. Não remova a restrição de origem para contornar erros de rede.

## Tenancy

- Produção: `https://<slug>.voice-horizon.online`.
- Desenvolvimento: `http://localhost:5173/?tenant=<slug>` com Vite proxy para `http://127.0.0.1:8000`, ou defina `VITE_API_BASE_URL`.
- Slugs reservados incluem `www`, `api`, `dashboard`, `docs`, `status`, `admin`, `mail`, `ftp`, `voice`, `media`, `turn` e `livekit`.
