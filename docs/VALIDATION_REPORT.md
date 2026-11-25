# Horizon Voice — relatório de validação da prévia

**Data:** 25 de novembro de 2026  
**Escopo:** verificações executadas no ambiente de desenvolvimento desta entrega. Este relatório não é certificação de produção nem teste em uma rede Minecraft real.

## Resultado das verificações executadas

| Verificação | Resultado | Observação |
|---|---|---|
| Testes FastAPI | **12 aprovados** | `cd backend && python -m pytest -q` |
| Compilação sintática Python | **Aprovada** | API, testes, migrations e scripts |
| Migrações Alembic | **Aprovadas** | `upgrade head` em SQLite limpo; tabelas e colunas de voz verificadas |
| JavaScript do Behavior Pack | **Aprovado** | `node --check` em todos os scripts |
| Sintaxe TS/TSX | **Aprovada** | `transpileModule` em quatro fontes; não equivale a typecheck |
| Manifestos do add-on | **Aprovados** | JSON, UUIDs, entry point e unicidade verificados pelo empacotador |
| Docker Compose / LiveKit YAML | **Sintaxe aprovada** | Parse YAML; não é validação semântica do Docker/LiveKit |
| Workflows GitHub Actions | **Sintaxe YAML aprovada** | Não houve execução em um repositório GitHub |
| `.mcpack` e `.mcaddon` | **Gerados e íntegros** | Teste de integridade ZIP e manifests internos |

### Cobertura dos 12 testes da API

- Cadastro de conta e servidor, ativação e pareamento.
- Uso único do código de ativação e limite de geração de códigos de pareamento.
- Isolamento multi-tenant e entre dimensões.
- Rejeição de coordenadas não finitas.
- Regra de proximidade versus grupo exclusivo.
- Entrada em grupo privado, verificação de senha e capacidade.
- Saída de jogador BDS e expiração de presença/pareamento.
- API de voz falha de forma segura com HTTP 503 quando LiveKit não está configurado, e aplica rate limit.
- Criação/entrada/saída de grupo por chamadas autenticadas do BDS.
- Exclusão de grupo pelo proprietário e recusa para outro jogador.
- Verificação estrutural de que endpoints que agendam sincronização LiveKit são assíncronos.

## Não executado ou não comprovado

1. **Build completo React/Vite e typecheck:** `npm install` não terminou neste ambiente; portanto `tsc -b` e `vite build` não foram executados localmente. O workflow CI fará essa verificação em runner GitHub com acesso ao registry npm.
2. **Docker:** Docker Engine/Compose não estão disponíveis neste ambiente. Não foram executados `docker compose config`, build de imagens, inicialização dos containers, teste Nginx/HAProxy ou deploy.
3. **LiveKit real:** o pacote Python `livekit-api` e um servidor LiveKit acessível não estão disponíveis aqui. Os testes verificam o comportamento fail-closed sem credenciais, não emissão real de token, webhook, mute, update-participant ou assinaturas seletivas no SFU.
4. **WebRTC/TURN:** não foi feito teste de microfone e alto-falante entre navegadores, redes distintas, NAT, TURN/UDP ou TURN/TLS.
5. **Minecraft BDS:** não há um BDS real neste ambiente. Não foram comprovados importação, registro de comandos, forms, `server-net`, nameTag, permissões de rede nem carga de jogadores no servidor.
6. **GitHub e VPS:** o repositório `Horizon-Voice` ainda não foi criado/publicado, nenhum workflow foi executado e nenhuma VPS foi provisionada ou atualizada.

## Restrições de arquitetura e segurança

- GitHub armazena código, documentação, Issues, Releases e executa Actions. GitHub Pages é hospedagem estática; não mantém FastAPI, PostgreSQL, Redis ou LiveKit em execução contínua. A API, o banco, Redis e SFU precisam de uma VPS/host de containers. Actions pode acionar o deploy por SSH depois de CI bem-sucedido.
- O add-on depende de `@minecraft/server-net` em pré-lançamento e de permissões de rede do BDS. A compatibilidade está limitada à versão indicada em `docs/COMPATIBILITY.md` e precisa ser testada no build exato do servidor.
- O comando utiliza namespace (`/horizon:voz` e `/horizon:cadastrarvoice`), não o alias literal `/voz`.
- `Player.id` é identidade da entidade/sessão no BDS, não XUID persistente; reconexões podem exigir novo pareamento.
- O estado de sincronização e os limites de requisição FastAPI são locais ao processo. A implantação usa uma réplica/worker; não escale horizontalmente sem implementar e testar coordenação distribuída com Redis.
- A aplicação não grava áudio por padrão. `speaking` é indicador de interface, não mecanismo de autenticação.

## Estado da entrega

**Preview técnica integrada — não publicar como serviço de produção ainda.** A base de API, portal, integração LiveKit e add-on foi implementada, mas o áudio real só pode ser considerado funcional depois de validar SDK/servidor LiveKit, sinalização, WebRTC/TURN, microfone, assinaturas seletivas e BDS no ambiente de destino. Não é correto prometer “zero erros” sem esses testes.

Antes da abertura pública: crie o repositório com `scripts/publish-to-github.ps1`, configure secrets de deploy conforme `docs/GITHUB.md`, configure domínio/certificados/portas conforme `docs/DEPLOYMENT.md`, aguarde CI verde e execute os testes de integração listados na documentação.
