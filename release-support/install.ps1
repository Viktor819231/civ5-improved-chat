param(
    [string]$GamePath,
    [string]$PackageRoot = $PSScriptRoot,
    [switch]$NoShortcut,
    [switch]$ValidateOnly,
    [switch]$Elevated
)

$ErrorActionPreference = 'Stop'
$modGuid = 'c74fe31f-6834-496f-87dc-fb1c471b7fc8'

function Get-VerifiedGameRoot([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate) -or -not (Test-Path -LiteralPath $Candidate -PathType Container)) { return $null }
    $resolved = (Resolve-Path -LiteralPath $Candidate).ProviderPath.TrimEnd('\')
    $hasExe = @('CivilizationV.exe', 'CivilizationV_DX11.exe', 'CivilizationV_Tablet.exe') | Where-Object { Test-Path -LiteralPath (Join-Path $resolved $_) -PathType Leaf }
    if (-not $hasExe -or -not (Test-Path -LiteralPath (Join-Path $resolved 'Assets\DLC') -PathType Container)) { return $null }
    return $resolved
}

function Get-SteamGameRoots {
    $steamRoots = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in @(
        @{ Path = 'HKCU:\Software\Valve\Steam'; Property = 'SteamPath' },
        @{ Path = 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'; Property = 'InstallPath' },
        @{ Path = 'HKLM:\SOFTWARE\Valve\Steam'; Property = 'InstallPath' }
    )) {
        try {
            $value = (Get-ItemProperty -LiteralPath $entry.Path -ErrorAction Stop).($entry.Property)
            if ($value) { [void]$steamRoots.Add($value) }
        } catch { }
    }
    if (${env:ProgramFiles(x86)}) { [void]$steamRoots.Add((Join-Path ${env:ProgramFiles(x86)} 'Steam')) }
    if ($env:ProgramFiles) { [void]$steamRoots.Add((Join-Path $env:ProgramFiles 'Steam')) }
    $libraries = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($steamRoot in $steamRoots) {
        [void]$libraries.Add($steamRoot)
        $vdf = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf -PathType Leaf) {
            $content = Get-Content -LiteralPath $vdf -Raw
            foreach ($match in [regex]::Matches($content, '"path"\s+"([^"\r\n]+)"')) {
                [void]$libraries.Add($match.Groups[1].Value.Replace('\\', '\'))
            }
            # Older Steam versions use numbered entries with a library path.
            foreach ($match in [regex]::Matches($content, '"\d+"\s+"([A-Za-z]:\\[^"\r\n]+)"')) {
                [void]$libraries.Add($match.Groups[1].Value.Replace('\\', '\'))
            }
        }
    }
    foreach ($library in $libraries) {
        $common = Join-Path $library 'steamapps\common'
        $manifest = Join-Path $library 'steamapps\appmanifest_8930.acf'
        if (Test-Path -LiteralPath $manifest -PathType Leaf) {
            $content = Get-Content -LiteralPath $manifest -Raw
            $match = [regex]::Match($content, '"installdir"\s+"([^"\r\n]+)"')
            if ($match.Success) {
                $candidate = Get-VerifiedGameRoot (Join-Path $common $match.Groups[1].Value)
                if ($candidate) { $candidate }
            }
        }
        $candidate = Get-VerifiedGameRoot (Join-Path $common "Sid Meier's Civilization V")
        if ($candidate) { $candidate }
    }
}

function Assert-ModFolder([string]$Folder) {
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { throw 'The supplied InGameTranslateMod folder is missing. Extract the complete ZIP before running the installer.' }
    if (((Get-Item -LiteralPath $Folder -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'A mod source/destination is a link or junction. Installation stopped before scanning it.'
    }
    $manifests = @(Get-ChildItem -LiteralPath $Folder -Filter '*.Civ5Pkg' -File)
    if ($manifests.Count -eq 0) { throw 'The InGameTranslateMod folder is not a recognized Improved Chat package.' }
    foreach ($manifest in $manifests) {
        [xml]$xml = Get-Content -LiteralPath $manifest.FullName -Raw
        $guid = ([string]$xml.Civ5Package.GUID).Trim('{}').ToLowerInvariant()
        if ($guid -ne $modGuid) { throw 'An existing or supplied InGameTranslateMod folder contains an unrelated package. It was not overwritten.' }
    }
}

function Get-SafeTree([string]$Folder) {
    $rootItem = Get-Item -LiteralPath $Folder -Force
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A mod source/destination is a link or junction. Installation stopped.' }
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($rootItem.FullName)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $current -Force)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A mod source/destination contains a link or junction. Installation stopped.' }
            $item
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

function Get-OtherImprovedChatCopies([string]$DlcFolder, [string]$CanonicalFolder) {
    $canonical = [IO.Path]::GetFullPath($CanonicalFolder).TrimEnd('\')
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $found = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $rootItem = Get-Item -LiteralPath $DlcFolder -Force
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'The DLC folder is a link or junction. Choose the real game installation folder instead.' }
    $pending.Push($rootItem.FullName)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        if ($current.Equals($canonical, [StringComparison]::OrdinalIgnoreCase)) { continue }
        foreach ($item in @(Get-ChildItem -LiteralPath $current -Force)) {
            # Never follow destination junctions into other folders/drives.
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            if ($item.PSIsContainer) { $pending.Push($item.FullName); continue }
            if ($item.Extension -ine '.Civ5Pkg') { continue }
            try {
                [xml]$xml = Get-Content -LiteralPath $item.FullName -Raw
                $guid = ([string]$xml.Civ5Package.GUID).Trim('{}').ToLowerInvariant()
                if ($guid -eq $modGuid) { [void]$found.Add($item.DirectoryName) }
            } catch {
                # Other packages are not ours to repair, overwrite or remove.
                continue
            }
        }
    }
    return @($found)
}

function Test-WriteAccess([string]$Folder) {
    $probe = Join-Path $Folder ('igt-write-check-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $stream = [IO.File]::Open($probe, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Dispose()
        Remove-Item -LiteralPath $probe -Force
        return $true
    } catch [UnauthorizedAccessException] { return $false }
}

function Get-Sha256File([string]$FilePath) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($FilePath)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Copy-VerifiedMod([string]$Source, [string]$Destination) {
    $sourceRoot = (Resolve-Path -LiteralPath $Source).ProviderPath.TrimEnd('\')
    $destinationRoot = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
    $prefix = $destinationRoot + '\'
    $items = @(Get-SafeTree $sourceRoot)
    if (Test-Path -LiteralPath $destinationRoot) {
        Assert-ModFolder $destinationRoot
        [void]@(Get-SafeTree $destinationRoot)
    }
    [void][IO.Directory]::CreateDirectory($destinationRoot)
    $files = @($items | Where-Object { -not $_.PSIsContainer })
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($sourceRoot.Length + 1)
        $target = [IO.Path]::GetFullPath((Join-Path $destinationRoot $relative))
        if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'An invalid destination path was rejected.' }
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
        if (-not $sourceRoot.Equals($destinationRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        }
        if ((Get-Sha256File $file.FullName) -ne (Get-Sha256File $target)) {
            throw ('Installed file verification failed: ' + $relative)
        }
    }
    if ($sourceRoot.Equals($destinationRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Host ('Already installed in this folder; verified ' + $files.Count + ' files without copying them onto themselves.')
    } else { Write-Host ('Installed and verified ' + $files.Count + ' files.') }
}

function Install-WithElevation([string]$VerifiedGame, [string]$Package) {
    Write-Host 'Windows needs administrator permission to write to the game folder. A normal Windows UAC prompt will appear.'
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath),
        '-GamePath', ('"{0}"' -f $VerifiedGame), '-PackageRoot', ('"{0}"' -f $Package), '-Elevated', '-NoShortcut')
    $process = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Administrator installation did not complete. You can install manually using README.txt.' }
}

try {
    if (@(Get-Process -Name 'CivilizationV', 'CivilizationV_DX11', 'CivilizationV_Tablet' -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'Civilization V is running. Exit it completely, then run this installer again. The installer will not close your game.'
    }
    $package = (Resolve-Path -LiteralPath $PackageRoot).ProviderPath
    $source = Join-Path $package 'InGameTranslateMod'
    Assert-ModFolder $source
    if ($GamePath) {
        $gameRoot = Get-VerifiedGameRoot $GamePath
        if (-not $gameRoot) { throw 'The selected folder is not a verified Civilization V installation (game executable and Assets\DLC required).' }
    } else {
        $candidates = @(Get-SteamGameRoots | Select-Object -Unique)
        if ($candidates.Count -eq 1) { $gameRoot = $candidates[0] }
        if (-not $gameRoot) {
            Add-Type -AssemblyName System.Windows.Forms
            $picker = New-Object System.Windows.Forms.FolderBrowserDialog
            $picker.Description = 'Choose your Civilization V game folder (the folder containing CivilizationV.exe and Assets).'
            $picker.ShowNewFolderButton = $false
            try {
                if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No game folder selected. Nothing was installed.' }
                $gameRoot = Get-VerifiedGameRoot $picker.SelectedPath
            } finally { $picker.Dispose() }
            if (-not $gameRoot) { throw 'The chosen folder is not a verified Civilization V installation.' }
        }
    }
    $dlcRoot = Join-Path $gameRoot 'Assets\DLC'
    $destination = Join-Path $dlcRoot 'InGameTranslateMod'
    $otherCopies = @(Get-OtherImprovedChatCopies $dlcRoot $destination)
    if ($otherCopies.Count -gt 0) {
        throw ("Another Improved Chat copy was found outside the expected installation folder:`n" +
            ($otherCopies -join "`n") +
            "`nWith Civ V closed, move the old Improved Chat mod folder(s) outside Assets\DLC, then run this installer again. Do not remove other DLC. If you copied the whole extracted beta into DLC, move that beta folder outside DLC first.")
    }
    if ($ValidateOnly) {
        Write-Host ('Validated package and game. Installation target: ' + $destination)
        exit 0
    }
    if (Test-Path -LiteralPath $destination) { Assert-ModFolder $destination }
    $sameFolder = [IO.Path]::GetFullPath($source).TrimEnd('\').Equals([IO.Path]::GetFullPath($destination).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)
    if ($sameFolder) {
        Copy-VerifiedMod $source $destination
    } elseif (-not (Test-WriteAccess $dlcRoot)) {
        if ($Elevated) { throw 'Windows still denied access to the game folder. Install manually or check folder permissions.' }
        Install-WithElevation $gameRoot $package
    } else {
        try { Copy-VerifiedMod $source $destination }
        catch [UnauthorizedAccessException] {
            if ($Elevated) { throw }
            Install-WithElevation $gameRoot $package
        }
    }
    if (-not $NoShortcut) {
        $companion = Join-Path $package 'InGameTranslateCompanion.exe'
        if (Test-Path -LiteralPath $companion -PathType Leaf) {
            $desktop = [Environment]::GetFolderPath('DesktopDirectory')
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut((Join-Path $desktop 'Improved Chat.lnk'))
            $shortcut.TargetPath = $companion
            $shortcut.WorkingDirectory = $package
            $shortcut.Description = 'Improved Chat translation companion for Civilization V'
            $shortcut.Save()
            Write-Host 'Created the Improved Chat desktop shortcut.'
        }
    }
    Write-Host ('Improved Chat is installed in: ' + $destination)
    Write-Host 'Keep this extracted folder. Open InGameTranslateCompanion.exe, click Enable online translation, then start Civ V.'
    exit 0
} catch {
    Write-Host ('Installation stopped: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
