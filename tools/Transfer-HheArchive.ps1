#Requires -Version 5.1
<#[ Windows PowerShell 5.1 / PowerShell 7; Docker Desktop is the only runtime. ]#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Export', 'Restore')][string]$Mode,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$ProjectName,
    [string]$ArchivePath,
    [string]$BackupDirectory,
    [string[]]$ComposeFile = @('docker-compose.yml'),
    [switch]$ConfirmRestore,
    [switch]$AllowVersionMismatch
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$OriginalLocation = Get-Location
$script:ComposeArgs = @('compose', '-p', $ProjectName)
foreach ($File in $ComposeFile) { $script:ComposeArgs += @('-f', $File) }
$TemporaryFolders = [System.Collections.Generic.List[string]]::new()
$TemporaryDatabases = [System.Collections.Generic.List[string]]::new()
$StoppedServices = @()
$WritersStopped = $false
$PhotosInstallAttempted = $false
$CutoverAttempted = $false
$DatabaseSwitched = $false
$TransferSucceeded = $false
$RestoreWork = $null
$SafetyArchive = $null
$OldDatabase = $null
$DbUser = $null
$DbName = $null
$TransferLock = $null

function Invoke-Docker([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker ha restituito un errore (codice $LASTEXITCODE)." }
}
function Invoke-Compose([string[]]$Arguments) {
    Invoke-Docker ($script:ComposeArgs + $Arguments)
}
function New-WorkDirectory {
    $Path = Join-Path $BackupDirectory ('.hhe-transfer-' + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $Path)
    $TemporaryFolders.Add($Path)
    return $Path
}
function Invoke-Helper([string]$Operation, [string]$Work) {
    $Helper = Join-Path $PSScriptRoot 'transfer_archive.py'
    Invoke-Compose @('run', '--rm', '--no-deps', '-T', '--volume', "${Work}:/transfer",
        '--volume', "${Helper}:/tmp/hhe-transfer.py:ro", 'api', 'python', '/tmp/hhe-transfer.py', $Operation) | Out-Host
}
function Invoke-Db([string[]]$Arguments) {
    Invoke-Compose (@('exec', '-T', 'db') + $Arguments)
}
function Start-PreviousServices {
    foreach ($Service in @('api', 'web')) {
        if ($StoppedServices -notcontains $Service) { continue }
        Invoke-Compose @('start', $Service) | Out-Host
        $Id = (Invoke-Compose @('ps', '-a', '-q', $Service)).Trim()
        $Deadline = (Get-Date).AddSeconds(100)
        do {
            $State = Invoke-Docker @('inspect', '--format={{json .State}}', $Id) | ConvertFrom-Json
            if (-not $State.Running) { throw "Il servizio $Service non e ripartito." }
            $HasHealth = $State.PSObject.Properties.Name -contains 'Health'
            if (-not $HasHealth -or $State.Health.Status -eq 'healthy') { break }
            if ((Get-Date) -ge $Deadline -or $State.Health.Status -eq 'unhealthy') {
                throw "Il controllo di salute di $Service non e riuscito."
            }
            Start-Sleep -Seconds 2
        } while ($true)
    }
}
function Invoke-Sql([string]$Sql, [string]$Work) {
    $Local = Join-Path $Work 'operation.sql'
    $Remote = '/tmp/hhe-operation-' + [guid]::NewGuid().ToString('N') + '.sql'
    [System.IO.File]::WriteAllText($Local, $Sql, [System.Text.UTF8Encoding]::new($false))
    try {
        Invoke-Compose @('cp', $Local, "db:$Remote") | Out-Host
        Invoke-Db @('psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', $DbUser, '-d', 'postgres', '-f', $Remote) | Out-Host
    } finally {
        Invoke-Db @('rm', '-f', $Remote) | Out-Host
    }
}
function Export-Snapshot([string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Il file esiste gia: $Destination" }
    $Work = New-WorkDirectory
    $Remote = '/tmp/hhe-transfer-' + [guid]::NewGuid().ToString('N') + '.dump'
    $Metadata = @{ project = $ProjectName; git_commit = $GitCommit; git_dirty = $GitDirty; postgres_major = $PgMajor }
    $Metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Work 'metadata.json') -Encoding UTF8
    try {
        # Binary data never passes through a PowerShell pipe or redirection.
        Invoke-Db @('pg_dump', '-U', $DbUser, '-d', $DbName, '--format=custom', '--no-owner', '--no-privileges', '--file', $Remote) | Out-Host
        Invoke-Db @('pg_restore', '--list', $Remote) | Out-Null
        Invoke-Compose @('cp', "db:$Remote", (Join-Path $Work 'database.dump')) | Out-Host
        Invoke-Helper 'pack' $Work
        Move-Item -LiteralPath (Join-Path $Work 'archive.hhe-backup.tar.gz') -Destination $Destination
        Write-Host "Backup salvato: $Destination"
    } finally {
        Invoke-Db @('rm', '-f', $Remote) | Out-Host
    }
}

try {
    Set-Location -LiteralPath $RepoRoot
    $LockPath = Join-Path $RepoRoot ('.hhe-transfer-' + $ProjectName + '.lock')
    try {
        $TransferLock = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch {
        throw "Un altro trasferimento e gia in corso per $ProjectName in questa cartella."
    }
    if (-not $BackupDirectory) { $BackupDirectory = Join-Path $RepoRoot 'backups' }
    $BackupDirectory = [System.IO.Path]::GetFullPath($BackupDirectory)
    [void](New-Item -ItemType Directory -Force -Path $BackupDirectory)
    Invoke-Compose @('config', '--quiet') | Out-Host
    foreach ($Service in @('db', 'api', 'web')) {
        $Ids = @(Invoke-Compose @('ps', '-a', '-q', $Service))
        if ($Ids.Count -ne 1 -or -not $Ids[0]) {
            throw "Servizio $Service non trovato nel progetto $ProjectName. Avvia prima: docker compose -p $ProjectName up --build -d --wait"
        }
        $Running = (Invoke-Docker @('inspect', '--format={{.State.Running}}', $Ids[0])).Trim()
        if ($Service -eq 'db' -and $Running -ne 'true') { throw 'Il database deve essere avviato prima del trasferimento.' }
        if ($Service -ne 'db' -and $Running -eq 'true') { $StoppedServices += $Service }
    }
    $DbUser = (Invoke-Db @('printenv', 'POSTGRES_USER')).Trim()
    $DbName = (Invoke-Db @('printenv', 'POSTGRES_DB')).Trim()
    if ($DbUser -notmatch '^[A-Za-z_][A-Za-z0-9_]*$' -or $DbName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        throw 'Questi strumenti richiedono nomi PostgreSQL alfanumerici con underscore.'
    }
    $PgVersion = (Invoke-Db @('psql', '-X', '-At', '-U', $DbUser, '-d', $DbName, '-c', 'SHOW server_version_num')).Trim()
    $PgMajor = [int][math]::Floor(([int]$PgVersion) / 10000)
    $GitCommit = $null
    $GitDirty = $false
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $GitCommit = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Impossibile leggere la versione Git.' }
        $GitDirty = [bool](& git status --porcelain --untracked-files=no)
    }
    if ($Mode -eq 'Restore') {
        if (-not $ArchivePath -or -not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw 'Indica il backup da ripristinare con -ArchivePath.' }
        if (-not $ConfirmRestore) {
            throw "Il ripristino sostituisce database e foto del progetto $ProjectName, salvandone prima una copia. Aggiungi -ConfirmRestore per procedere."
        }
        $RestoreWork = New-WorkDirectory
        Copy-Item -LiteralPath $ArchivePath -Destination (Join-Path $RestoreWork 'input.hhe-backup.tar.gz')
        Invoke-Helper 'unpack' $RestoreWork
        $Manifest = Get-Content -LiteralPath (Join-Path $RestoreWork 'verified-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Manifest.postgres_major -ne $PgMajor) { throw 'Versioni PostgreSQL diverse: usare la stessa versione principale sui due computer.' }
        if (-not $AllowVersionMismatch -and ($GitDirty -or $Manifest.git_dirty -or -not $GitCommit -or
            -not $Manifest.git_commit -or $GitCommit -ne $Manifest.git_commit)) {
            throw 'Versioni del codice diverse/non identificabili o modifiche locali. Aggiorna entrambi i PC alla stessa revisione Git, oppure usa consapevolmente -AllowVersionMismatch.'
        }
    } else {
        if (-not $ArchivePath) { $ArchivePath = Join-Path $BackupDirectory ("hhe-$ProjectName-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.hhe-backup.tar.gz') }
        $ArchivePath = [System.IO.Path]::GetFullPath($ArchivePath)
        if (Test-Path -LiteralPath $ArchivePath) { throw "Il file esiste gia: $ArchivePath" }
        if (-not (Test-Path -LiteralPath (Split-Path $ArchivePath -Parent) -PathType Container)) { throw 'La cartella di destinazione non esiste.' }
    }

    Write-Host "Progetto: $ProjectName. Arresto temporaneo di API e frontend per una copia coerente."
    # Mark before stopping: even a partial stop must resume services in finally.
    $WritersStopped = $true
    if ($StoppedServices.Count) { Invoke-Compose (@('stop', '--timeout', '45') + $StoppedServices) | Out-Host }
    if ($Mode -eq 'Export') {
        Export-Snapshot $ArchivePath
    } else {
        $SafetyArchive = Join-Path $BackupDirectory ("prima-del-ripristino-$ProjectName-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8) + '.hhe-backup.tar.gz')
        Export-Snapshot $SafetyArchive
        $Token = [guid]::NewGuid().ToString('N')
        $StagedDatabase = 'hhe_incoming_' + $Token
        $OldDatabase = 'hhe_previous_' + $Token
        $TemporaryDatabases.Add($StagedDatabase)
        $RemoteDump = "/tmp/hhe-incoming-$Token.dump"
        try {
            Invoke-Db @('createdb', '-U', $DbUser, '--template=template0', $StagedDatabase) | Out-Host
            Invoke-Compose @('cp', (Join-Path $RestoreWork 'validated/database.dump'), "db:$RemoteDump") | Out-Host
            # Load and validate the complete dump in a separate DB before touching the destination.
            Invoke-Db @('pg_restore', '-U', $DbUser, '--dbname', $StagedDatabase, '--no-owner', '--no-privileges', '--exit-on-error', '--single-transaction', $RemoteDump) | Out-Host
            $PhotosInstallAttempted = $true
            Invoke-Helper 'install' $RestoreWork
            $CutoverAttempted = $true
            Invoke-Sql @"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$DbName', '$StagedDatabase') AND pid <> pg_backend_pid();
BEGIN;
ALTER DATABASE "$DbName" RENAME TO "$OldDatabase";
ALTER DATABASE "$StagedDatabase" RENAME TO "$DbName";
COMMIT;
"@ $RestoreWork
            $DatabaseSwitched = $true
            [void]$TemporaryDatabases.Remove($StagedDatabase)
            Write-Host "Database e fotografie ripristinati. Copia precedente: $SafetyArchive"
        } finally {
            Invoke-Db @('rm', '-f', $RemoteDump) | Out-Host
        }
    }
    $TransferSucceeded = $true
} catch {
    # Restore old photos if cutover failed; the old DB was never replaced.
    if ($PhotosInstallAttempted -and -not $DatabaseSwitched -and $SafetyArchive) {
        try {
            # If COMMIT succeeded but the client lost the acknowledgement, do
            # not put old photos alongside a database that already switched.
            if ($CutoverAttempted) {
                $Exists = (Invoke-Db @('psql', '-X', '-At', '-U', $DbUser, '-d', 'postgres', '-c',
                    "SELECT count(*) FROM pg_database WHERE datname='$OldDatabase'")).Trim()
                if ($Exists -eq '1') { throw 'Cambio database gia avvenuto; controllare prima di riavviare.' }
            }
            $Recovery = New-WorkDirectory
            Copy-Item -LiteralPath $SafetyArchive -Destination (Join-Path $Recovery 'input.hhe-backup.tar.gz')
            Invoke-Helper 'unpack' $Recovery
            Invoke-Helper 'install' $Recovery
            Write-Host 'Ripristinate le fotografie precedenti; database originale conservato.'
        } catch {
            $WritersStopped = $false
            Write-Warning "Recupero fotografie fallito. API/frontend lasciati fermi. Ripristina il backup: $SafetyArchive"
        }
    }
    throw
} finally {
    foreach ($Database in $TemporaryDatabases) {
        try { Invoke-Db @('dropdb', '-U', $DbUser, '--if-exists', $Database) | Out-Host } catch { Write-Warning "Database temporaneo conservato: $Database" }
    }
    try {
        if ($WritersStopped -and $StoppedServices.Count) {
            Start-PreviousServices
        }
        if ($TransferSucceeded -and $DatabaseSwitched) {
            Invoke-Db @('dropdb', '-U', $DbUser, $OldDatabase) | Out-Host
        }
    } catch {
        Write-Warning 'Avvio dei servizi o pulizia non riuscito: verifica docker compose ps -a e logs. Il backup precedente resta disponibile.'
        throw
    } finally {
        foreach ($Folder in $TemporaryFolders) {
            try {
                if (Test-Path -LiteralPath $Folder) { Remove-Item -LiteralPath $Folder -Recurse -Force }
            } catch { Write-Warning "Cartella temporanea da rimuovere manualmente: $Folder" }
        }
        if ($TransferLock) { $TransferLock.Dispose() }
        Set-Location $OriginalLocation
    }
}
