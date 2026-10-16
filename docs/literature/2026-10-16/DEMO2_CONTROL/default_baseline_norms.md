# Default-configuration baselines: runtime context defaults, hybrid-LLM paper practice, and autotuning methodology norms (for DEMO-2 control choice)

Scope note: research done 2026-10-15. About 36 tool calls. Several primary pages (OpenVINO API/OVMS docs, the llama.cpp GitHub README, OpenVINO release notes) came back as navigation-only or blocked, so some OpenVINO defaults are **unverified** and are listed under Gaps. Secondary or aggregator sources are marked **[secondary]**.

## Q1. Default context windows in common local runtimes (as of Oct 2026)

### Takeaway
There is no single "runtime default" context window. Ollama now picks a context size from VRAM tiers (4k below 24 GiB). Current llama.cpp builds default to the model's own trained context (`-c 0`). vLLM takes the length from the model config. LM Studio still loads at 4096 in practice. That makes a 4096 window an "Ollama/LM Studio low-VRAM default", not a universal one, and not an OpenVINO default. On an Intel AI PC with shared memory well under 24 GiB of VRAM, 4096 is what a current Ollama user would actually get, and that is the only honest framing of the choice.

### Cited Findings
- **Ollama** (current docs, Oct 2026): "Ollama defaults to the following context lengths based on VRAM: < 24 GiB VRAM: 4k context; 24-48 GiB VRAM: 32k context; >= 48 GiB VRAM: 256k context." Also: "Cloud models are set to their maximum context length by default." The docs recommend at least 64,000 tokens "for web search, agents, and coding tools." The setting is changed with `OLLAMA_CONTEXT_LENGTH=64000 ollama serve` and checked via the CONTEXT column of `ollama ps`. — [Ollama docs: Context length](https://docs.ollama.com/context-length)
  - The fetched page carried no version note. The Ollama release that introduced the VRAM tiers was not confirmed (see Gaps). The older FAQ line that DEMO-2 currently cites ("default 4096"/2048) may be stale, so cite the context-length page and the Ollama version that was actually checked.
  - Ollama's own docs recommend ≥64k for agents. A reviewer could quote that line against a 4k control on an agentic BFCL multi-turn benchmark. It cuts both ways: the vendor's own default is known to be too small for agents, which is exactly the gap a tuned configuration fixes. — [Ollama docs](https://docs.ollama.com/context-length)
- **llama.cpp llama-server** (Debian unstable man page, package `llama.cpp-tools 1:0.6.0+dfsg-2`, page dated 2026-10-09): `-c, --ctx-size N` "(default: 0, 0 = loaded from model)". Also `--cache-prompt` "whether to enable prompt caching (default: enabled)", `-ctk/--cache-type-k` "(default: f16)", `-np/--parallel` "number of server slots (default: -1, -1 = auto)", and a `-fit/--fit` option "whether to adjust unset arguments to fit in device memory". — [Debian manpage llama-server(1)](https://manpages.debian.org/unstable/llama.cpp-tools/llama-server.1.en.html)
  - Supporting evidence: llama.cpp commit "model-conversion : remove -c 0 from model card template [no ci] (#18807)" drops `-c 0` because it "already matches the default". — [semanticdiff view of commit 20ca2e1](https://app.semanticdiff.com/gh/ggml-org/llama.cpp/commit/20ca2e12c40bb1b17b22b8acef22bf559a6f91c3)
  - Older llama.cpp builds defaulted to a fixed small n_ctx. For example, early-2024 tags b1818/b1824 have their own server README defaults. — [b1824 README mirror](https://git.peisongxiao.com/CS348Project/llama.cpp/raw/tag/b1824/examples/server/README.md) (not fetched; listed only as the location of the historical default)
- **LM Studio**: the CLI docs give no default for `--context-length` ("The number of tokens to consider as context when generating text"). — [LM Studio docs: lms load](https://lmstudio.ai/docs/cli/load). User reports show "loaded_context_length is 4096" and "The context in LM studio resets to 4k" (Zed issue; Zed v0.193.3 and a later comment on Zed 1.14.2). — [zed-industries/zed#33938](https://github.com/zed-industries/zed/issues/33938) **[secondary / user report]**
- **vLLM**: `--max-model-len` "Model context length. If unspecified, will be automatically derived from the model config." `--kv-cache-dtype` "Default: 'auto'" ("will use model data type"). — [vLLM v0.6.3 engine args](https://docs.vllm.ai/en/v0.6.3/models/engine_args.html) (older doc version. Current docs not fetched, but the behavior is long-standing.)
- **MLX-LM**: one comparative paper describes MLX as using a rotating KV cache that is "configurable" with a "(default 4k tokens)" window. It pins MLX v0.26, MLC-LLM commit 3d42929, llama.cpp b5963, and Ollama v0.10.1. — [Rajesh et al., arXiv 2511.05502](https://arxiv.org/pdf/2511.05502) **[secondary. Not verified against mlx-lm source. I recall `max_kv_size` defaulting to unbounded/None in mlx_lm, so treat this as conflicting/unverified.]**
- **OpenVINO GenAI / OVMS**: this session could not retrieve a primary-source statement of a default max prompt length or context window for CPU/GPU. The SchedulerConfig and OVMS LLM-reference pages returned navigation only. See Gaps.
- **Foundry Local / Windows AI, Intel AI Playground, MLC-LLM**: no primary-source default found in this session (see Gaps).

### Inferences
- The defensible framing is not "4096 is the runtime default." It is "4096 is what the most widely used local runtime (Ollama) assigns on hardware in our class (<24 GiB VRAM), and what LM Studio loads by default." On an Intel AI PC with an iGPU/NPU and shared system memory, Ollama would land in the 4k tier. The control can therefore be described as "the context a typical user of a mainstream local runtime would get on this device class." Cite the Ollama context-length page and record the Ollama version checked.
- OpenVINO GenAI, which DEMO-2 actually runs, has (as far as I could verify) no fixed 4096 default on CPU/GPU. The window is bounded by the model's `max_position_embeddings` and memory. A strict "OpenVINO defaults as-is" control would therefore use the model maximum (Qwen3-4B: 32,768 native, 40,960 in some configs), and that is close to the tuned window. This is the core strawman risk (a). Two mitigations:
  1. Report **two controls**: (i) "ecosystem-typical default" with a 4096 window (Ollama/LM Studio low-VRAM tier); (ii) "OpenVINO as-shipped", with the model-max window and all runtime defaults, including prefix caching if it is on by default. The tuned configuration is then compared against both.
  2. Alternatively, run a window-only ablation (4096 → 40,960 with everything else default) so the effect of the window is separated from OBS_MASK, residency, and KV precision.
- Concern (b): explicitly disabling prefix caching in the control, when the runtime enables it by default, contradicts the label "default". Either leave it at the runtime default and read back the effective value, or rename the control "minimal/naive configuration" and justify the choice. Mislabeling a deliberately degraded setting as "default" is the specific pattern reviewers call a strawman.
- The llama.cpp change to "0 = loaded from model" is the strongest evidence that the ecosystem is moving away from 4096 defaults. A reviewer familiar with current llama.cpp may object, so pre-empt it.

### Gaps
- **OpenVINO GenAI 2026.2.1 defaults (critical, unverified):** the SchedulerConfig `enable_prefix_caching` default, whether LLMPipeline on CPU/GPU uses the continuous-batching/PagedAttention backend (and so prefix caching) by default, the default `cache_size`, and the default KV-cache precision (u8 on CPU, dynamic quantization) all remain unverified. The docs pages ([SchedulerConfig 2026](https://docs.openvino.ai/2026/api/genai_api/_autosummary/openvino_genai.SchedulerConfig.html), [OVMS LLM reference 2026](https://docs.openvino.ai/2026/model-server/ovms_docs_llm_reference.html), [2025 release notes](https://docs.openvino.ai/2025/about-openvino/release-notes-openvino.html)) rendered as navigation only. GitHub issue #4343 only shows users setting `sc.enable_prefix_caching = True` explicitly, and that "scheduler_config triggers PagedAttention layer" (2026.3/2026.4). — [openvino.genai#4343](https://github.com/openvinotoolkit/openvino.genai/issues/4343). **Recommendation: settle this empirically by printing the effective SchedulerConfig and the compiled-model properties (`KV_CACHE_PRECISION`, etc.) from the installed 2026.2.1 build, and by reading `scheduler_config.hpp` at the 2026.2.1 tag.**
- The NPU `MAX_PROMPT_LEN` default (I believe it is 1024 in StaticLLMPipeline, but could not verify this session).
- The Ollama version that introduced VRAM-tiered defaults, and the exact text of the Ollama FAQ that DEMO-2 currently cites.
- The llama.cpp build number where `-c` switched from 4096 to 0. The direct GitHub README fetch was blocked (URL not in provenance): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- MLC-LLM `context_window_size`/`prefill_chunk_size` defaults, Foundry Local defaults (probably taken from each ONNX model's `genai_config.json` `max_length`; unverified), and Intel AI Playground defaults: none were found.

## Q2. How hybrid device-cloud LLM papers configure and report the local runtime baseline

### Takeaway
In the papers checked, hybrid/routing work rarely reports local runtime configuration (context window, KV precision, prefix caching). Local models are run through Ollama with no reported settings, or are not run on-device at all. None of the checked papers compares a "default" against a "tuned" local runtime configuration. DEMO-2's explicit runtime-configuration ablation is novel relative to this literature, and its reporting bar is set by the systems-benchmarking literature (Q3/Q4), not by the routing papers.

### Cited Findings
- **ECO-LLM (arXiv 2507.09003)**: "We integrate Ollama for edge deployment and OpenAI for cloud processing". No engine-level settings are given. Context length appears only as a sweepable parameter ("model context lengths to sweep through"). Prefix caching is mentioned only for retrieval context ("ECO-LLM Emulator also implements prefix caching for computational efficiency"). The edge hardware is "a single NVIDIA RTX A6000 GPU", which the authors say exceeds typical edge devices. The main baseline is RouteLLM, augmented with their RAG module. There is **no default-vs-tuned runtime comparison**. — [ECO-LLM, arXiv 2507.09003v1](https://arxiv.org/html/2507.09003v1)
- **Minions (Hazy Research / Ollama blog, Feb 25 2025)**: the local model is Llama 3.2 via Ollama. Example clients are `OllamaClient(model_name="llama3.2")` and `OllamaClient(model_name="llama3.2", temperature=0.0, structured_output_schema=...)`. The post mentions **no context window/num_ctx setting**. — [Ollama blog: Minions](https://registry.ollama.ai/blog/minions)
  - Inference: under Ollama's then-default (2048 at the time, by my recollection; unverified), a Minions local model would have run with a small window unless the library set `num_ctx` internally. This was not checked in the Minions repo.
- **Local-runtime comparison paper (arXiv 2511.05502)**: pins versions and commits ("macOS, Xcode/Metal, Python, and framework commits"), fixes seeds and sampling, and runs N=10 trials. It does **not** say whether runtimes used defaults or tuned settings, and the KV/caching designs differ by runtime. Comparisons to an NVIDIA A100 with vLLM are "contextual, not head-to-head". — [arXiv 2511.05502](https://arxiv.org/pdf/2511.05502) **[used as an example of reporting practice]**

### Inferences
- From prior knowledge, not re-verified this session: HybridLLM (Ding et al., ICLR 2024), RouteLLM (Ong et al., 2024), and MixLLM are router-quality papers evaluated on pre-computed response quality and API cost. They do not deploy a local runtime, so they report no runtime defaults. Phrase any claim to that effect cautiously ("to our knowledge…"), or verify it before writing it.
- Because the routing literature leaves the local runtime unspecified, DEMO-2 can position itself as "the first to show that local runtime configuration, not just the router, moves hybrid $/task". The control must then be convincingly realistic, which again argues for two controls (ecosystem default and as-shipped OpenVINO).

### Gaps
- EdgeWise (arXiv 2610.17560) and EC2-Bench (arXiv 2610.17816) could not be located. A search for "arXiv 2610.17560 EdgeWise" returned unrelated results. Their runtime-reporting practice is unverified, and the IDs themselves should be double-checked.
- PAAC, HybridFlow, and MixLLM were not retrieved this session.
- Whether the Minions code sets `num_ctx` internally was not checked.

## Q3. Methodology norms for "vendor default vs tuned" comparisons (autotuning literature)

### Takeaway
The database-tuning literature treats the shipped default as a legitimate but **weak** reference. It is usually reported alongside **stronger baselines**: rule-based tuning tools, expert DBAs, a cloud provider's pre-tuned configuration, or an organization's fleet configuration. Later work explicitly criticizes defaults as unrepresentative ("based on minimal hardware requirements") and measures gains against a production or pre-tuned configuration instead. Benchmarking-methodology work lists "failure to optimize" competing configurations as a top pitfall. The norm is to report several baselines and to show that the gain survives against the strongest reasonable one.

### Cited Findings
- **OtterTune (Van Aken et al., SIGMOD 2017)**, §7.1: the authors "did not modify any knobs in their default configurations other than to enable incoming connections". Figure 10 compares "(1) default configuration, (2) OtterTune configuration, (3) tuning script configuration…". §7.6 also compares against configurations "selected by human DBAs and open-source tuning advisor tools" (MySQLTuner, PGTune), human experts ("the premiere MySQL tuning and optimization expert…", "the lead DBA for a mid-western judicial court system"), and **Amazon RDS configurations** extracted and rerun "on the same EC2 setup". The authors did this because running RDS directly "did not provide a fair comparison because Amazon does not allow you to disable the replication settings." Each DBA "was provided with the same EC2 setup used in all of our experiments." — [OtterTune SIGMOD'17 PDF](https://www.cs.purdue.edu/homes/csjgwang/CloudNativeDB/OtterTuneSIGMOD17.pdf)
  - Lesson for DEMO-2: four baseline tiers (vendor default, rule-based tool, human expert, cloud-vendor pre-tuned), all on identical hardware, with fairness adjustments explained.
- **Van Aken et al., VLDB 2021, "An Inquiry into ML-based Automatic Configuration Tuning Services on Real-World DBMSs"**:
  - §2.2: "the default configurations for MySQL and Postgres are based on their minimal hardware requirements". The paper presents this as why beating the default is expected and weak evidence.
  - §2.2: "one can achieve 75–95% of the performance obtained by ML-generated configurations by tuning only two knobs". This is a strong "simple-tuned" baseline.
  - §3.2: gains are measured relative to Société Générale's "pre-tuned configurations that SG uses for their entire fleet", which "outperform Oracle's default settings" but "only modify 4–6 knobs".
  - §5.1: the same VM "can fluctuate by as much as 4×" under an identical default configuration, so baselines must be measured repeatedly.
  - §5: Latin Hypercube Sampling is used "as a baseline".
  - [VLDB 2021 p1241](https://vldb.org/pvldb/vol14/p1241-aken.pdf)
- **Raasveldt et al., "Fair Benchmarking Considered Difficult" (DBTest 2018), slides**: the "Common Pitfalls" list includes "Overly-Specific Tuning". The slide "Failure to Optimize" says there is "Low incentive to optimise competition" and lists "Compiler (-O1 vs -O3, version, …)" and "Configuration" (e.g., "pg_shared_buffers=10GB"). Its fix: "Involve competition! Have them configure their system." The slides also stress holding "same configuration parameters", "same compilation flags", and "same version number" constant. — [Raasveldt DBTest'18 slides](https://dbtest.dima.tu-berlin.de/media/DBTEST.io_Presentations/dbtest_raasveldt_18-06.pdf)

### Inferences
- Mapped to DEMO-2:
  - (1) **Vendor/ecosystem default**: 4096 window (Ollama tier), OpenVINO defaults otherwise, with prefix caching **left at its default**.
  - (2) **As-shipped OpenVINO**: model-max window, all runtime defaults.
  - (3) **Simple-tuned / "two-knob" baseline**, analogous to Van Aken's two-knob result: window raised to 40,960 only, no OBS_MASK or residency.
  - (4) Full tuned configuration.
  - If (4) beats (3) on cloud $/task at equal passes, the strawman critique fails, because the gain is not explained by fixing one obviously bad default.
- Van Aken 2021's "defaults based on minimal hardware requirements" argument is a ready-made citation for why a shipped default is a fair "what users actually get" baseline but not the only one. Pair it with a stronger baseline rather than defending the default alone.
- The variance warning (4× fluctuation) supports running the control several times and reporting dispersion.

### Gaps
- CDBTune (SIGMOD 2019), Zhang et al. VLDB 2022 HPO evaluation, Spark/Hadoop tuning papers, compiler-autotuning norms, and LLM-serving configuration tuners (vLLM/SGLang tuning papers) were not retrieved this session, so no quotes are available. No explicit reviewer critique using the word "strawman" about default baselines was found in a primary source.

## Q4. Recommended practice for disclosing defaults (versions, read-back of effective settings)

### Takeaway
Pin and report exact versions and commits, state every non-default knob, and verify effective runtime settings at run time rather than trusting documentation. The runtimes expose read-back mechanisms (`ollama ps` CONTEXT column, llama-server flags with env-var equivalents), and the benchmarking literature treats version, configuration, and compile flags as required disclosures.

### Cited Findings
- Ollama recommends checking the allocated context via `ollama ps`: the CONTEXT column shows the allocated length, and PROCESSOR shows CPU offload. — [Ollama docs](https://docs.ollama.com/context-length)
- llama-server documents an env-var equivalent and a default for each flag (e.g., `LLAMA_ARG_CACHE_PROMPT`, `LLAMA_ARG_CACHE_TYPE_K`). Its `--fit` option "adjust[s] unset arguments to fit in device memory", so effective values can differ from nominal defaults and must be read back. — [llama-server(1) manpage](https://manpages.debian.org/unstable/llama.cpp-tools/llama-server.1.en.html)
- Benchmarking norms: hold "same configuration parameters… same compilation flags… same version number" constant and disclose them. — [Raasveldt DBTest'18](https://dbtest.dima.tu-berlin.de/media/DBTEST.io_Presentations/dbtest_raasveldt_18-06.pdf). Pin framework commits, fix seeds and sampling, and use repeated trials (N=10, mean ± sd). — [arXiv 2511.05502](https://arxiv.org/pdf/2511.05502)
- Run baselines on an identical environment, and explain any deviation from a vendor's shipped configuration (OtterTune's RDS replication example). — [OtterTune SIGMOD'17](https://www.cs.purdue.edu/homes/csjgwang/CloudNativeDB/OtterTuneSIGMOD17.pdf)

### Inferences
- Proposed disclosure table for DEMO-2: per configuration, list the OpenVINO/OpenVINO GenAI version (2026.2.1), the optimum-intel/NNCF export version, the model revision hash, device (CPU/GPU/NPU), driver version, effective `SchedulerConfig` (printed at startup), effective compiled-model properties (`KV_CACHE_PRECISION`, `INFERENCE_PRECISION_HINT`, read back via `get_property`), max prompt length/window, the prefix-caching state, and each knob's source ("runtime default", "borrowed from Ollama <ver> <24 GiB tier", "tuned").
- Label each control knob with provenance. "Borrowed from Ollama" for the window is honest. "Disabled versus runtime default" for prefix caching has to be either justified or reverted.

### Gaps
- No formal artifact-evaluation checklist (e.g., ACM AE badges or MLPerf rules) about reporting runtime defaults was retrieved this session.
