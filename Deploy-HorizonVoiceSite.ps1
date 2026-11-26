#Requires -Version 5.1
<#
Horizon Voice production deploy helper.
Run this file from the extracted project folder. It deliberately refuses to deploy
until PR #7 is merged and every check on its head commit has succeeded.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Stop-Deploy {
    param([string]$Message)
    Write-Host ''
    Write-Host "[DEPLOY CANCELADO] $Message" -ForegroundColor Red
    exit 1
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

Write-Host ''
Write-Host '===== HORIZON VOICE - VALIDACAO LOCAL =====' -ForegroundColor Cyan

$RequiredFiles = @(
    'docker-compose.yml',
    'frontend\Dockerfile',
    'frontend\src\main.tsx',
    'frontend\src\App.tsx',
    'backend\Dockerfile',
    'backend\alembic\versions\0005_server_images.py',
    'infra\nginx\default.conf',
    'infra\haproxy\haproxy.cfg',
    'infra\livekit\livekit.yaml',
    'scripts\package_source.py',
    'Deploy-HorizonVoiceSite.ps1'
)

$MissingFiles = @()
foreach ($RelativePath in $RequiredFiles) {
    $Exists = Test-Path -LiteralPath (Join-Path $RepoRoot $RelativePath) -PathType Leaf
    if ($Exists) {
        Write-Host "[OK]      $RelativePath" -ForegroundColor Green
    }
    else {
        Write-Host "[AUSENTE] $RelativePath" -ForegroundColor Red
        $MissingFiles += $RelativePath
    }
}
if ($MissingFiles.Count -gt 0) {
    Stop-Deploy 'O pacote está incompleto. Extraia novamente o ZIP completo e execute o script na pasta raiz.'
}

$SshKey = Join-Path $HOME '.ssh\horizon_voice_vps'
if (Test-Path -LiteralPath $SshKey -PathType Leaf) {
    Write-Host "[OK]      Chave SSH: $SshKey" -ForegroundColor Green
}
else {
    Stop-Deploy "Chave SSH não encontrada: $SshKey"
}

$SshCommand = Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
if (-not $SshCommand) {
    Stop-Deploy 'OpenSSH não encontrado. Ative o Cliente OpenSSH nos Recursos Opcionais do Windows.'
}

Write-Host ''
Write-Host '===== VALIDACAO DO GITHUB - PR #7 =====' -ForegroundColor Cyan

$Headers = @{
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'HorizonVoice-DeployScript'
}

try {
    $PR = Invoke-RestMethod -Method Get -Uri 'https://api.github.com/repos/Yadzdev/Horizon-Voice/pulls/7' -Headers $Headers
}
catch {
    Stop-Deploy "Não foi possível consultar a PR #7 no GitHub: $($_.Exception.Message)"
}

Write-Host "PR: #$($PR.number) - $($PR.title)"
Write-Host "Estado: $($PR.state)"
Write-Host "Integrada: $($PR.merged)"
Write-Host "Commit: $($PR.head.sha)"

if (-not $PR.merged) {
    Stop-Deploy 'A PR #7 ainda não foi integrada ao main. O deploy não será iniciado.'
}

try {
    $Checks = Invoke-RestMethod -Method Get -Uri "https://api.github.com/repos/Yadzdev/Horizon-Voice/commits/$($PR.head.sha)/check-runs" -Headers $Headers
}
catch {
    Stop-Deploy "Não foi possível consultar as verificações do GitHub: $($_.Exception.Message)"
}

$CheckRuns = @($Checks.check_runs)
if ($CheckRuns.Count -eq 0) {
    Stop-Deploy 'O GitHub não retornou verificações para o commit da PR. Não é seguro liberar o deploy.'
}

$FailedChecks = @($CheckRuns | Where-Object {
    $_.status -ne 'completed' -or $_.conclusion -ne 'success'
})

foreach ($Check in $CheckRuns) {
    if ($Check.status -eq 'completed' -and $Check.conclusion -eq 'success') {
        Write-Host "[APROVADO] $($Check.name)" -ForegroundColor Green
    }
    else {
        Write-Host "[PENDENTE/FALHOU] $($Check.name) - $($Check.status) / $($Check.conclusion)" -ForegroundColor Red
    }
}

if ($FailedChecks.Count -gt 0) {
    Stop-Deploy 'Existem verificações pendentes ou com falha. Corrija o CI antes de publicar.'
}

Write-Host ''
Write-Host '===== DADOS DA VPS =====' -ForegroundColor Cyan

$VpsHost = Read-Host 'IP ou domínio da VPS'
if ([string]::IsNullOrWhiteSpace($VpsHost) -or $VpsHost -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$') {
    Stop-Deploy 'IP/domínio inválido.'
}

