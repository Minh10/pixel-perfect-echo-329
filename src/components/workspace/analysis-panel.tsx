import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { MessageSquareText } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";
import { EmptyState, ErrorState, PageHeader } from "@/components/app/states";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { ApiError, apiAsset } from "@/lib/api/http-service";
import { IS_DEMO, api, documentsQuery } from "@/lib/api/service";
import type { QACitation, QAResponse, ValueKind } from "@/lib/api/types";

const VALUE_KIND: Record<ValueKind, string> = {
  reported: "Reported",
  calculated: "Calculated from cited values",
  visual_estimate: "Visual estimate from chart, approximate",
};

const KIND_TAG: Record<QACitation["evidenceKind"], string> = {
  table: "table",
  figure: "figure",
  text: "narrative",
  window: "narrative",
};

export function AnalysisPanel({
  documentId,
  embedded = false,
}: {
  documentId?: string | undefined;
  embedded?: boolean;
}) {
  if (IS_DEMO || !api.ask) {
    if (embedded)
      return (
        <p className="border-l-2 border-primary bg-primary-soft p-4 text-sm text-muted-foreground">
          Public sample only. Live analysis requires an activated demo session; no AI result is
          generated.
        </p>
      );
    return (
      <PendingModule
        eyebrow="Analysis"
        title="Ask a question"
        description="Ask questions about a report and receive answers cited to specific pages, tables and charts."
        icon={<MessageSquareText className="size-5" />}
      />
    );
  }
  return <AnalysisWorkspace requestedId={documentId} embedded={embedded} />;
}

