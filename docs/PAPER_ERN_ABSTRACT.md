# ERN abstract (Zach's personal configuration research) - as given by Zach, 2026-10-15 (verbatim)
# NOTE (Zach): numbers date to 2026-09-07 (current data then) and will be refreshed.

A language model agent can run in the cloud, where every call is billed and the user's data
leaves the device, or on the device, where it costs nothing and stays private but is bounded
by the hardware. Hybrid execution does both and picks, per request, which side handles the
work. That choice is normally made from the task and the model, treating the device as
fixed. On one machine running one model, configuration determines whether local execution
is possible at all, so a router that cannot see it works from incomplete information. We are
building a design space exploration over hardware configuration, across four objectives that
trade against one another: turn latency, memory cost, task quality, and how much context
the device holds before it fails. Our hypothesis is that no configuration wins on all four,
because the axes move different objectives, so the space needs a search rather than a set of
Defaults.

We measure six axes on a 16 GB Intel Core Ultra laptop running Qwen3-4B under OpenVINO
GenAI: device placement, session residency, cache precision, weight precision, attention
window, and model size. We fixed the latency target before collecting data: first token under
10 s, decode above 6 tokens per second. Task quality comes from 200 entries of the Berkeley
Function Calling Leaderboard v4 multi-turn benchmark, scored by its own checker, which
passes all 200 gold cases. Every cell reads its cache precision back from the runtime, and we
discard the ones whose reading disagrees. Compared arms run interleaved in one session, so
machine state cannot explain the difference.

Each axis we measured moves a different objective. Placement and residency change latency
and leave memory alone. Together they take the share of turns meeting the target from 0%
to 100% on fixed hardware. Cache precision runs the opposite way. Dropping from 16-bit to
8-bit halves cache bytes per token and buys context, but the quantized arms pay
dequantization, so 16-bit still runs prefill 15 to 27 percent faster at depth. Weight precision
costs memory and speed. INT8 holds 1.76 GB more resident memory and decodes 1.3 to 1.5
times slower than INT4. What it returns is a narrow slice of quality. The two complete the
same fraction of tasks (10.0% vs 11.5%, McNemar p = 0.55), but INT4 emits no parseable
tool call on 32 entries where INT8 emits one, against 7 the other way (odds ratio 4.57, p = 7
x 10^-5).

No setting wins on all four objectives, so hybrid routing should account for configuration,
and that configuration has to be searched rather than assumed. Next we characterize the
remaining axes and extend to 64 GB hardware, then run the search over the curves.
