# Changelog

## 0.1.0-preview — 2026-11-25

- Registro de conta, tenant, ativação BDS e pareamento de navegador.
- Sincronização de posições em lotes e isolamento de proximidade entre dimensões.
- Emissão de tokens LiveKit com assinatura seletiva autorizada pela API.
- Controles de publicação, mute, deafen, mute local e presença via webhook.
- Grupos públicos/privados com senha Argon2 e modo exclusivo da proximidade.
- Portal React com captura de microfone após interação, seleção de dispositivos e reconexão/renovação de token.
- Indicadores de nome `[LINK]`, `[FALANDO]` e `[MUDO]` no BDS.
- Endpoint de saída BDS para expirar presença/pareamento e encerrar a sessão no SFU.
- Docker Compose para API, PostgreSQL, Redis, LiveKit, Nginx e HAProxy; CI, deploy SSH opcional e automação de release.
- O add-on continua dependendo de `@minecraft/server-net` em pré-lançamento; build Docker, TypeScript completo e testes reais de BDS/WebRTC dependem de execução em ambiente com rede, certificados e servidor.
