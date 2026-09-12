# SEAM — opening pitch

Delivery script. ~7 minutes spoken. Written for the lab/advisor meeting on the new direction.
Compression notes for other audiences at the end.

Every measured number below is real and cited to a run. Anything illustrative is marked.

---

## 1. The question (60 seconds — say this almost verbatim)

"An OEM is speccing an AI PC for 2028. Their target workload is a personal agent — it plans,
retrieves, calls tools, writes. They have a fixed die budget and they have to choose: more unified
memory, or a wider NPU.

Nobody can answer that question. Not the routing literature, because it assumes the hardware is
given. Not the accelerator literature, because it assumes the workload runs locally and finishes.
Not the vendors, because their TCO spreadsheets aren't workload-parametric.

And it's a real decision with real money on it — at fleet scale the NPU block is on the order of
ten dollars a unit, so 'do we need it' is an eight-figure question that is currently answered by
intuition.

That's the question that pays for the work. But it's a symptom of something we don't understand,
and the thing we don't understand is what I actually want to go after."

## 2. Why it is hard — three channels

"The reason it's hard is that silicon reaches the agent through three separate channels, and they
don't move together.

**Capacity — what is possible at all.** The KV cache on our platform is 73,728 bytes per token —
read back from the device, because the model config declares f16 and it's actually u8, and taking
the config at its word would have doubled every number I'm about to say. At 32K context that's
2.4 GB, which is approaching the model weights. And the position limit is 40,960 tokens, so
128K context isn't a large number on this model — it's an unreachable one. Context length is a
hardware property, and past a certain point the workload doesn't get slower, it stops fitting.
That's a cliff, not a slope.

**Throughput and accelerator balance — what gets chosen.** Here I have to be careful, because the
number I'd have quoted a week ago doesn't survive its own provenance check. What's sealed is a
randomized, interleaved contrast of **1.881× between two conditions on the same die** — same
model, same quantization, same memory controller. If both clusters sit behind the same bandwidth,
that ratio should be near 1. It isn't, which points at INT4 decode being compute-bound rather than
memory-bound on client silicon — 4 FLOPs per byte against a machine balance near 2.5.

But confinement classification came back UNCLEAR, so I can't yet assert those two conditions were
the core clusters I labelled them. It's the argument I expect to make, not one I'm making today.

**Thermal, memory and power — what it costs, and it moves during the session.** This is the one I
care most about. Thermal state evolves under sustained load and context grows as the trajectory
runs, so the objective surface is non-stationary *within a single evaluation*. Every DSE
formulation in this space assumes a static design point. That assumption is wrong here, which
makes a single-number benchmark of this space not merely imprecise but ill-posed."

## 3. What we are actually trying to explain

*This is the research content. Do not skip it to get to the method — it is the reason the method
is shaped the way it is.*

"Underneath the sizing question there's one I care about more.

There is a causal chain running from a physical property of a machine to the semantic behavior of
a program, and as far as I can tell nobody has measured it end to end:

```
silicon property  →  throughput  →  what finishes inside a deadline  →
which steps run where  →  what context the next step sees  →
what the agent does  →  accuracy and dollars
```

Every hardware paper in this space measures the left end. Every agent paper measures the right
end. The propagation between them is asserted in both literatures and demonstrated in neither,
because measuring it requires hardware instrumentation at one end and agent semantics at the
other, and almost nobody has both on the same bench.

So the thing I want to explain is **how a property of silicon becomes a property of behavior, and
what that conversion costs.** Five specific questions, each with a mechanism I can be wrong about:

**Why does the partition move when the hardware changes — and is compute speed the whole story?**
The mechanism I'm proposing is that escalation is a threshold on predicted latency, hardware
scales that prediction, so the crossing rate is a deterministic function of throughput and nothing
else. That's a strong claim and it's falsifiable: the two escalation curves should be *the same
curve*, horizontally rescaled by the measured throughput ratio. If they collapse, the partition
shift is fully accounted for by compute speed. If they don't, something else is driving it and
finding out what is the more interesting result.

**Why is an accelerator sometimes worth nothing?** Roofline. Decode is bandwidth-bound; INT4 gives
about 4 FLOPs per byte against a client machine balance near 2.5, so you're on the memory side of
the knee and adding compute buys you nothing. I want to know where that knee sits for real agent
work and which side each workload lands on — and note that on this platform the ratio of a
*measured* rate to a *derived* bandwidth ceiling is not yet quotable, because STREAM hasn't run and
the denominator is a datasheet.

**Why does the optimum move during a single session, and what drives it?** There are two
mechanisms and they're separable by their driver: thermal state tracks elapsed time under load,
memory pressure tracks context length. Those are independent, so they can be told apart — and
telling them apart matters, because you design against them differently.

