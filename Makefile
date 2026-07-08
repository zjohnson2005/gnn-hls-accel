# APU characterization workflow (run from repo root).
#
# Linux/WSL:
#   export OPENAI_API_KEY=sk-...
#   make apu-gate
#
# Windows PowerShell (no make required):
#   .\apu_characterization\run_apu_gate.ps1

.PHONY: apu-bootstrap apu-gate apu-replicate-v3 apu-validate apu-replicate-check apu-replicate-unattended help

V3_ARTIFACT := apu_characterization/out/replication_remote_search_v3.json
VENV_ACTIVATE := . .venv-wsl/bin/activate

help:
	@echo "APU targets:"
	@echo "  apu-bootstrap            WSL venv + platform self-tests"
	@echo "  apu-gate                 bootstrap (if needed) + unit tests + FO-01 smoke"
	@echo "  apu-replicate-v3         full v3 replication (~1 hr) + validate"
	@echo "  apu-validate             validate latest v3 artifact"
	@echo "  apu-replicate-unattended start replication in background (Windows/WSL)"
	@echo "  apu-replicate-check      poll unattended run; validate when finished"

apu-bootstrap:
	bash apu_characterization/run_wsl_bootstrap.sh

apu-gate:
	bash apu_characterization/run_apu_gate.sh

apu-replicate-v3:
	bash apu_characterization/run_linux_replication_v3.sh

apu-validate:
	@test -f $(V3_ARTIFACT) || (echo "missing $(V3_ARTIFACT)"; exit 1)
	@$(VENV_ACTIVATE) && python apu_characterization/tools/validate_publishable.py $(V3_ARTIFACT)

apu-preflight:
	bash -c 'cd "$$(pwd)" && git config core.autocrlf true 2>/dev/null; . .venv-wsl/bin/activate && python apu_characterization/tools/apu_preflight.py'

apu-replicate-unattended:
	bash apu_characterization/run_apu_replicate_unattended.sh

apu-replicate-check:
	@$(VENV_ACTIVATE) && python apu_characterization/tools/apu_replicate_status.py --validate
