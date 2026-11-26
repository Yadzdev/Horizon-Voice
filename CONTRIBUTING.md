# Contribuindo com Horizon Voice

O fluxo obrigatório é **Issue → Branch → Pull Request → Deploy**. Leia [AGENTS.md](./AGENTS.md) antes de qualquer mudança; as regras valem para colaboradores e agentes automatizados.

1. Abra uma Issue com contexto e critérios de aceitação.
2. Crie uma branch `feat/<numero>-<slug>`, `fix/<numero>-<slug>`, `docs/<numero>-<slug>` ou `test/<numero>-<slug>`.
3. Desenvolva, teste e atualize documentação/changelog.
4. Abra PR para `main` e mencione `Fixes #N` ou `Refs #N` na descrição.
5. Aguarde CI e revisão. Produção só recebe deploy depois de merge aprovado.

Não envie credenciais, tokens, DSNs privados, dados de jogadores, capturas com PII ou gravações de voz ao repositório.
