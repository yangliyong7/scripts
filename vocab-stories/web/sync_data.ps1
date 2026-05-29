# Sync vocabulary data from parent data/ to web/data/
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "data"
$dst = Join-Path $PSScriptRoot "data"
Copy-Item (Join-Path $src "units.json") (Join-Path $dst "units.json") -Force
Copy-Item (Join-Path $src "word_to_unit.json") (Join-Path $dst "word_to_unit.json") -Force
Write-Host "Synced units.json and word_to_unit.json"
