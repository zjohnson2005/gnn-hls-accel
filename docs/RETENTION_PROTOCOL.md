# Retention protocol

The builder is `seam.retention_prompt.build_cell`. It does not open a
preregistration. Prediction files for these outcomes live under
`derived/retention/` and are attached at scoring time.

## SEMANTIC

The prompt is the required spans of the source, in document order. Nothing
is inserted in the gaps. The resident token count of that prompt must equal
the POSITIONAL budget for the cell. A mismatch refuses the cell before any
device call.

## OBS_MASK

OBS_MASK runs beside SEMANTIC. For each observation, keep the first K
whitespace tokens and drop the rest. Add no marker. Record K on the cell.

## Residency interaction

Cross retention with residency. The four cells are SEMANTIC and the
unreduced source, each under RESIDENT and NON_RESIDENT, on the same
positional budget. The outcome is the pair of turn-1 prefill times, or the
pair of TTFT limits, on that cross. The protocol does not register a
numeric delta.

## Interaction cost

Interaction cost is the resident-token gap between the unreduced source and
the positional budget, together with the measured prefill-time gap between
those two prompts on the same residency. Both numbers are recorded from the
run. Neither is given a predicted value in this protocol.
