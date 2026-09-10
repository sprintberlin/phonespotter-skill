---
name: phonespotter-skill
description: "Find and verify B2B phone numbers through Google-grounded OpenRouter search and Lusha fallback."
---

# PhoneSpotter

Use this skill when a newly created contact lacks a phone number and a public B2B lookup is requested.

1. Run the installed `phonespotter` CLI with one JSON input object.
2. Provide at least a person or company identity. Include name, company, email, LinkedIn URL, position and country when known.
3. Return its structured result. The CLI applies provider order, E.164 normalization, deduplication, and LLM evaluation.
4. Do not expose provider keys or automatically write results to a CRM.
5. `status: partial` means only a central company number was found. A direct or mobile number is the desired result.

Configuration controls models, search settings, enabled providers and cost limits. Credentials come only from environment variables.
