# Crea .env.real con claves aleatorias para la instalacion REAL. Uso: crear_env_real.ps1 <ruta de .env.real>
param([Parameter(Mandatory = $true)][string]$Destino)
$ErrorActionPreference = 'Stop'
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
function NuevoHex([int]$n) {
    $b = New-Object byte[] $n
    $rng.GetBytes($b)
    return ([System.BitConverter]::ToString($b)).Replace('-', '').ToLower()
}
$k = New-Object byte[] 32
$rng.GetBytes($k)
$fernet = [System.Convert]::ToBase64String($k).Replace('+', '-').Replace('/', '_')
$lineas = @(
    'POSTGRES_USER=sistema',
    ('POSTGRES_PASSWORD=' + (NuevoHex 24)),
    'POSTGRES_DB=sistema_propio',
    'APP_ENV=production',
    'AUTH_MODE=local',
    ('SESSION_SECRET=' + (NuevoHex 32)),
    ('FIELD_ENCRYPTION_KEY=' + $fernet),
    'COOKIE_SECURE=true',
    'COPIAS_DIR=./copias_real',
    'OWN_TAX_IDS='
)
[System.IO.File]::WriteAllLines($Destino, [string[]]$lineas)
$txt = [System.IO.File]::ReadAllText($Destino)
if ($txt -notmatch 'SESSION_SECRET=[0-9a-f]{64}' -or $txt -notmatch 'POSTGRES_PASSWORD=[0-9a-f]{48}' -or $txt -notmatch 'FIELD_ENCRYPTION_KEY=[A-Za-z0-9_\-]{43}=') {
    Remove-Item $Destino
    Write-Error 'No se han podido generar las claves.'
    exit 1
}
Write-Output 'Claves creadas.'
exit 0