**What is the exchange rate between local silicon and cloud spend, and is it linear?** I predict
it isn't. Because escalation is a threshold, more silicon should buy nothing until you cross a
knee, then buy a great deal, then saturate. If that shape is real, 'how much hardware is worth
how many dollars of API spend' has a right answer that depends on where you're standing on the
curve — and that is the economic content of the entire project.

**Which of the three channels binds, and when?** Capacity, throughput, thermal. My expectation is
that it's rarely the one people assume, and that the ordering flips with workload. A theory of
which constraint dominates when is the thing an architect would actually use.

And here's how the tool connects. **SEAM is the falsification instrument for that explanation.**
If I understand the chain, I can predict the rank order of designs I have never run. That's what
rank preservation measures. It isn't a software quality metric — it's the test of whether the
explanation is correct. A tool that ranks correctly is a claim that the mechanism is understood."

## 4. The concession — say this before anyone asks

"Now I want to be direct about what is already done, because I've audited this and a lot of it is.

The behavioral premise — that an agent behaves differently depending on where its steps run — is
documented. Minions saw it. Off-policy evaluation for LLM agents is active work. Output-length
prediction is a mature subfield. There are allocation frameworks that explicitly *assume access to
estimates of single-attempt success probability and expected generation length for each
subtask–model pair* — that's the surrogate I need, already specified. R2V-Agent does step-level
small-model-to-large-model routing, motivated by compounding local errors.

And on the hardware side it's worse than I first thought. Agent.xpu does prefill/decode
accelerator affinity on a client SoC. Agent Memory does phase-aware cost attribution across
agent memory systems. There's a full workload characterization paper on agentic tool-call
behavior. MORI characterizes tool-call idle windows. And MemExplorer, out of Microsoft Research
and Cambridge, is a memory-plus-NPU co-design DSE tool for agentic workloads that balances
throughput and power between prefill and decode devices.

I went in expecting to find a gap and I found a field. Three hypotheses I had drafted got
withdrawn before I pre-registered them, because the audit killed them."

## 5. The pivot — the one line the pitch turns on

"But here is what every one of those has in common.

**They all optimize a local system in isolation. Not one of them admits a cloud boundary.**

MemExplorer designs an accelerator that does all the work. Agent.xpu schedules across NPU and
iGPU, and everything stays on the die. The routing papers cross the boundary but hold the hardware
fixed.

The moment a step is allowed to escalate, the sizing question changes in kind, not in degree. It
stops being *is this NPU large enough* and becomes **large enough for what fraction — given that
the remainder goes to the cloud, at what accuracy, and at what dollar cost.**

That question is untouched. And it is not a gap I'm asserting — it's what's left after I removed
everything I could verify was taken.

Everyone in that literature conditions on (subtask, model). Nobody conditions on
(subtask, model, silicon), and nobody prices the alternative."

## 6. What SEAM is

"SEAM is a design-time DSE framework, not a router.

The structure is a loop. Hardware determines which policies are viable. Policy determines what the
agent does. What the agent does determines what hardware it needs. There's no closed form —
the behavioral response is empirical, it's discontinuous because escalation is a threshold, and
it's non-stationary because the machine drifts under you. So it has to be searched.

The space is about 5×10⁷ configurations. One evaluation is an agent trajectory — minutes and real
tokens, not a kernel launch — so exhaustive enumeration is roughly four hundred years of serial
machine time. A large measured study is on the order of 10³ trajectories. So the surrogate is
being asked to extrapolate about 10⁴ to 10⁵ times beyond what it has seen, and I'd rather say
that number out loud than have someone find it.

Which is why the metric that matters is **rank preservation**, not accuracy. A router that's 5%
off on every decision is a bad router. A design-time tool that's 5% off on every design but orders
them correctly is a correct tool, because the output is *which configuration*, not *what number*.
That's Kendall's tau on held-out design points, and it's the only number I'd defend the tool on.

The output is a silicon sizing rule — the minimum local configuration that reaches a stated
operating point, for a given workload. That's a BOM answer."

## 7. The experimental vehicle

"To measure any of that I need silicon to enter through exactly one channel, so the vehicle is
deliberately unsophisticated: a deadline-aware local-first policy. Try each step locally, escalate
if predicted latency exceeds a per-step deadline.

Between two arms, **only prefill and decode throughput may differ** — same tasks, seeds, prompts,
step types, predicted lengths, deadline, confinement mechanism, reasoning mode. Enforced in code
with tests that fail on violation.

A smarter router would escalate better and measure worse, because silicon would enter through
several channels at once and no shift could be attributed to any of them. Being unsophisticated is
a design property.

And it's self-checking. If the invariant holds, the two escalation curves should be the same curve
horizontally rescaled by the measured throughput ratio. Pre-registered. If they don't collapse,
something other than compute speed is driving the partition — one test that catches affinity
leakage, thermal confounds, and predictor bugs together."

