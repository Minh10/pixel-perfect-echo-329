import { ArrowUpRight, FileText, Table2, ScanLine, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { IS_DEMO } from "@/lib/api/service";
import type { DocumentPage, Evidence, FinDocument } from "@/lib/api/types";

export function ReportOverview({
  doc,
  pages,
  evidence,
  current,
  onPage,
  onEvidence,
}: {
  doc: FinDocument;
  pages: DocumentPage[];
  evidence: Evidence[];
  current: number;
  onPage: (page: number) => void;
  onEvidence: () => void;
}) {
  const page = pages.find((item) => item.number === current);
  const regions = evidence.filter((item) => item.page === current);
  const counts = [
    { label: "Pages", value: pages.length, icon: FileText },
    { label: "Regions", value: evidence.length, icon: ScanLine },
    {
      label: "Tables",
      value: evidence.filter((item) => item.category === "table").length,
      icon: Table2,
    },
  ];
  return (
    <div className="report-overview p-5 xl:p-6">
      <div className="mb-6 flex items-center justify-between">
        <p className="eyebrow">DOCUMENT INTELLIGENCE</p>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-1.5 rounded-full bg-success" />
          {IS_DEMO ? "Illustrative sample" : "Pages ready"}
        </span>
      </div>
      <h2 className="text-xl font-semibold leading-snug">{doc.issuer || doc.title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        {[doc.type, doc.period].filter(Boolean).join(" · ") || doc.filename || "Financial report"}
      </p>
      <div className="my-6 grid grid-cols-3 divide-x border-y py-4">
        {counts.map(({ label, value, icon: Icon }) => (
          <div key={label} className="px-3 first:pl-0">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon className="size-3" />
              {label}
            </span>
            <p className="mt-2 font-mono text-2xl font-medium tabular">{value}</p>
          </div>
        ))}
      </div>
      <section aria-label="Current page intelligence" className="mb-7">
        <div className="mb-2 flex items-center justify-between">
          <p className="eyebrow">ON THIS PAGE</p>
          <span className="font-mono text-xs text-muted-foreground">
            {String(current).padStart(2, "0")} / {pages.length}
          </span>
        </div>
        <h3 className="text-base font-medium">{page?.section || `Page ${current}`}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {regions.length
            ? `${regions.length} detected regions · ${Array.from(new Set(regions.map((item) => item.category))).join(", ")}`
            : "No evidence regions recorded on this page."}
        </p>
        {regions.length > 0 && (
          <Button variant="ghost" size="sm" className="mt-2 px-0 text-primary" onClick={onEvidence}>
            Inspect page evidence <ArrowUpRight className="size-3.5" />
          </Button>
        )}
        {page?.hasTextLayer === false && !IS_DEMO && (
          <p className="mt-2 text-xs text-warning">
            No text layer reported. Extraction may be incomplete.
          </p>
        )}
      </section>
      <section aria-label="Document outline">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="eyebrow">DOCUMENT OUTLINE</h3>
          <span className="text-xs text-muted-foreground">{pages.length} pages</span>
        </div>
        <div className="space-y-0.5">
          {pages.map((item) => (
            <Button
              key={item.number}
              variant="ghost"
              aria-current={item.number === current ? "page" : undefined}
              className="h-auto min-h-10 w-full justify-start gap-3 rounded-sm px-2 py-2 text-left data-[current=true]:bg-secondary"
              data-current={item.number === current}
              onClick={() => onPage(item.number)}
            >
              <span className="w-5 shrink-0 font-mono text-xs text-muted-foreground">
                {String(item.number).padStart(2, "0")}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-normal">
                {item.section || `Page ${item.number}`}
              </span>
              <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
            </Button>
          ))}
        </div>
      </section>
      <details className="mt-6 border-t pt-4 text-xs text-muted-foreground">
        <summary className="cursor-pointer font-medium">
          Source & extraction details
          {doc.warnings?.length ? ` · ${doc.warnings.length} notices` : ""}
        </summary>
        <dl className="mt-3 space-y-2">
          <div>Status: {doc.status}</div>
          {doc.parser && (
            <div>
              Parser: {doc.parser.name} {doc.parser.version}
            </div>
          )}
          {doc.processedAt && <div>Processed: {doc.processedAt}</div>}
          {doc.filename && <div className="break-all">File: {doc.filename}</div>}
        </dl>
        {doc.warnings?.map((warning, index) => (
          <p key={index} className="mt-2 leading-relaxed">
            {warning}
          </p>
        ))}
      </details>
      {IS_DEMO && (
        <p className="mt-5 border-t pt-4 text-xs leading-relaxed text-muted-foreground">
          DEMO · Public synthetic report. Regions and values are illustrative, not verified
          financial findings.
        </p>
      )}
    </div>
  );
}
