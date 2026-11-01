import { useEffect, useRef, useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Search, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ApiError } from "@/lib/api/http-service";
import { IS_DEMO, api, documentsQuery, jobQuery } from "@/lib/api/service";
import type { DocumentType, Job, UploadMeta } from "@/lib/api/types";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";

const DOCUMENT_TYPES: DocumentType[] = [
  "Annual Report",
  "Quarterly Report",
  "Prospectus",
  "Sustainability Report",
];

export const Route = createFileRoute("/documents")({
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Documents — FINAUDIT AI" },
      {
        name: "description",
        content: "Library of uploaded financial reports and their processing status.",
      },
      { property: "og:title", content: "Documents — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Library of uploaded financial reports and their processing status.",
      },
    ],
  }),
  pendingComponent: PageSkeleton,
  errorComponent: function DocumentsError({ error }) {
    const router = useRouter();
    const unavailable =
      error instanceof ApiError &&
      (error.code === "backend_unavailable" || error.code === "timeout");
    return (
      <div className="p-8">
        <ErrorState
          title={unavailable ? "Document service unavailable" : "Couldn't load documents"}
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => router.invalidate()}
        />
      </div>
    );
  },
  component: Documents,
});

function Documents() {
  const { data } = useSuspenseQuery(documentsQuery());
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [issuer, setIssuer] = useState("");
  const [period, setPeriod] = useState("");
  const [type, setType] = useState<DocumentType | "">("");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [activeJob, setActiveJob] = useState<{ id: string; fileName: string } | null>(null);
  const [uploading, setUploading] = useState(false);

  const filtered = data.filter((d) =>
    `${d.title} ${d.issuer ?? ""} ${d.period ?? ""}`.toLowerCase().includes(q.toLowerCase()),
  );

  const onFile = async (file: File | undefined) => {
    if (!file || !api.uploadDocument) return;
    if (file.type && file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Choose a PDF file.");
      return;
    }
    const meta: UploadMeta = { title: file.name.replace(/\.pdf$/i, "") };
    if (issuer.trim()) meta.issuer = issuer.trim();
    if (period.trim()) meta.period = period.trim();
    if (type) meta.type = type;
    setUploading(true);
    setUploadProgress(0);
    try {
      const { job } = await api.uploadDocument(file, meta, setUploadProgress);
      setActiveJob({ id: job.id, fileName: file.name });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Upload accepted. Processing has started.");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Upload failed.";
      toast.error(message);
      setActiveJob(null);
    } finally {
      setUploading(false);
      setUploadProgress(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onSettled = async (job: Job) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["documents"] }),
      queryClient.invalidateQueries({ queryKey: ["document", job.documentId] }),
      queryClient.invalidateQueries({ queryKey: ["pages", job.documentId] }),
      queryClient.invalidateQueries({ queryKey: ["evidence", job.documentId] }),
    ]);
    if (job.state === "failed") {
      const doc = await api.getDocument(job.documentId).catch(() => null);
      toast.error(doc?.error?.message ?? job.error?.message ?? "Processing failed.");
    } else {
      toast.success("Document is ready to inspect.");
    }
    setActiveJob(null);
  };

  return (
    <div className="page-layout space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Documents"
        description={
          IS_DEMO
            ? "Annual reports, interims and prospectuses available for analysis."
            : "Upload a financial PDF. Processing runs in the background, then the report opens in Document Intelligence."
        }
        actions={
          IS_DEMO ? (
            <Button disabled title="Upload requires the backend API">
              <Upload /> Upload report
            </Button>
          ) : (
            <Button disabled={uploading} onClick={() => fileRef.current?.click()}>
              <Upload /> {uploading ? "Uploading…" : "Upload report"}
            </Button>
          )
        }
      />
      {!IS_DEMO && (
        <form
          className="grid gap-3 rounded-md border bg-card p-4 sm:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            fileRef.current?.click();
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={(event) => void onFile(event.target.files?.[0])}
          />
          <div className="space-y-1.5">
            <Label htmlFor="issuer">Issuer</Label>
            <Input
              id="issuer"
              value={issuer}
              onChange={(event) => setIssuer(event.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="period">Period</Label>
            <Input
              id="period"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doctype">Type</Label>
            <select
              id="doctype"
              value={type}
              onChange={(event) => setType(event.target.value as DocumentType | "")}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">Optional</option>
              {DOCUMENT_TYPES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </form>
      )}
      {uploadProgress !== null && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Uploading PDF · {Math.round(uploadProgress * 100)}%
          </p>
          <Progress value={uploadProgress * 100} />
        </div>
      )}
      {activeJob && (
        <JobProgress jobId={activeJob.id} fileName={activeJob.fileName} onSettled={onSettled} />
      )}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          aria-label="Filter documents"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by title, issuer or period"
          className="pl-8"
        />
      </div>
      {data.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description={
            IS_DEMO
              ? "The demo library is empty."
              : "Upload a financial PDF to process pages, tables, figures and evidence."
          }
          action={
            !IS_DEMO ? (
              <Button size="sm" onClick={() => fileRef.current?.click()}>
                <Upload /> Upload report
              </Button>
            ) : undefined
          }
        />
      ) : filtered.length ? (
        <DocumentsTable documents={filtered} />
      ) : (
        <EmptyState
          title="No matching documents"
          description="Try a different issuer name or reporting period."
          action={
            <Button variant="outline" size="sm" onClick={() => setQ("")}>
              Clear filter
            </Button>
          }
        />
      )}
    </div>
  );
}

function JobProgress({
  jobId,
  fileName,
  onSettled,
}: {
  jobId: string;
  fileName: string;
  onSettled: (job: Job) => void;
}) {
  const { data, error } = useQuery(jobQuery(jobId));
  const settled = useRef(false);
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;

  useEffect(() => {
    if (!data || settled.current) return;
    if (data.state === "succeeded" || data.state === "failed") {
      settled.current = true;
      onSettledRef.current(data);
    }
  }, [data]);

  useEffect(() => {
    if (error)
      toast.error(error instanceof Error ? error.message : "Could not read processing status.");
  }, [error]);

  return (
    <div className="space-y-2 rounded-md border bg-card p-4">
      <p className="text-sm font-medium">{fileName}</p>
      <p className="text-xs capitalize text-muted-foreground">
        {data ? `${data.stage} · ${Math.round(data.progress * 100)}%` : "Waiting for the worker…"}
      </p>
      <Progress value={(data?.progress ?? 0) * 100} />
    </div>
  );
}
