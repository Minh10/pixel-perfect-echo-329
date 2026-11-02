# Ask AI verification — 2026-11-02

## Changes

- Keep the open report in the question scope, including when extra reports are selected.
- Suggest questions only from that report's parsed metrics and known periods; suggestions are not guarantees that the current model/validator can answer them.
- Use the existing allowed five-result retrieval setting, a multiline question field, explicit source quotes, and collapsible calculation details.
- Distinguish source-validation failure from absence of evidence; never substitute an unverified answer.
- No Windows backend, tunnel, secrets, guards, or usage limits changed. Not published in this task.

## Live preview verification

Public real PDF: Berkshire Hathaway's First Quarter 2025 Earnings Release, dated May 3, 2025, from https://www.berkshirehathaway.com/news/may0325.pdf.

One upload through the PDF control: Ready, two pages, 30 parsed financial facts, seven evidence regions. The original text contains net earnings of $4,603 million for Q1 2025 and operating earnings of $11,222 million for Q1 2024.

| Question | Actual result |
| --- | --- |
| Why can investment gains/losses be misleading? | PASS: supported narrative answer, two verbatim citations on pages 1 and 2; source click opens page 1 and highlights the cited chunk. |
| Forecast revenue in 2030? | PASS: insufficient-evidence abstention, no invented forecast. |
| Q1 2025 net earnings? | BLOCKED: duplicate matching table cells rejected by FastAPI validator. |
| Q1 2024 operating earnings? | BLOCKED: quote-verbatim and operand-reference validation. |
| Insurance float at March 31, 2025? | BLOCKED: quote and period binding validation. |
| Q1 2025 BNSF operating earnings? | BLOCKED: source quote containing the year rejected as more than one number. |
| Definition of operating earnings? | BLOCKED: model proposed a nonnumeric operand; validator requires a number. |

Seven QA submissions reported 12 Windows model calls including repairs; no Gateway calls. No claim is made about the remaining global model budget.

106 automated tests passed; lint has zero errors and six existing component-export warnings. Desktop live flow had no browser runtime errors or horizontal overflow. Successful narrative answer and both citation quotes were compared with the original PDF; numeric answer correctness is not verified because those answers were withheld.

## Remaining blocker

Reliable numeric and some narrative answers require a Windows FastAPI QA prompt/validator fix. The readable PDF has the relevant data; this is not an OCR problem. Preserve source/period/unit checks, but resolve duplicate equivalent cells, prevent fabricated/nonverbatim operand quotes, and allow narrative answers without numeric operands. No backend changes were applied here.