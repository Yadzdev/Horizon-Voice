# Observabilidade

O backend oferece duas integrações opcionais:

- Sentry para captura de exceções da API, com send_default_pii=False e amostragem de traces em 5%.
- OpenTelemetry para traces HTTP/FastAPI e consultas SQLAlchemy exportados via OTLP/HTTP.

Datadog e New Relic podem receber os dados através do agente, collector ou endpoint OTLP escolhido. O Horizon Voice não cria contas, projetos, dashboards nem credenciais nesses fornecedores.

## Variáveis da API

Configure no arquivo .env da VPS:

| Variável | Exemplo | Efeito |
|---|---|---|
| SENTRY_DSN | DSN do projeto da API | Ativa captura de exceções da API |
| OTEL_ENABLED | true | Ativa a instrumentação FastAPI e SQLAlchemy |
| OTEL_EXPORTER_OTLP_ENDPOINT | http://otel-collector:4318/v1/traces | Destino OTLP/HTTP; vazio usa o endpoint padrão do exporter |

Após alterar o .env, valide a configuração e recrie a API com Docker Compose.

## Privacidade e operação

- Nunca envie tokens, chaves de servidor, códigos de pareamento, áudio, posições de jogadores ou conteúdo de grupos para atributos de telemetria.
- Não habilite send_default_pii no Sentry.
- Proteja o endpoint OTLP e prefira tráfego privado/TLS entre a VPS e o collector.
- Ajuste a amostragem de acordo com tráfego e custo antes de escalar.
- Não configure múltiplos exporters para o mesmo fluxo sem necessidade; isso duplica volume e custo.
- Health check continua disponível em /api/v1/health.

## O que exige configuração externa

O Sentry só coleta quando um DSN válido for configurado. Datadog/New Relic só recebem dados quando um agente, collector ou endpoint OTLP acessível estiver configurado. Nenhuma credencial é incluída no repositório.
