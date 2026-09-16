$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$env:PYTHONPATH = $Repo

py -3 -m pytest -q apu_characterization/tests/oa01
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

py -3 -c "import json; from pathlib import Path; from apu_characterization.oa01 import PROTOCOL_VERSION, SUBJECT_COMMIT; from apu_characterization.oa01.manifest import validate_manifest; p=json.loads(Path('apu_characterization/oa01/protocol_oa01_v1.json').read_text()); m=json.loads(Path('apu_characterization/oa01/task_manifest.json').read_text()); assert p['protocol_version']==PROTOCOL_VERSION; assert p['status']=='pre_registered_locked'; assert p['subject']['commit']==SUBJECT_COMMIT; assert p['task_manifest_sha256']==m['manifest_sha256']; assert not validate_manifest(m); print('OA-01 protocol and pre-registration lock OK')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

py -3 -m apu_characterization.oa01.runner --phase S
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

