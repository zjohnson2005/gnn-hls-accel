"""Phase 0/1 characterization — disaggregate the CPU-side agentic latency bucket.

Import submodules directly (e.g. ``orchestration_engine.characterization.taxonomy``).
This package intentionally avoids eager imports so phase2 utilities
(``regen_cost_model``, ``energy_calc``) run on hosts where default python3 is 3.6.
"""
