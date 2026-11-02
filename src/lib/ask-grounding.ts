import type { FinancialFact, QARequest } from "./api/types";

/** Suggestions name only metrics and periods actually extracted from this report. */
export function supportedQuestions(facts: FinancialFact[], documentId: string): string[] {
  const questions = new Set<string>();
  for (const fact of facts) {
    if (
      fact.documentId !== documentId ||
      fact.valueStatus !== "parsed" ||
      fact.value === null ||
      fact.period.source === "unknown"
    )
      continue;
    const metric = fact.rowLabel
      .replace(/\.{2,}/g, "")
      .replace(/\s+/g, " ")
      .trim();
    const period = fact.period.label?.trim();
    if (!metric || !period || /^other\b/i.test(metric)) continue;
    questions.add(`What was ${metric} for ${period}?`);
    if (questions.size === 3) break;
  }
  return [...questions];
}

/** The open PDF always remains in scope, even when additional reports are selected. */
export function groundedRequest(
  question: string,
  selected: string[],
  documentId?: string,
): QARequest {
  const documentIds = [...new Set([...(documentId ? [documentId] : []), ...selected])];
  return {
    question: question.trim(),
    ...(documentIds.length ? { documentIds } : {}),
    topK: 5,
  };
}
