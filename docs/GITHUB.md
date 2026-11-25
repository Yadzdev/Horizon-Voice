# GitHub: publicar, CI, releases e deploy

## Limite de hospedagem

O GitHub é o repositório e a plataforma de automação. GitHub Pages publica ficheiros estáticos e não executa FastAPI/Python, PostgreSQL, Redis ou LiveKit. Por isso o portal, a API e o SFU são executados na VPS por Docker Compose. GitHub Actions faz os testes e, se os secrets de SSH estiverem configurados, envia o comando de atualização para essa VPS.

Fonte: [GitHub Docs — Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).

## Criar o repositório

No computador onde está a pasta do projeto:

1. Instale Git e GitHub CLI (`gh`).
2. Execute `gh auth login` e autentique na sua conta.
3. Abra PowerShell na raiz `Horizon-Voice`.
4. Execute:

```powershell
.\scripts\publish-to-github.ps1
```

O script inicializa Git se necessário, cria um repositório público chamado `Horizon-Voice` na conta autenticada e publica a branch `main`. Pode indicar outro nome: `./scripts/publish-to-github.ps1 -RepositoryName "Meu-Horizon-Voice"`.

Antes de publicar, revise `git status` e confira que `.env`, certificados, bancos locais e tokens não aparecem nos arquivos a enviar. O `.gitignore` bloqueia esses itens por padrão.

## CI automático

`.github/workflows/ci.yml` executa em push para `main`, Pull Requests e `workflow_dispatch`:

- Testes da API Python.
- Instalação de dependências e build TypeScript/Vite.
- Verificação de JSON, JavaScript do add-on e montagem dos pacotes BDS.

O build de frontend requer acesso do runner aos registries npm e pode falhar se alguma dependência mudar/incompatibilizar.

## Deploy automático da VPS

Na VPS, clone o repositório em `/opt/horizon-voice`, prepare `.env`, certificados e Docker Compose conforme `DEPLOYMENT.md`. Depois, nas configurações do repositório em **Settings → Secrets and variables → Actions**, crie:

| Secret | Valor |
|---|---|
| `DEPLOY_HOST` | IP ou hostname SSH da VPS |
| `DEPLOY_USER` | usuário SSH sem root, com permissão Docker no diretório |
| `DEPLOY_SSH_PRIVATE_KEY` | chave privada dedicada para deploy |
| `DEPLOY_KNOWN_HOSTS` | linha host key da VPS, validada fora do Actions |
| `DEPLOY_PATH` | caminho absoluto da cópia do repositório, por exemplo `/opt/horizon-voice` |

A workflow `deploy.yml` só tenta publicar após a workflow **CI** terminar com sucesso em um `push` para `main` (ou quando for iniciada manualmente) e somente quando todos os secrets estão definidos. Ela abre SSH, executa `git pull --ff-only`, valida `docker compose config` e atualiza os serviços com `docker compose up -d --build`. Ela **não** envia `.env` ou certificados; esses arquivos permanecem na VPS.

Não use `ssh-keyscan` sem validar a impressão digital do host. Não reutilize uma chave pessoal; crie uma chave restrita para Actions e remova-a quando não for mais necessária.

## Criar release e anexar o add-on

Crie uma tag `v0.1.0-preview` e envie-a:

```bash
git tag v0.1.0-preview
git push origin v0.1.0-preview
```

`release.yml` gera os pacotes `.mcaddon`, `.mcpack` e ZIP da fonte, e anexa os artefatos à página da release. Isso não certifica compatibilidade com BDS; documente o BDS exato em que foi testado antes de marcar uma release estável.
