# APU characterization workflow (run from repo root).
#
# Linux/WSL:
#   export OPENAI_API_KEY=sk-...
#   make apu-gate
#
# Windows PowerShell (no make required):
#   .\apu_characterization\run_apu_gate.ps1

.PHONY: apu-bootstrap apu-gate apu-replicate-v3 apu-validate apu-validate-sweep apu-replicate-check apu-replicate-unattended cap-gate tlp-gate mcp-bootstrap mcp-preflight mcp-gate mcp-matrix-plan mcp-postprocess mcp-validate mcp-bare-metal mcp-clean help

V3_ARTIFACT := apu_characterization/out/replication_remote_search_v3.json
SWEEP_ARTIFACT := apu_characterization/out/concurrency_sweep.json
MCP_ARTIFACT := apu_characterization/out/mcp_tax/mcp_tax.matrix.json
MCP_RUN_ROOT ?= apu_characterization/out/mcp_tax/runs
VENV_ACTIVATE := . .venv-wsl/bin/activate

help:
	@echo "APU targets:"
	@echo "  apu-bootstrap            WSL venv + platform self-tests"
	@echo "  apu-gate                 bootstrap (if needed) + unit tests + FO-01 smoke"
	@echo "  apu-replicate-v3         full v3 replication (~1 hr) + validate"
	@echo "  apu-validate             validate latest v3 artifact"
	@echo "  apu-validate-sweep       validate live concurrency_sweep.json"
	@echo "  apu-replicate-unattended start replication in background (Windows/WSL)"
	@echo "  apu-replicate-check      poll unattended run; validate when finished"
	@echo "  cap-gate                 CAP-01 v2 unit and contract gate"
	@echo "  tlp-gate                 TLP-01 unit and contract gate"
	@echo "  mcp-bootstrap            install exact MCP-01 dependency lock"
	@echo "  mcp-preflight            verify complete MCP-01 source/runtime bundle"
	@echo "  mcp-gate                 MCP-01 unit and integration-contract gate"
	@echo "  mcp-matrix-plan          print frozen serial MCP-01 matrix"
	@echo "  mcp-postprocess          analyze retained runs and validate artifacts"
	@echo "  mcp-validate             validate completed MCP-01 matrix"
	@echo "  mcp-bare-metal           launch serial matrix (native Linux only)"

apu-bootstrap:
	bash apu_characterization/run_wsl_bootstrap.sh

apu-gate:
	bash apu_characterization/run_apu_gate.sh

apu-replicate-v3:
	bash apu_characterization/run_linux_replication_v3.sh

apu-validate:
	@test -f $(V3_ARTIFACT) || (echo "missing $(V3_ARTIFACT)"; exit 1)
	@$(VENV_ACTIVATE) && python apu_characterization/tools/validate_publishable.py $(V3_ARTIFACT)

apu-validate-sweep:
	@test -f $(SWEEP_ARTIFACT) || (echo "missing $(SWEEP_ARTIFACT)"; exit 1)
	@$(VENV_ACTIVATE) && python apu_characterization/tools/validate_sweep.py $(SWEEP_ARTIFACT)

apu-preflight:
	bash -c 'cd "$$(pwd)" && git config core.autocrlf true 2>/dev/null; . .venv-wsl/bin/activate && python apu_characterization/tools/apu_preflight.py'

apu-replicate-unattended:
	bash apu_characterization/run_apu_replicate_unattended.sh

apu-replicate-check:
	@$(VENV_ACTIVATE) && python apu_characterization/tools/apu_replicate_status.py --validate

cap-gate:
	bash apu_characterization/run_cap01_gate.sh

tlp-gate:
	bash apu_characterization/run_tlp01_gate.sh

mcp-bootstrap:
	bash apu_characterization/bootstrap_mcp.sh

mcp-preflight:
	@$(VENV_ACTIVATE) && python apu_characterization/tools/check_mcp_bundle.py

mcp-gate:
	bash apu_characterization/run_mcp_gate.sh

mcp-matrix-plan:
	@$(VENV_ACTIVATE) && python -m apu_characterization.experiments.mcp_tax_matrix

mcp-postprocess:
	bash apu_characterization/postprocess_mcp.sh $(MCP_RUN_ROOT)

mcp-validate:
	@test -f $(MCP_ARTIFACT) || (echo "missing $(MCP_ARTIFACT)"; exit 1)
	@$(VENV_ACTIVATE) && python apu_characterization/tools/validate_mcp_tax.py $(MCP_ARTIFACT)

mcp-bare-metal:
	bash apu_characterization/run_mcp_bare_metal.sh

mcp-clean:
	@rm -rf apu_characterization/out/mcp_tax/_integration_one \
		apu_characterization/out/mcp_tax/_integration_sdk \
		apu_characterization/out/mcp_tax/_pid_check \
		apu_characterization/out/mcp_tax/.measurement.lock \
		apu_characterization/out/mcp_tax/runs/.measurement.lock \
		apu_characterization/out/mcp_tax/debug_smoke_integration/.measurement.lock
