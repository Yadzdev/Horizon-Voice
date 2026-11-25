# Deploy da plataforma em VPS

## Por que precisa de VPS

O repositório GitHub armazena o código e executa automações. GitHub Pages serve arquivos estáticos e não executa FastAPI/Python. O processo FastAPI, PostgreSQL, Redis e LiveKit SFU precisam de processos/containers persistentes. Este projeto usa Docker Compose em uma VPS e pode ser atualizado por GitHub Actions via SSH. Consulte [GITHUB.md](GITHUB.md).

## Requisitos

- VPS Linux com Docker Engine e plugin Docker Compose.
- IP público fixo e firewall que permita UDP.
- DNS para `voice-horizon.online`.
- Certificado TLS confiável (não autoassinado) com SANs `voice-horizon.online` e `*.voice-horizon.online`.
- Certificado e chave em `certs/fullchain.pem` e `certs/privkey.pem`.
- Capacidade de CPU/rede suficiente para mídia WebRTC. Dimensionamento precisa ser medido com carga real.

## DNS

Crie registros apontando para o IP da VPS:

| Tipo | Nome | Valor |
|---|---|---|
| A | `voice-horizon.online` | IP público da VPS |
| A | `*.voice-horizon.online` | IP público da VPS |

O wildcard abrange subdomínios de clientes, `media.voice-horizon.online` e `turn.voice-horizon.online`. O certificado wildcard deve incluir também o domínio raiz. Para emitir wildcard com Let's Encrypt, use validação DNS-01 no seu provedor DNS.

## Preparar servidor

Clone o repositório público na VPS e entre na pasta:

```bash
sudo mkdir -p /opt/horizon-voice
sudo chown "$USER":"$USER" /opt/horizon-voice
git clone https://github.com/SEU_USUARIO/Horizon-Voice.git /opt/horizon-voice
cd /opt/horizon-voice
cp .env.example .env
python3 scripts/generate-secrets.py
```

Copie os valores gerados para `.env`, substituindo todos os `CHANGE_ME`. Não coloque `.env`, chave TLS ou credenciais em commits, Issues, screenshots ou logs públicos. `LIVEKIT_API_KEY=horizon_voice` é o identificador da chave; `LIVEKIT_API_SECRET` deve ser secreto e aleatório.

Coloque o certificado e a chave em:

```text
certs/fullchain.pem
certs/privkey.pem
```

Os dois devem ser legíveis pelo processo do container. Não publique a chave privada.

## Portas

Abra as portas a seguir tanto no firewall da VPS quanto no firewall de rede do provedor:

| Porta | Protocolo | Uso |
|---|---|---|
| 80 | TCP | Redirecionamento HTTP para HTTPS / validação web |
| 443 | TCP | Portal/API HTTPS, sinalização LiveKit WSS e TURN/TLS no hostname `turn.voice-horizon.online` (roteado por SNI) |
| 7881 | TCP | Fallback ICE/TCP do LiveKit |
| 50000–60000 | UDP | Mídia WebRTC ICE |
| 3478 | UDP | TURN/UDP e STUN |
| 30000–40000 | UDP | Faixa de relay TURN configurada neste arquivo |

PostgreSQL 5432, Redis 6379, FastAPI 8000 e LiveKit 7880 permanecem somente na rede privada Docker. Não crie regras públicas para essas portas.

LiveKit requer acesso de mídia UDP e TCP/TURN; HTTPS sozinho não transporta o áudio. Verifique os testes de conectividade a partir de redes móveis e redes restritivas. A documentação oficial lista as portas ICE, TCP e TURN necessárias. [LiveKit: Ports and firewall](https://docs.livekit.io/transport/self-hosting/ports-firewall/).

## Iniciar

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs -f api web livekit edge
```

O container da API executa `alembic upgrade head` antes do Uvicorn. O frontend é compilado por Vite no build e servido pelo Nginx. O HAProxy faz encaminhamento L4 do tráfego TLS: `turn.voice-horizon.online` segue para TURN/TLS no LiveKit com PROXY protocol v2 para preservar o IP de origem; os outros hosts TLS chegam ao Nginx. A rede Docker usa a sub-rede `172.31.240.0/24`; se alterá-la, ajuste também `turn.proxy_protocol_trusted_cidrs` em `infra/livekit/livekit.yaml`. O Nginx encaminha `/api/` para FastAPI e `media.voice-horizon.online` para a sinalização LiveKit.

## Confirmar

1. `https://voice-horizon.online` abre o portal.
2. `https://media.voice-horizon.online` responde pela sinalização LiveKit (não é uma página web normal).
3. `https://<slug>.voice-horizon.online` resolve para o tenant correto após ativação.
4. `https://voice-horizon.online/api/v1/health` retorna status `ok`.
5. Teste um cliente BDS de preview que contenha os módulos Script API do manifesto.
6. Teste pelo menos dois navegadores em dispositivos/redes diferentes; um deve ouvir o outro apenas dentro da distância/dimensão/grupo autorizados.
7. Teste TURN/TLS com UDP bloqueado e TURN/UDP em uma rede que permita UDP.

Não marque o serviço como lançado até esses testes passarem.

## Operação e backups

- Faça backup diário de PostgreSQL e teste restauração.
- Redis é usado pelo LiveKit, mas a API ainda tem limites e caches locais em memória.
- Mantenha uma única réplica/worker FastAPI. Não escale a API horizontalmente até implementar rate limit distribuído, presença distribuída e locks/pub-sub compartilhados.
- Atualize imagens e dependências com revisão; não use `latest` em produção.
- Observe CPU, RAM, tráfego UDP, qualidade WebRTC, falhas de TURN, latência de API e tamanho do PostgreSQL.
- Tenha política de privacidade e retenção. O projeto não grava áudio por padrão.

## Rollback

Antes de atualizar, faça backup de PostgreSQL e registre o commit atual. Para voltar:

```bash
git log -1 --oneline
git checkout <commit-estavel>
docker compose up -d --build
```

A política de migração deve preservar compatibilidade. Não aplique downgrade destrutivo de schema sem backup validado.
