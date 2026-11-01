import { Link } from "@tanstack/react-router";
import type { FinDocument } from "@/lib/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DocStatus } from "./doc-status";
import { FileText, ArrowUpRight } from "lucide-react";

export function DocumentsTable({ documents }: { documents: FinDocument[] }) {
  return (
    <div className="overflow-hidden rounded-md border bg-card">
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
            <TableRow key={d.id} className="hover:bg-primary-soft/50 focus-within:bg-primary-soft/50">
              <TableCell className="py-5 pl-5 whitespace-normal">
                <div className="flex items-center gap-3"><FileText className="hidden size-5 shrink-0 text-muted-foreground sm:block" /><div className="min-w-0">
                {d.status === "ready" ? (
                  <Link to="/intelligence" search={{ doc: d.id }} className="inline-flex items-center gap-2 rounded-sm font-semibold hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{d.title}<ArrowUpRight className="hidden size-3.5 shrink-0 text-muted-foreground sm:block" /></Link>
                ) : (
                  <span className="font-medium">{d.title}</span>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{d.issuer}<span className="sm:hidden"> · {d.period}</span></p>
                </div></div>
              </TableCell>
              <TableCell className="hidden text-sm text-muted-foreground xl:table-cell">{d.type}</TableCell>
              <TableCell className="hidden text-sm tabular sm:table-cell">{d.period}</TableCell>
              <TableCell className="hidden text-right text-sm tabular md:table-cell">{d.pages}</TableCell>
              <TableCell className="hidden text-xs text-muted-foreground xl:table-cell">{d.uploadedAt}</TableCell>
              <TableCell className="pr-5"><DocStatus status={d.status} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
