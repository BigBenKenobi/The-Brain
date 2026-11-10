# Local model evaluation boundary

Model hosting and SSH connection work is deferred at the user's request. No model
has been installed, selected or benchmarked. The current workspace is not established
as the intended hosting device. Its NVIDIA driver query failed; that says nothing
about the hosting device's capabilities.

The portable boundary can be exercised without a model:

```text
python3 -m brain --brain STORE model-input PROJECT_ID --max-records 24 --max-chars 24000
python3 -m brain --brain STORE model-check INPUT.json RESPONSE.json IDENTITY.json
```

Save the first command's JSON output privately. Inputs contain only screened retained
records from one explicit project snapshot. They use full canonical excerpts within
a bounded text budget, distributed across evidence roles and source paths. Coverage
lists every omitted record, including deduplicated text. Each record carries evidence
hash/span/snapshot and any reviewed replacement IDs. Answer keys are never included.

The model response is a JSON object with `items` and `relationships` arrays. An item
contains `id`, `kind`, `summary` and `claims`; a claim contains `record_id` and an
exact `quote` from the input. A relationship contains `from`, `to`, `kind`, `rationale`
and `claims`. Identity JSON contains runtime, version, model, digest and configuration
(an object). Identity is caller-reported until an actual runtime adapter verifies it.

Validation rebuilds the input from immutable retained evidence and compares it in
full. It rejects fabricated or out-of-scope references, duplicate JSON keys, extra
fields, invalid endpoints and oversized responses. Results retain input/response
hashes, model identity and precise source references. Neither exporting nor checking
changes capture, reviewed state, sharing approvals or retrieval.

Exact quotation proves attribution only. A model can cite real text and still draw
an unsupported conclusion. Validated proposals therefore remain unreviewed, with
unknown work stage, uncertain currency and reported evidence strength. Evaluation
must review entailment, contradictions and useful-context recall before considering
adoption. Malformed proposals cannot disable the independent deterministic workflow.

Prepare the existing pilot corpus with:

```text
PYTHONPATH=. python3 scripts/prepare_model_evaluation.py --corpus evaluations/runs/2026-11-10/baseline --output NEW_OUTPUT_DIRECTORY
```

The initial alphabetical packing omitted all five critical phrases in the current
project checkpoint. Distributing records across evidence roles retained all five
within 24 records and 21,501 text characters, and retained the held-out project's
three phrases. This measures input availability, not model performance. The expanded
vision's two phrases are also present, overcoming the briefing's shorter excerpt
boundary for later model evaluation. Full inference comparison, model/runtime identity
verification, wall time, peak RAM/VRAM, timeout handling and host-specific failure
testing remain pending.

Ollama was investigated as a possible adapter using its official
[generate API](https://docs.ollama.com/api/generate) and
[model inventory API](https://docs.ollama.com/api/tags); no runtime choice was made.
A future adapter must enforce local inference, rather than assuming every service
on localhost uses local weights. There is no network transport in this boundary.

The Ollama [API introduction](https://docs.ollama.com/api/introduction) confirms
that a local server can also invoke cloud models. Loopback transport alone is
therefore insufficient to establish this project's local-only requirement. The
[FAQ](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features) documents
`OLLAMA_NO_CLOUD=1` or `disable_ollama_cloud` in server configuration, requiring a
restart. Any future adapter must verify the actual hosting runtime's configuration
before sending project evidence. No service was configured or contacted here.
