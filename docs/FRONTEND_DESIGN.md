# Interface, identidade visual e motion

## Direção visual

A interface usa uma linguagem inspirada nos elementos de Minecraft Bedrock: blocos quadrados, contornos marcados, camadas de grama e terra, verde de folhagem, tons de pedra, pequenas etiquetas de mundo e tipografia monoespaçada para códigos e endereços. Os elementos de marca são feitos em CSS; não dependem de arte gerada por IA nem de imagens protegidas do jogo.

A página de cada servidor é a experiência principal do jogador. Ela mostra o nome, a descrição, a capa escolhida pelo proprietário, o endereço do portal e o fluxo de pareamento. A aplicação é independente e não é afiliada à Mojang ou Microsoft.

## Capa do servidor

No painel, o proprietário pode escolher PNG, JPEG ou WebP. O navegador gera uma prévia e limita a imagem a 10 MB antes de redimensionar e converter para WebP (até 1440 px e 2,5 MB). A API valida autorização, tamanho real, formato decodificável, dimensões e quantidade de pixels antes de persistir a versão otimizada em um volume Docker separado.

A imagem é opcional. Cadastros antigos e novos sem capa usam o fundo padrão de blocos. A rota pública GET /api/v1/public/servers/{slug} expõe somente nome, slug, descrição, estado e URL pública da capa; nunca retorna segredo do servidor. A capa é servida por GET /api/v1/public/servers/{slug}/image.

## Motion Principles

A implementação segue o workflow Create e o cookbook de kylezantos/design-motion-principles:

- Feedback curto ao entrar na tela e ao pressionar botões.
- Skeleton apenas enquanto dados remotos estão carregando.
- Lazy loading e decoding assíncrono para miniaturas fora da primeira dobra.
- Estado de progresso no botão durante cadastro e processamento da imagem.
- Animações limitadas a transform e opacity; sem deslocamento de layout.
- prefers-reduced-motion desativa transições e animações.
- Sem pulsação contínua, parallax ou animação em eventos de alta frequência.

## Validação

A cobertura automatizada inclui testes unitários para resolução do tenant, integração da API para upload/autorização/consulta pública e Playwright para o portal do jogador e o fluxo de cadastro com imagem. Teste manual em 360px, 768px e desktop continua necessário antes de um release estável.
