import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type { FinDocument } from "@/lib/api/types";
import { IS_DEMO, jobQuery } from "@/lib/api/service";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DocStatus } from "./doc-status";
import { FileText, ArrowUpRight } from "lucide-react";

function display(value: string | null | undefined) {
  const text = value?.trim();
  return text ? text : "—";
}

function formatUploadedAt(value: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function StatusCell({ doc }: { doc: FinDocument }) {
  const jobId = !IS_DEMO && doc.status === "processing" ? doc.latestJobId : null;
  const { data: job } = useQuery({
    ...jobQuery(jobId ?? "idle"),
    enabled: Boolean(jobId),
  });

  return (
    <div className="min-w-0">
      <DocStatus status={doc.status} />
      {job && doc.status === "processing" && (
        <p className="mt-1 text-[11px] capitalize text-muted-foreground">
          {job.stage} · {Math.round(job.progress * 100)}%
        </p>
      )}
      {doc.status === "failed" && doc.error?.message && (
        <p className="mt-1 max-w-52 text-[11px] text-destructive">{doc.error.message}</p>
      )}
    </div>
  );
}

export function DocumentsTable({ documents }: { documents: FinDocument[] }) {
  return (
    <div className="overflow-hidden border-y bg-card">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50">
            <TableHead className="h-12 pl-5">Document</TableHead>
            <TableHead className="h-12 hidden xl:table-cell">Type</TableHead>
            <TableHead className="h-12 hidden sm:table-cell">Period</TableHead>
            <TableHead className="h-12 text-right hidden md:table-cell">Pages</TableHead>
            <TableHead className="h-12 hidden xl:table-cell">Uploaded</TableHead>
            <TableHead className="h-12 pr-5">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((d) => (
            <TableRow
              key={d.id}
              className="document-row hover:bg-primary-soft/50 focus-within:bg-primary-soft/50"
            >
              <TableCell className="py-4 pl-5 whitespace-normal">
                <div className="flex items-center gap-3">
                  <FileText className="hidden size-5 shrink-0 text-muted-foreground sm:block" />
                  <div className="min-w-0">
                    {d.status === "ready" ? (
                      <Link
                        to="/intelligence"
                        search={{ doc: d.id }}
                        className="action-link inline-flex max-w-full items-center gap-2 break-words rounded-sm font-semibold hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {d.title}
                        <ArrowUpRight className="hidden size-3.5 shrink-0 text-muted-foreground sm:block" />
                      </Link>
                    ) : (
                      <span className="font-medium">{d.title}</span>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      {display(d.issuer)}
                      <span className="sm:hidden"> · {display(d.period)}</span>
                    </p>
                  </div>
                </div>
              </TableCell>
              <TableCell className="hidden text-sm text-muted-foreground xl:table-cell">
                {display(d.type)}
              </TableCell>
              <TableCell className="hidden text-sm tabular sm:table-cell">
                {display(d.period)}
              </TableCell>
              <TableCell className="hidden text-right text-sm tabular md:table-cell">
                {d.pages}
              </TableCell>
              <TableCell className="hidden text-xs text-muted-foreground xl:table-cell">
                {formatUploadedAt(d.uploadedAt)}
              </TableCell>
              <TableCell className="pr-5">
                <StatusCell doc={d} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
