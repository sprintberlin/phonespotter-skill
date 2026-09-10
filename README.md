# PhoneSpotter Skill

A synchronous, reusable B2B phone-number lookup skill.

PhoneSpotter first uses **Google-grounded web search through OpenRouter** to find public company central numbers, direct dials, or mobiles. It then invokes **Lusha** only when a sufficiently verified direct dial or mobile number is still missing. Every non-empty provider response is normalized to E.164, deduplicated, and assessed by a configured OpenRouter model. Empty provider responses proceed to the next provider without an evaluation request.

It does not read CRM records, scrape private mailboxes, or write back to a CRM. It only accepts a contact identity and emits a structured result.

## Provider order

1. `openrouter_web_search`: `openrouter:web_search` with `engine: native` and a Gemini model, using Google's native grounded search through OpenRouter.
2. `lusha`: paid fallback for direct business phone or mobile data.

A verified direct line or mobile ends the waterfall. A company central number is retained as `company_phone`, but is only a partial result.

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install .
cp config.example.yml config.yml
```

Set credentials in the environment, never in `config.yml`:

```bash
export OPENROUTER_API_KEY='...'
export LUSHA_API_KEY='...'
```

## Configuration

`config.yml` only contains behavior: OpenRouter endpoint/model, Google-grounded search options, provider order, and quality limits. It deliberately contains no credentials.

The default OpenRouter model is `google/gemini-3.7-flash`. With `engine: native`, OpenRouter routes web search through Gemini's native Google grounding.

## Usage

Pass one JSON object on stdin:

```bash
printf '%s' '{
  "first_name": "Max",
  "last_name": "Mustermann",
  "company": "Beispiel GmbH",
  "email": "max@beispiel.de",
  "country": "DE"
}' | phonespotter --config config.yml --pretty
```

Or pass it directly:

```bash
phonespotter --config config.yml --input '{"company":"Beispiel GmbH","country":"DE"}' --pretty
```

Example result:

```json
{
  "status": "found",
  "direct_phone": "+49301234567",
  "mobile_phone": null,
  "company_phone": "+49301230000",
  "best_phone": "+49301234567",
  "best_phone_type": "direct",
  "confidence": 0.91,
  "providers_checked": ["openrouter_web_search", "lusha"],
  "successful_provider": "lusha"
}
```

Possible statuses:

- `found`: verified direct or mobile business phone found.
- `partial`: only a verified company central number was found.
- `not_found`: no provider returned a usable candidate.
- `error`: input or required configuration is missing.

## OpenClaw skill

The repository-root `SKILL.md` is the thin OpenClaw adapter. The reusable functionality lives in the Python CLI, so it can also be used by scripts, webhooks, CRMs, or other agents.

## Safety and cost controls

- Secrets only come from environment variables.
- Phone values are normalized and validated deterministically with `phonenumbers` before evaluation.
- The evaluator can only select numbers already returned by a provider. It cannot generate a number.
- Empty provider results do not invoke the evaluator.
- Lusha is not contacted until the Google-grounded stage has failed to produce a sufficiently verified direct or mobile number.