function AnalysisWorkspace({
  requestedId,
  embedded = false,
}: {
  requestedId?: string | undefined;
  embedded?: boolean;
}) {
  const navigate = useNavigate();
  const documents = useQuery(documentsQuery());
  const ready = (documents.data ?? []).filter((doc) => doc.status === "ready");
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState<string[]>(requestedId ? [requestedId] : []);
  const mutation = useMutation({
    mutationFn: (body: { question: string; documentIds?: string[] }) => {
      if (!api.ask) throw new Error("Questions unavailable");
      return api.ask(body);
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = question.trim();
    if (!text || mutation.isPending) return;
    mutation.mutate(
      selected.length > 0 ? { question: text, documentIds: selected } : { question: text },
    );
  };

  const toggle = (id: string) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const result = mutation.isSuccess ? mutation.data : null;

  return (
    <div className={embedded ? "@container min-w-0 space-y-5 p-5" : "page-layout space-y-6"}>
      {!embedded && (
        <PageHeader
          eyebrow="Analysis"
          title="Ask a question"
          description="Answers cite source passages, tables and charts. If evidence is insufficient, no supported answer is given."
        />
      )}
      {selected.length > 0 && (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Selected reports: </span>
          {ready
            .filter((doc) => selected.includes(doc.id))
            .map((doc) => doc.title)
            .join(" · ")}
        </p>
      )}
      <form onSubmit={submit} className="space-y-4">
        <div className="flex flex-col gap-2 @md:flex-row">
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about a reported figure, period, or change"
            aria-label="Financial question"
            disabled={mutation.isPending}
          />
          <Button type="submit" disabled={mutation.isPending || question.trim().length === 0}>
            {mutation.isPending ? "Asking…" : "Ask"}
          </Button>
        </div>
        <details className="border-y py-3" open={requestedId ? undefined : true}>
          <summary className="cursor-pointer text-sm font-medium">
            {selected.length > 0
              ? `Reports included · ${selected.length} selected`
              : "Reports included · automatic selection"}
          </summary>
          <fieldset className="mt-3 space-y-2">
            <legend className="text-xs text-muted-foreground">
              {requestedId
                ? "The open report is already selected. Type a question, or add another report."
                : "No report selected: matching reports are chosen using the company named in your question."}
            </legend>
            {documents.isError && (
              <p className="text-sm text-destructive">
                {documents.error instanceof Error
                  ? documents.error.message
                  : "Could not load documents."}
              </p>
            )}
            {ready.length === 0 && !documents.isLoading && !documents.isError && (
              <p className="text-sm text-muted-foreground">
                No processed documents are available yet.
              </p>
            )}
            <ul className="grid gap-2 @lg:grid-cols-2">
              {ready.map((doc) => (
                <li key={doc.id}>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selected.includes(doc.id)}
                      onChange={() => toggle(doc.id)}
                      disabled={mutation.isPending}
                    />
                    <span>
                      <span className="font-medium">{doc.title}</span>
                      <span className="block text-xs text-muted-foreground">
                        {[doc.issuer, doc.period].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        </details>
      </form>

      {mutation.isError && (
        <AnalysisError error={mutation.error} onRetry={() => mutation.reset()} />
      )}

      {result?.status === "abstained" && (
        <div className="space-y-4">
          <EmptyState
            title="No supported answer"
            description={result.abstention?.detail || "The service abstained."}
          />
          <AnswerFooter result={result} />
        </div>
      )}

      {result?.status === "answered" && (
        <article className="space-y-6 rounded-md border bg-card p-5">
          {result.answer && <p className="text-sm leading-relaxed">{result.answer}</p>}
          {result.value && (
            <p className="text-sm">
              <span className="font-mono text-lg font-semibold tabular">{result.value.value}</span>
              {result.value.unit && (
                <span className="ml-2 text-muted-foreground">{result.value.unit}</span>
              )}
              <span className="ml-3 text-xs font-medium text-primary">
                {VALUE_KIND[result.value.valueKind]}
              </span>
            </p>
          )}
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="text-sm font-medium">
              How this was calculated
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 space-y-3">
              {result.operands.map((operand) => (
                <p key={operand.id} className="text-sm">
                  <span className="font-medium">{operand.label}</span>
                  <span className="font-mono"> = {operand.quote}</span>
                  <span className="text-muted-foreground"> [{operand.evidenceId}]</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {KIND_TAG[operand.evidenceKind]}
                  </span>
                  <span className="ml-2 text-xs text-primary">{VALUE_KIND[operand.valueKind]}</span>
                  {(operand.rowLabel || operand.period) && (
                    <span className="block text-xs text-muted-foreground">
                      Source row “{operand.rowLabel ?? "?"}”
                      {operand.period ? ` · period ${operand.period}` : ""}
                      {operand.periodType && operand.periodType !== "unknown"
                        ? ` (${operand.periodType.replace(/_/g, " ")})`
                        : ""}
                      {operand.binding === "fact" ? " · bound to table cell" : ""}
                    </span>
                  )}
                </p>
              ))}
              {result.calculations.map((step) => (
                <p key={step.id} className="font-mono text-xs">
                  {step.description}: {step.op}({step.inputs.map((input) => input.value).join(", ")}
                  ) = {step.result}
                </p>
              ))}
              {result.operands.length === 0 && result.calculations.length === 0 && (
                <p className="text-sm text-muted-foreground">No calculation steps were returned.</p>
              )}
            </CollapsibleContent>
          </Collapsible>
          <ul className="space-y-3">
            {result.citations.map((citation) => {
              const region = citation.chunk.regions[0];
              const page = region?.page ?? citation.chunk.pages[0];
              return (
                <li key={`${citation.evidenceId}-${citation.chunk.chunkId}`}>
                  <Button
                    variant="ghost"
                    type="button"
                    className="block h-auto w-full whitespace-normal rounded-md border px-3 py-3 text-left hover:bg-primary-soft/40"
                    aria-label={`View source on page ${page ?? "unknown"}`}
                    onClick={() =>
                      navigate({
                        to: "/intelligence",
                        search: {
                          tool: "ask",
                          doc: citation.chunk.documentId,
                          ...(typeof page === "number" ? { page } : {}),
                          ...(region?.workspaceEvidenceId
                            ? { ev: region.workspaceEvidenceId }
                            : {}),
                          chunk: citation.chunk.chunkId,
                        },
                      })
                    }
                  >
                    <span className="text-xs text-muted-foreground">
                      {[
                        citation.chunk.documentTitle,
                        page ? `p. ${page}` : null,
                        citation.chunk.sectionPath.join(" › "),
                        KIND_TAG[citation.evidenceKind],
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    {citation.quote && <span className="mt-1 block text-sm">{citation.quote}</span>}
                    {citation.chunk.table?.units && (
                      <span className="mt-1 block font-mono text-[11px] text-muted-foreground">
                        Units: {citation.chunk.table.units}
                      </span>
                    )}
                    {citation.chunk.figure?.imageUrl && (
                      <img
                        src={apiAsset(citation.chunk.figure.imageUrl)}
                        alt={citation.chunk.figure.caption ?? "Cited figure"}
                        className="mt-2 max-h-32 max-w-full"
                      />
                    )}
                  </Button>
                </li>
              );
            })}
          </ul>
          <AnswerFooter result={result} />
        </article>
      )}
    </div>
  );
}

function AnswerFooter({ result }: { result: QAResponse }) {
  const considered = result.documentsConsidered
    .map((doc) => doc.title || doc.issuer || doc.documentId)
    .filter(Boolean)
    .join(", ");
  return (
    <footer className="space-y-1 border-t pt-3 text-xs text-muted-foreground">
      <p>{result.note}</p>
      <p>
        {[
          result.usage.model,
          result.timingsMs["total_ms"] != null ? `${result.timingsMs["total_ms"]} ms` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
        {result.usage.costUsd != null ? ` · $${result.usage.costUsd}` : ""}
      </p>
      {considered && <p>Documents considered: {considered}</p>}
      {result.warnings.map((warning) => (
        <p key={warning}>{warning}</p>
      ))}
    </footer>
  );
}

function AnalysisError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const unavailable =
    error instanceof ApiError && (error.status === 503 || error.code === "llm_unavailable");
  return (
    <div className="space-y-3">
      <ErrorState
        title={
          unavailable
            ? "Question service temporarily unavailable"
            : "The question could not be answered"
        }
        message={
          error instanceof Error
            ? error.message
            : "The analysis service returned an error. No answer was generated."
        }
        onRetry={onRetry}
      />
      <Button asChild variant="outline" size="sm">
        <Link to="/intelligence">Inspect source evidence</Link>
      </Button>
    </div>
  );
}