## 8. Why you should believe the measurements

"The thing I'd point to as evidence this is being done carefully is the defect list.

OpenVINO's `PCORE_ONLY` silently falls through to all cores on Panther Lake while `ECORE_ONLY`
binds — so anyone measuring P-core versus LP-E on this platform has affinity leaking and doesn't
know it. A corrupt model IR that loaded and generated plausible output, caught only because a
2.26 GB file crashed a hash function. Battery counters that update on a roughly 19-second cadence
with an 8% systematic between two estimators. A charging confound that made throughput appear to
*increase* over a run.

Every one of those is a defect that would have produced clean-looking, wrong results. That's the
contribution that's already accruing, and it's why I trust the numbers I do have."

## 9. Why this lab

"Two reasons this belongs here rather than anywhere else.

The routing decision itself is a coordinate in my design space — where the decision runs, software
or a hardware gating engine. Every paper in that literature is software. This lab has HLS,
OmniSim, and OCuLink on the same bench, so the routing amortization bound becomes something
*measured against silicon we designed* rather than modeled. And the OmniSim-versus-FPGA error
quantifies the fidelity of every hypothetical-hardware claim in the paper.

Second, MemExplorer's answer is to give prefill and decode separate devices with separate memory.
On a client SoC you can't do that — one unified pool shared by CPU, iGPU and NPU. The client
version of their question is strictly harder and their answer isn't available to us. That's the
paragraph that separates us in related work."

## 10. The ask

"What I want out of this meeting:

- Whether the chain in §3 is the right object to go after, or whether I should be explaining one
  link of it properly instead of all six adequately. That's the question I'm least sure about.
- A read on whether the cloud-boundary framing is enough of a differentiator, or whether I'm
  standing too close to MemExplorer and Agent.xpu.
- Whether to keep the HLS gating engine as a first-class contribution or hold it as a follow-on.
- Confirmation on the second platform, because the sizing rule generalizing from two machines is
  the weakest external-validity claim I have and I know it.
- And a sanity check on scope: I've removed three hypotheses in the last week from auditing. I'd
  rather keep narrowing than defend something soft."

---

## Delivery notes

**§3 is the pitch. §5 is the defense.** They do different jobs and it matters which one you lead
with. §3 is what you're trying to *understand* — the chain from silicon to behavior — and it's
what makes this research rather than procurement consulting. §5 is why nobody else has done it.
An advisor who buys §3 will help you fix §5; one who only hears §5 will treat the whole thing as a
positioning exercise.

**If you get cut short, land the chain.** Get to "how a property of silicon becomes a property of
behavior, and what that conversion costs," then jump to the isolation line in §5. Everything else
is elaboration.

**Every explanatory question in §3 has a mechanism attached, deliberately.** Say the mechanism out
loud each time. "The partition moves" is an observation; "the partition moves because escalation
is a threshold on predicted latency and hardware scales the prediction" is a claim you can be
wrong about. The second one is what gets you taken seriously, and the rescaling test is what makes
it honest.

**The audit is an asset, not an apology.** §4 is where most people would hedge. Do the opposite —
name every paper, say you withdrew three hypotheses. Someone who narrowed their own claim under
evidence is more credible than someone who found a gap. It also makes §5 land, because by then the
room knows you looked.

**Lead with measured numbers, mark illustrative ones — and know which is which.** Sealed and
device-read: 73,728 B/token u8, the 40,960 position ceiling, the 1.881× interleaved contrast.
Provisional: the core-cluster labels on that contrast, pending confinement. Not quotable: any
percentage against the 52 tok/s roof, because the denominator is derived and STREAM hasn't run.
If you use a sizing-rule example, say "illustrative" out loud.

**A week ago this section carried 15.1 vs 7.4 tok/s framed as a quantization result.** There is no
sealed INT8 arm; the framing was wrong and the numbers were untraced. If someone in the room saw
the earlier version, say so plainly — catching it yourself is the credible move, and it is the
same discipline that produced the KV dtype catch.

**Don't let routing dominate.** It's the instrument, not the finding. If the room starts debating
routing policies, pull back to the sizing question.

**Two questions to have loaded:** "Isn't this off-policy evaluation?" — no, OPE work models the
*environment* and runs the agent for real; I need the *agent* modeled because local inference is
my bottleneck and the environment is cheap. "How is this different from MemExplorer?" — rack-scale
versus client, two objectives versus five, and no cloud boundary.

### Compressions

**Two minutes:** §1, the third channel from §2, §4, and the ask.

**For the collaborator:** §1 and §2 only, then pivot to INVAR. He needs the motivation, not the
method — and the sizing story is what makes his hardware-conditional evaluation question matter.

**For an industry conversation:** §1, §2, §5's sizing-rule output, §9. Drop the vehicle and the
validation entirely.
