import { Link } from "@tanstack/react-router";
import type { FinDocument } from "@/lib/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DocStatus } from "./doc-status";

export function DocumentsTable({ documents }: { documents: FinDocument[] }) {
  return (
    <div className="overflow-hidden rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50">
            <TableHead className="eyebrow h-9">Document</TableHead>
            <TableHead className="eyebrow h-9 hidden md:table-cell">Type</TableHead>
            <TableHead className="eyebrow h-9">Period</TableHead>
            <TableHead className="eyebrow h-9 text-right hidden sm:table-cell">Pages</TableHead>
            <TableHead className="eyebrow h-9 hidden md:table-cell">Uploaded</TableHead>
            <TableHead className="eyebrow h-9">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((d) => (
            <TableRow key={d.id}>
              <TableCell className="py-3">
                {d.status === "ready" ? (
                  <Link to="/intelligence" search={{ doc: d.id }} className="font-medium hover:text-evidence hover:underline">{d.title}</Link>
                ) : (
                  <span className="font-medium">{d.title}</span>
                )}
                <p className="text-xs text-muted-foreground">{d.issuer}</p>
              </TableCell>
              <TableCell className="hidden text-sm md:table-cell">{d.type}</TableCell>
              <TableCell className="font-mono text-xs">{d.period}</TableCell>
              <TableCell className="hidden text-right font-mono text-xs tabular sm:table-cell">{d.pages}</TableCell>
              <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">{d.uploadedAt}</TableCell>
              <TableCell><DocStatus status={d.status} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
