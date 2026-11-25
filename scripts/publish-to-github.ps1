[CmdletBinding()]
param(
    [string]$RepositoryName = "Horizon-Voice"
)

$ErrorActionPreference = "Stop"

function Stop-WithMessage([string]$Message) {
    Write-Host "ERRO: $Message" -ForegroundColor Red
    exit 1
}

# This script must be executed as a .ps1 file. Pasting its lines into the
# interactive console leaves the script path variables empty.
$scriptFile = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($scriptFile) -or -not (Test-Path -LiteralPath $scriptFile -PathType Leaf)) {
    Stop-WithMessage "Execute o arquivo publish-to-github.ps1 diretamente. Não cole o conteúdo linha por linha no PowerShell."
}

$scriptDirectory = Split-Path -Parent (Resolve-Path -LiteralPath $scriptFile).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDirectory "..")).Path

# Refuse to run from a random folder (for example C:\Users\<user>).
$requiredPaths = @(
    ".gitignore",
    "README.md",
    "docker-compose.yml",
    "backend",
    "frontend",
    "addon"
)
foreach ($relativePath in $requiredPaths) {
    $candidate = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $candidate)) {
        Stop-WithMessage "A pasta informada não parece ser a raiz do Horizon-Voice. Arquivo/pasta ausente: $relativePath. Extraia o ZIP completo e execute o script dentro de Horizon-Voice\scripts."
    }
}

if ($RepositoryName -notmatch '^[A-Za-z0-9_.-]+$') {
    Stop-WithMessage "Nome de repositório inválido: $RepositoryName"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "Git não foi encontrado. Instale Git for Windows e abra um novo PowerShell."
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "GitHub CLI (gh) não foi encontrado. Instale GitHub CLI e abra um novo PowerShell."
}

& gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Sua conta ainda não está autenticada. Execute: gh auth login"
}

$account = (& gh api user --jq .login).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($account)) {
    Stop-WithMessage "Não foi possível identificar a conta GitHub autenticada. Execute gh auth login."
}
$repositoryFullName = "$account/$RepositoryName"

Write-Host "Projeto encontrado: $projectRoot" -ForegroundColor Cyan
Write-Host "Destino: https://github.com/$repositoryFullName" -ForegroundColor Cyan
Write-Host "Atenção: o repositório será PÚBLICO. Não publique senhas, tokens ou arquivos .env." -ForegroundColor Yellow
$confirmation = Read-Host "Digite PUBLICAR para continuar"
if ($confirmation -cne "PUBLICAR") {
    Write-Host "Cancelado. Nenhum repositório foi criado." -ForegroundColor Yellow
    exit 0
}

Push-Location $projectRoot
try {
    $insideRepo = $false
    $existingTopLevel = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($existingTopLevel | Out-String).Trim())) {
        $insideRepo = $true
        $actualGitRoot = (Resolve-Path -LiteralPath ($existingTopLevel | Out-String).Trim()).Path.TrimEnd('\')
        $expectedGitRoot = (Resolve-Path -LiteralPath $projectRoot).Path.TrimEnd('\')
        if (-not [string]::Equals($actualGitRoot, $expectedGitRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-WithMessage "Foi encontrado um repositório Git em uma pasta PAI ($actualGitRoot), e não na pasta Horizon-Voice. Isso costuma acontecer quando o script é executado em C:\Users\<usuario>. Feche o terminal, remova somente o .git acidental da pasta do usuário (veja as instruções no chat) e execute este arquivo dentro de Horizon-Voice\scripts."
        }
    }

    if (-not $insideRepo) {
        & git init
        if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Não foi possível inicializar o Git na pasta do projeto." }
    }

    & git branch -M main
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Não foi possível definir a branch main." }

    & git add -A
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Falha ao preparar os arquivos. Verifique permissões e .gitignore." }

    & git diff --cached --quiet
    $diffExit = $LASTEXITCODE
    if ($diffExit -eq 1) {
        & git -c user.name="$account" -c user.email="$account@users.noreply.github.com" commit -m "Publish Horizon Voice source"
        if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Falha ao criar o commit. Configure seu nome/e-mail Git e tente novamente." }
    } elseif ($diffExit -ne 0) {
        Stop-WithMessage "Não foi possível verificar os arquivos preparados pelo Git."
    }

    # Create the public repo if it does not exist yet; reuse it if it already exists.
    & gh repo view $repositoryFullName --json nameWithOwner | Out-Null
    $repoExists = ($LASTEXITCODE -eq 0)
    if (-not $repoExists) {
        & gh repo create $repositoryFullName --public --description "Horizon Voice - Minecraft Bedrock voice platform"
        if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Falha ao criar o repositório no GitHub." }
    }

    $remoteUrl = (& git remote get-url origin 2>$null)
    $remoteExit = $LASTEXITCODE
    $expectedUrl = "https://github.com/$repositoryFullName.git"

    if ($remoteExit -ne 0 -or [string]::IsNullOrWhiteSpace(($remoteUrl | Out-String).Trim())) {
        & git remote add origin $expectedUrl
        if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Não foi possível configurar o remote origin." }
    } else {
        $normalizedRemote = ($remoteUrl | Out-String).Trim().TrimEnd('/')
        $normalizedExpected = $expectedUrl.TrimEnd('/')
        if ($normalizedRemote -notmatch [regex]::Escape($repositoryFullName)) {
            Stop-WithMessage "Já existe um remote origin diferente ($normalizedRemote). Não alterei esse destino. Revise git remote -v antes de continuar."
        }
    }

    & git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "O push falhou. Se o repositório remoto já tiver arquivos/commits, será necessário reconciliar o histórico antes de tentar novamente."
    }

    Write-Host "Publicação concluída: https://github.com/$repositoryFullName" -ForegroundColor Green
    Write-Host "Acesse a aba Actions para acompanhar CI. A API e o LiveKit ainda precisam ser implantados em uma VPS; GitHub não os hospeda como processos permanentes." -ForegroundColor Yellow
}
finally {
    Pop-Location
}
