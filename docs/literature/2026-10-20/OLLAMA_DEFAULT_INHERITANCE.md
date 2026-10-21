# Do ECO-LLM and Minions inherit Ollama's context default? (Task AZ, 2026-10-20)

Rithwik item 3. Result: **withdraw "inherit" for both.** Minions' code sets
num_ctx explicitly in every Ollama request. ECO-LLM names context length as a
configured, swept Ollama option and has no public code. Neither paper is
evidence that a hybrid study inherits Ollama's default.

Method: git clones made 2026-10-20 of github.com/HazyResearch/minions (HEAD
a87d0ee9, 2026-03-11) and github.com/ollama/ollama (HEAD 2cd63f7a,
2026-10-20); `git grep` and `git log -S/-G` for num_ctx, NumCtx and
OLLAMA_CONTEXT_LENGTH; the arXiv pages of both papers; GitHub search for an
ECO-LLM repository.

## 1. Ollama's default num_ctx by version (source)

| Ollama versions | default num_ctx | where (commit) |
|---|---|---|
| through v0.5.12 (tag commit 8c13cfa4, 2025-02-23) | 2048 | api/types.go DefaultOptions, `NumCtx: 2048` (v0.5.12 L612; present since 1fbf3585, 2023-10-02) |
| v0.5.13 (2025-03-03) to v0.6.6 | 2048, now settable by `OLLAMA_CONTEXT_LENGTH` | 314573bf (2025-02-24, #8938): envconfig/config.go `ContextLength = Uint("OLLAMA_CONTEXT_LENGTH", 2048)` |
| v0.6.7 (tag commit a7835c67, 2025-04-30) to v0.15.4 | 4096 | 44b466ee (2025-04-28): `Uint("OLLAMA_CONTEXT_LENGTH", 4096)` (an earlier 424f6486 #10364 was reverted by dd93e1af the same week) |
| v0.15.5 (tag commit 8a4b77f9, 2026-02-05) onward | VRAM tiers: < 24 GiB 4096, 24-48 GiB 32768, >= 48 GiB 262144 (thresholds coded as 23 / 47 GiB) | 0334ffa6 (2026-01-27), "server: use tiered VRAM-based default context length" |

A request's `options.num_ctx`, a Modelfile `PARAMETER num_ctx`, or
`OLLAMA_CONTEXT_LENGTH` overrides the default. Version dates are the tag
commits' dates in the clone; release-page dates were not fetched.

## 2. Minions (Narayan et al., arXiv 2502.15964 v1, 2025-02-21; ICML 2025)

- No Ollama server version is stated or pinned. setup.py lists `"ollama"`
  (the Python client) unpinned at 5c2c9c2f (L9) and at HEAD (L8).
- First public commit 250d790b (author date 2025-02-03, committed
  2025-02-24). Commit at the Ollama blog post 5c2c9c2f (2025-02-25).
  `minions/clients/ollama.py`, identical num_ctx code in both:
  - L16 `num_ctx: int = 4096,` (constructor default);
  - L27 `self.num_ctx = num_ctx`;
  - L59-66 `_prepare_options`: `opts = {"temperature": ..., "num_predict": ...,
    "num_ctx": self.num_ctx}`, passed as `options=` on every chat (async L111-113,
    sync L153-166);
  - L45 (`_ensure_model_available`): a one-message warm-up `ollama.chat` with
    no options. It only checks that the model exists.
  - The README example at 5c2c9c2f (L85-87) builds
    `OllamaClient(model_name="llama3.2")`, so it sends num_ctx 4096 explicitly.
- At that date the newest Ollama release was v0.5.12, with default 2048. So
  Minions raised the context to 4096 explicitly; it did not inherit 2048.
- 9668878 (2025-04-13, "fix: ollama ctx length") changed the default to
  `num_ctx: int = 48000`. At HEAD a87d0ee9: L20 48000, L57 131072 for
  granite3.2-vision, L176 sent in options. app.py sets num_ctx in several
  places: L753 `num_ctx=4096`; L1257-1301 picks from 2048-131072 by
  estimated prompt tokens and re-creates the client. The a2a app's config.py
  L52 default is 4096.
- Wording: "Minions sets num_ctx explicitly: 4096 in the code at publication,
  48,000 since April 2025."

## 3. ECO-LLM (Patidar et al., arXiv 2507.09003; v1 2025-07-11, v2 2026-06-21)

- Code: none public. Both versions say "We plan to open-source the code upon
  publication." The arXiv page lists no code link. GitHub search (repos named
  eco-llm; the first author's 13 public repos) found nothing related.
- Paper text (v1 and v2):
  - "We integrate Ollama for edge deployment and OpenAI for cloud
    processing" (section 4);
  - Table 2, Ollama row, configurable options: "model name, temperature,
    context length";
  - section 3.2.2: a model framework "might include ... model context lengths
    to sweep through".
  - No num_ctx value, Ollama version or Modelfile is given.
- Ollama's default at v1's date was 4096 (v0.6.7 to v0.15.4), but the paper
  says context length is a configured, swept option. With no code there is
  no evidence it was left at the default.
- Wording: "ECO-LLM treats context length as a configured Ollama option that
  its emulator sweeps; the values are not reported and the code is not
  public."

## 4. Consequences for our documents (registered docs are not edited)

Neither paper supports "typical hybrid studies inherit Ollama's 4k default".
The 4096 figure itself is still a correct Ollama default for v0.6.7-v0.15.4,
and for the < 24 GiB tier from v0.15.5 (our XPS, 16 GB). Minions at
publication also used 4096, set explicitly.

The default at Minions' version was 2048, so per the task rule every "4096"
or "inherit" used to justify arm D is flagged. The text needs a superseding
amendment, not an edit:
1. docs/amendments/DEMO2_AMEND_2026-10-16_TRUE_DEFAULT.md (REGISTERED):
   - L63 arm D: "A plus a 4096 window, labeled 'the configuration typical
     hybrid studies inherit'". The label is unsupported.
   - L89-92: "ECO-LLM (2507.09003) and Minions run Ollama locally and state
     no context setting". Wrong for the Minions code; ECO-LLM states that
     context length is configured.
2. docs/amendments/DEMO2_DESIGN_2026-10-14.md (REGISTERED):
   - L78: "4096 tokens | Ollama FAQ: 'By default, Ollama uses a context window
     size of 4096 tokens.'" True only for v0.6.7-v0.15.4 and the < 24 GiB tier
     after; the version is not cited.
3. docs/RELATED_SEARCHES.md (log; append-only correction):
   - L330-334 verdict "Hybrid papers on Ollama inherit its context default:
     SUPPORTED, with a caveat". Now NOT SUPPORTED.
   - L372 allowed wording "the configuration typical hybrid studies inherit
     (Ollama's 4k tier below 24 GiB)". Withdraw.
   - L87-88, L107: the FAQ 4096 quote. Add the version range.
4. docs/EXPERIMENT_REGISTRY.md L201 (DEMO-2 row) and the OLLAMA-WINDOW row
   (L208) repeat the arm D label.
5. tools/demo2_true_default_predict.py ARMS["D"] label "ecosystem default
   (Ollama < 24 GiB tier)". It is accurate for current Ollama on the XPS;
   no change needed.

Proposed replacement label for arm D (for Zach; goes in the arm-spec
addendum): "Ollama's current default window on a < 24 GiB machine (4096,
Ollama >= v0.15.5; also 4096 in v0.6.7-v0.15.4)". Drop the "hybrid studies
inherit" claim, or cite a study whose code shows no num_ctx override (none
found here).

## Sources
- https://github.com/HazyResearch/minions (commits 250d790b, 5c2c9c2f, 9668878, a87d0ee9)
- https://github.com/ollama/ollama (commits 1fbf3585, 314573bf, 424f6486, dd93e1af, 44b466ee, 0334ffa6; tags v0.5.12, v0.5.13, v0.6.7, v0.15.5)
- https://arxiv.org/abs/2502.15964 (Minions v1, 2025-02-21)
- https://arxiv.org/abs/2507.09003, https://arxiv.org/html/2507.09003v1, https://arxiv.org/html/2507.09003v2 (ECO-LLM)