$VpsUser = Read-Host 'Usuário SSH da VPS'
if ([string]::IsNullOrWhiteSpace($VpsUser) -or $VpsUser -notmatch '^[A-Za-z_][A-Za-z0-9_.-]*$') {
    Stop-Deploy 'Usuário SSH inválido.'
}

$VpsPath = Read-Host 'Pasta do projeto na VPS [/opt/horizon-voice]'
if ([string]::IsNullOrWhiteSpace($VpsPath)) {
    $VpsPath = '/opt/horizon-voice'
}
if ($VpsPath -notmatch '^/[A-Za-z0-9._/-]+$') {
    Stop-Deploy 'Caminho remoto inválido. Use um caminho absoluto sem espaços.'
}

Write-Host ("Destino: {0}@{1}:{2}" -f $VpsUser, $VpsHost, $VpsPath)
Write-Host 'A VPS precisa ter o repositório Git clonado, .env configurado e certificados TLS instalados.'
Write-Host 'O script fará backup do PostgreSQL antes de atualizar, quando o banco já estiver em execução.'

$Confirm = Read-Host 'Digite PUBLICAR para confirmar o deploy'
if ($Confirm -cne 'PUBLICAR') {
    Stop-Deploy 'Operação cancelada pelo usuário.'
}

$RemoteScript = @'
#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_PATH='__VPS_PATH__'
cd "$PROJECT_PATH"

echo '[1/7] Conferindo ambiente da VPS...'
test -d .git || { echo 'ERRO: esta pasta não contém um clone Git.' >&2; exit 10; }
test -s .env || { echo 'ERRO: arquivo .env ausente ou vazio.' >&2; exit 11; }
test -s certs/fullchain.pem || { echo 'ERRO: certs/fullchain.pem ausente.' >&2; exit 12; }
test -s certs/privkey.pem || { echo 'ERRO: certs/privkey.pem ausente.' >&2; exit 13; }
command -v docker >/dev/null 2>&1 || { echo 'ERRO: Docker não está instalado.' >&2; exit 14; }
docker compose version >/dev/null 2>&1 || { echo 'ERRO: Docker Compose v2 não está disponível.' >&2; exit 15; }
if grep -q 'CHANGE_ME' .env; then
  echo 'ERRO: substitua todos os valores CHANGE_ME do .env antes do deploy.' >&2
  exit 16
fi
git diff --quiet && git diff --cached --quiet || {
  echo 'ERRO: existem alterações locais em arquivos versionados na VPS. Resolva antes.' >&2
  exit 17
}

echo '[2/7] Salvando versão atual e preparando backup...'
PREVIOUS_COMMIT=$(git rev-parse HEAD)
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  echo 'Criando backup PostgreSQL...'
  docker compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "backups/postgres-$STAMP.sql"
  test -s "backups/postgres-$STAMP.sql" || { echo 'ERRO: backup PostgreSQL vazio.' >&2; exit 18; }
  echo "Backup criado: backups/postgres-$STAMP.sql"
else
  echo 'PostgreSQL ainda não está em execução; backup inicial não aplicável.'
fi

echo '[3/7] Atualizando código do GitHub...'
git fetch origin main
git switch main
git pull --ff-only origin main

echo '[4/7] Validando Docker Compose...'
docker compose config >/dev/null

echo '[5/7] Construindo e iniciando serviços...'
docker compose up -d --build

echo '[6/7] Aguardando API ficar saudável...'
API_READY=0
for attempt in $(seq 1 36); do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)" >/dev/null 2>&1; then
    API_READY=1
    break
  fi
  sleep 5
done

if [ "$API_READY" -ne 1 ]; then
  echo 'ERRO: API não ficou saudável. Últimos logs:' >&2
  docker compose ps >&2 || true
  docker compose logs --tail=100 api web edge livekit >&2 || true
  echo "Commit anterior: $PREVIOUS_COMMIT" >&2
  exit 19
fi

echo '[7/7] Estado final dos serviços:'
docker compose ps
echo "Deploy concluído. Commit anterior: $PREVIOUS_COMMIT"
'@

$RemoteScript = $RemoteScript.Replace('__VPS_PATH__', $VpsPath)
$RemoteBytes = [System.Text.Encoding]::UTF8.GetBytes($RemoteScript)
$RemoteBase64 = [Convert]::ToBase64String($RemoteBytes)
$RemoteCommand = "echo $RemoteBase64 | base64 -d | bash"
$Destination = "$VpsUser@$VpsHost"

Write-Host ''
Write-Host '===== CONECTANDO E PUBLICANDO NA VPS =====' -ForegroundColor Cyan

& $SshCommand.Source -i $SshKey -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 $Destination $RemoteCommand
if ($LASTEXITCODE -ne 0) {
    Stop-Deploy "SSH/deploy terminou com código $LASTEXITCODE. Confira a mensagem acima."
}

Write-Host ''
Write-Host '[SUCESSO] Horizon Voice atualizado na VPS.' -ForegroundColor Green
