# Approvals and inputs, Mon Oct 26 2026 evening (Task BS)

Recorded Mon Oct 26 2026, about 8:55 PM ET (Task BS). Source: the "Context" section of
~/seam_closeout_1013/papers_20261015/TASK_BS_RITHWIK_RUNBOOKS.md, which gives Rithwik's reply as Zach
relayed it. Rithwik's original message is not in this repo; the lines below are verbatim from the task file,
not from his message. If Zach has the original, it should be added below these lines (not replace them).

## Rithwik's reply (Mon Oct 26 2026 evening, as relayed in the task file, verbatim)
- RTX 4070 is his personal laptop: he runs our specs himself and sends logs + screenshots. Needs exact
  commands and a folder layout.
- Strix Halo (evo-x2) runs his job queue: he runs our specs as queued jobs, no direct access. Needs specs and
  gives us a slot.
- vLLM needs Linux (WSL/Docker) on these Windows machines; on evo-x2 that means admin changes + reboot. Not OK.
  llama.cpp is fine on both.
- 64 GB T2S: one evening OK, to be picked around his runs.
- He will send the T2S Shared GPU Memory Override value, retention run_ids and the E1/E2 task source.
- He proposes splitting "the formula" and "the router" between the two papers (discussed Tue Oct 27, 8 PM).

## Zach's instruction (Task BS message, Mon Oct 26 2026 ~8:35 PM ET, verbatim)
"Run ~/seam_closeout_1013/papers_20261015/TASK_BS_RITHWIK_RUNBOOKS.md end to end. Mac only, no ssh, $0,
commit locally only, no Claude attribution, never edit a script a running queue reads, launch nothing. End
with the push command, the two runbook zips/PDFs to send Rithwik, and the meeting note path."

## What this covers (docs/registrations/BS_XRT_RUNBOOKS_2026-10-26.md)
- E4 (vLLM) NOT RUN (deviation, reason above). E3 on the 4070 and E5a on the evo-x2 from pinned runbooks
  that Rithwik operates. E5b only if Rithwik says share changes are OK. The T2S evening is optional and
  needs his OK for the evening he picks and for the llama.cpp folder install (R-T2S-LLAMA).
- New downloads named in the runbooks (CUDA 12.4 + cudart zips; ROCm zip optional) run on Rithwik's
  machines at his choice; nothing is downloaded on our hosts by this task.
- The paper split is NOT decided here: docs/MEETING_RITHWIK_2026-10-27.md is a starting point; Zach decides.
