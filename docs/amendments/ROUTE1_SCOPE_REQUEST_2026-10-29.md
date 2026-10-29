# ROUTE-1 scope request (split by question), 2026-10-29

Filed 2026-10-29 (Task BT) with docs/amendments/HYB1_AMEND_2026-10-29_ROUTE1_SAVINGS.md. Written replies are
requested by Tue Nov 3. If there is no written agreement by Thu Nov 5, 11:59 PM ET, DR-R7 applies: ROUTE-1
still runs, but its results stay out of the ISPASS paper.

## Split by question
ISPASS asks what the ceiling model is worth. It evaluates one fixed, non-learned, feasibility-only
configure-and-plan rule, on the memory-bound XPS with OpenVINO, on tau2, BFCL and TraceLab. It reports
oracle-gap and $ vs D1/D2 in a subsection of section 8.2 of about 0.6 page. The router paper asks which policy
routes each request and what it costs: learned, difficulty- and quality-aware, mid-session re-routing,
deployment, and matched-quality savings on its own hardware and traces. It consumes the ceiling model as a
feature. Neither paper reports a cost number on the other's traces and hardware. Each cites the other.

## Proposed wording, ISPASS
"We use the ceiling model to plan each agent session at start: it selects the device configuration and the
planned migration turn. The rule is fixed and feasibility-only, with no difficulty or quality model. We
evaluate it as the value of runtime-feasibility information against default hybrid routers. Learned,
quality-aware routing that combines feasibility with task difficulty is the subject of concurrent work
[Sharma et al., under submission] and is out of scope."

## Proposed wording, router paper
"Feasibility features and the per-session configuration plan come from the measured ceiling model of
[Johnson et al., under submission]. We do not re-derive or re-evaluate it, and we report no cost results on
its hardware or traces."

## Replies (paste the written answers verbatim, with date and time ET)
Rithwik Sharma reply:

Dr. Cong Hao reply:
