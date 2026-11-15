# Support Triage Agent

A work-in-progress AI support agent for a fictional pet insurance company, Tidewater Pet Insurance. The goal is an agent that drafts replies to support tickets without the language model ever seeing a customer's personal details.

Everything here is invented: the company, the tickets, the names, the IDs. No real customer or employer data is used.

## The problem

Support tickets are full of personal details: names, emails, phone numbers, member IDs, sometimes card or Social Security numbers. Sending that text straight to a language model is a privacy risk, and in regulated industries it can be a compliance problem. But the model doesn't need those details to draft a good reply. It needs the shape of the problem.

## The approach

```
ticket  -->  redact  -->  language model drafts a reply  -->  restore  -->  reply for an agent to review
             (details become placeholders)                   (placeholders become details again)
```

1. **Redact.** Personal details are replaced with typed placeholders such as `[EMAIL_1]` and `[NAME_1]`. The same value always gets the same placeholder, so the text still reads coherently.
2. **Draft.** The model sees only the redacted text.
3. **Restore.** Placeholders in the draft are swapped back for the real values before a human reviews it.

Example:

```
Before:  Hi, this is Dana Whitfield. My member ID is TW-482913. Reach me at dana.whitfield@example.com.
After:   Hi, this is [NAME_1]. My member ID is [MEMBER_ID_1]. Reach me at [EMAIL_1].
```

## Status

| Part | Status |
|---|---|
| Redactor (`deid/`) | Working, with tests and an evaluation |
| Labeled test tickets (`data/tickets.jsonl`) | 24 tickets, 56 labeled personal details |
| Knowledge base for the agent | Not started |
| Agent that drafts replies | Not started |
| Evaluation of the agent's replies | Not started |

## How well the redactor works

Measured on the 24 labeled tickets. A detail counts as caught only if the redactor covers it completely.

| Type | Labeled | Caught | Recall |
|---|---|---|---|
| ADDRESS | 4 | 2 | 50% |
| CARD | 1 | 1 | 100% |
| DATE | 10 | 9 | 90% |
| EMAIL | 9 | 9 | 100% |
| MEMBER_ID | 7 | 7 | 100% |
| NAME | 17 | 12 | 71% |
| PHONE | 7 | 6 | 86% |
| SSN | 1 | 1 | 100% |
| **All** | **56** | **47** | **84%** |

Precision is 96%: of 49 things flagged, 47 were real personal details.

Reproduce it with `python evals/run_deid_eval.py`, which also lists every miss and false positive.

### What it misses, and why

The test set includes hard cases on purpose. The current misses:

- **Names of other people.** The redactor knows the customer's name from the ticket record, but not a neighbor's or a vet's. "Carol Jennings" and "Dr. Okafor" get through.
- **Nicknames and partial names.** "Sam" for Samuel and "Chloe B." are missed or only partly covered.
- **Details written in words.** A phone number spelled out ("two zero six...") and a date written as "March 3rd 2026" don't match the patterns.
- **Unusual addresses.** "77 Harbor View" has no street suffix, and "Avenue South" is only partly covered.

And two false positives: the company's own support number and a vet clinic's street address were redacted, though neither is a customer's personal detail.

Rule-based detection is predictable and easy to audit, which matters for regulated data, but 84% recall is not good enough to rely on alone. The next step is to close the cheap gaps with better rules, then compare against a named-entity model for names.

## Design choices

- **Rules first, model later.** Patterns are fast, free, and explainable. Each miss above is a specific, fixable case.
- **Card numbers need a valid checksum.** A 16-digit invoice number is not redacted as a card, which avoids a common false positive.
- **Reversible by design.** The mapping stays on our side, so the final reply can use the customer's real details without the model having seen them.
- **Hard cases in the test set.** A test set the redactor scores 100% on would say nothing about where it fails.

## Run it

Requires Python 3.10 or newer. The redactor uses only the standard library.

```
python evals/run_deid_eval.py      # evaluation
pip install pytest && pytest       # tests
```

## Roadmap

1. Fix the cheap misses: more date formats, capitalized "My daughter ..." phrases, addresses with a direction suffix.
2. Write a small knowledge base of support articles for the agent to ground its replies in.
3. Build the agent that drafts replies from redacted tickets.
4. Evaluate the drafts: is the reply correct, grounded in the knowledge base, and free of leaked details?

## A note on how this was built

The problem and the approach come from my day job, working on AI support tooling in a regulated industry. The first version of the redactor and the test tickets was written with Claude as a coding assistant.
