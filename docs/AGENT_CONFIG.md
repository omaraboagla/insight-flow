# Agent and runtime configuration

Date: 2026-10-05. Never put credentials in this document.

## Available build environment models

The orchestration tool exposes `gpt-6.1-sol` (latest coding/everyday workhorse), `gpt-6-astra` (frontier reasoning), `gpt-6-sol`, `gpt-6-luna` (fast lower-cost), and `gpt-5.6-sol`. These are Codex team models, separate from product Gemini models.

| Role | Selected best fit | Reasoning | Ownership |
| --- | --- | --- | --- |
| PLAN-GOVERN | gpt-6-astra | high | docs/*; gate/security review |
| BUILD | gpt-6.1-sol | high | app/* and launch/runtime files |
| TEST-REPORT | gpt-6-luna | medium | tests/* and reports/* |

The orchestrator confirmed these actual assignments in STATUS.md. Team requests and evidence handoffs are written to STATUS.md.

## Gemini runtime decisions

| Purpose | Environment variable | Requested default | Verification |
| --- | --- | --- | --- |
| SQL planning | GEMINI_MODEL | gemini-3.5-flash | Listed in public docs; account SDK check blocked |
| Rewrite/phrasing | GEMINI_FAST_MODEL | gemini-3.1-flash-lite | Listed in public docs; account SDK check blocked |
| Embedding | GEMINI_EMBED_MODEL | gemini-embedding-001 | Listed in public docs; account SDK check blocked |

No Gemini 2.5 family model is permitted. The user identifies its scheduled retirement as 2026-10-16. If a requested model is absent or returns 404, select the newest listed compatible Flash/Flash Lite model and record the exact decision here and in README. Never silently replace a missing embedding model with a text model.

API verification status: **BLOCKED / NOT VERIFIED**. The official SDK is absent and package installation failed because the execution environment cannot resolve its package index. No authenticated model-list response or successful tiny API call has been observed. PLAN-GOVERN does not access credentials.

The [official public model catalog](https://ai.google.dev/gemini-api/docs/models), checked on 2026-10-05, lists the requested `gemini-3.5-flash` and `gemini-3.1-flash-lite`, and newer `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, and `gemini-3.5-flash-lite`. SDK documentation includes `gemini-embedding-001`. Public documentation is not proof that this account can call those models. Retain the user-requested defaults until authenticated discovery is possible; no fallback was actually exercised.

Authenticated available model IDs: **NOT AVAILABLE — SDK/network blocker**. Tiny generation outcome: **NOT RUN**. Runtime models actually used for successful calls: **none verified**.

## Verified official SDK shapes

Consulted [official google-genai Python SDK documentation](https://googleapis.github.io/python-genai/) on 2026-10-05. Use `from google import genai` and `from google.genai import types`. Construct the client inside app startup after dotenv loading, using the environment credential without logging it. No prompt, test fixture or public response contains the credential.

```python
# Inside the application's configured SDK boundary; environment setup omitted.
models = list(client.models.list())
model_ids = [model.name for model in models]
response = client.models.generate_content(
    model=main_model,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        response_json_schema=plan_json_schema,
    ),
)
embedding_response = client.models.embed_content(
    model=embedding_model,
    contents=texts,
    config=types.EmbedContentConfig(output_dimensionality=768),
)
vectors = [embedding.values for embedding in embedding_response.embeddings]
```

The SDK documents `models.list()` pagination, `response_json_schema` for JSON-schema-controlled generation, and `embed_content(contents=...)` for one or multiple texts. Validate parsed JSON against the application contract; count `usage_metadata` when returned. Plain model IDs may be normalized by stripping `models/` from inventory names. [Official SDK reference](https://googleapis.github.io/python-genai/genai.html) and [Gemini structured output guide](https://ai.google.dev/gemini-api/docs/structured-output) are primary implementation references.
