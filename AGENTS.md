# Horizon Voice — regras para qualquer agente e colaborador

Estas regras valem para pessoas, agentes e qualquer modelo.

## Fluxo obrigatório: Issue → Branch → Pull Request → Deploy

1. Antes de cada correção, melhoria ou funcionalidade, abra uma GitHub Issue com contexto, escopo, critérios de aceitação, riscos e impacto.
2. Crie uma branch por Issue: `feat/<numero>-<slug>`, `fix/<numero>-<slug>`, `docs/<numero>-<slug>` ou `test/<numero>-<slug>`.
3. Use commits Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `ci:` etc.).
4. Abra um Pull Request para `main`. A descrição deve incluir `Fixes #N` quando resolver a Issue ou `Refs #N` quando estiver relacionada.
5. Descreva alterações, validação, impacto de segurança, telas afetadas e itens ainda não testados.
6. Atualize documentação e changelog no mesmo PR.
7. Aguarde CI e revisão. Não faça push direto em `main`, não faça deploy de branch de trabalho e não faça merge para ignorar checks.
8. Produção só recebe deploy depois de PR aprovado e merge em `main`, pelo workflow de deploy.

## Segurança e compatibilidade

- Preserve contratos HTTP, autenticação, isolamento multi-tenant, IDs e fluxos de áudio, salvo Issue coordenada que autorize a mudança.
- Nunca versionar chaves, senhas, tokens, DSNs privados, dados de jogadores, capturas com PII ou gravações.
- Valide entradas no cliente e no servidor. Não confie apenas no MIME declarado; valide assinatura/estrutura no backend.
- Capas dos servidores são públicas. Limite peso e tipos; nunca exponha `settings_json` ou segredos.
- Use capturas próprias/licenciadas. Não presuma que imagem encontrada na web pode ser reutilizada comercialmente.
- Horizon Voice é independente e não pode ser apresentado como oficial ou afiliado à Mojang/Microsoft.
- Preserve teclado, foco visível, contraste e `prefers-reduced-motion`.

## Motion e carregamento

- Consulte https://github.com/kylezantos/design-principles antes de alterar motion.
- Skeletons só durante carregamentos reais, com dimensões próximas do conteúdo final.
- Use lazy loading e decoding assíncrono em mídia não crítica.
- Prefira transições curtas, reversíveis e orientadas a feedback; evite loops decorativos e animação de dados atualizados frequentemente.
- Respeite `prefers-reduced-motion`.

## Qualidade e observabilidade

- Rode lint, arquitetura, unitários, build e E2E relevantes antes de abrir/atualizar um PR.
- Use Biome, Dependency Cruiser/contratos de arquitetura, Knip, Commitlint, Vitest, Playwright, Stryker e Codecov.
- OpenTelemetry é o padrão de traces; Sentry é opcional para erros. Datadog e New Relic podem receber OTLP via collector/endpoint.
- Sem DSN ou collector configurado, não enviar telemetria.
- Não enviar pairing codes, tokens, cabeçalhos Authorization, áudio ou PII à telemetria.

## Checklist de PR

- [ ] Issue mencionada na descrição.
- [ ] Branch ligada à Issue; sem commit direto em main.
- [ ] Testes, docs e changelog atualizados.
- [ ] Lint, arquitetura, testes, build e Playwright relevantes executados.
- [ ] Segurança, acessibilidade e reduced motion revisados.
- [ ] Sem segredos, PII ou conteúdo sem licença.
- [ ] Deploy somente após checks verdes, aprovação e merge.
