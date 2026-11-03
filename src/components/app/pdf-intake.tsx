import { useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ApiError } from "@/lib/api/http-service";
import { DEFAULT_DOCUMENT_ID, IS_DEMO, api } from "@/lib/api/service";
import type { DocumentType, UploadMeta } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useLiveStatus } from "@/lib/live-status";

const DOCUMENT_TYPES: DocumentType[] = [
  "Annual Report",
  "Quarterly Report",
  "Prospectus",
  "Sustainability Report",
];

export function PdfIntake() {
  const live = useLiveStatus();
  if (IS_DEMO || !api.uploadDocument) return <SampleStart canActivate={live.enabled} />;
  return <LiveIntake />;
}

function SampleStart({ canActivate }: { canActivate: boolean }) {
  return (
    <section data-pointer-surface className="intake-surface border-y bg-card px-1 py-5">
      <p className="eyebrow">SYNTHETIC SAMPLE</p>
      <h2 className="mt-2 text-xl font-semibold">
        {canActivate ? "Activate the live demo to upload a PDF" : "Open the sample report"}
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
        {canActivate
          ? "Live entry is enabled. Activate a temporary session to upload; this view contains only synthetic sample data."
          : "Synthetic report available for inspection. Live PDF processing is not active in this view."}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {canActivate && (
          <Button asChild>
            <Link to="/login">Activate live demo</Link>
          </Button>
        )}
        <Button asChild variant={canActivate ? "outline" : "default"}>
          <Link to="/intelligence" search={{ doc: DEFAULT_DOCUMENT_ID ?? undefined }}>
            Open sample report
          </Link>
        </Button>
      </div>
    </section>
  );
}

function LiveIntake() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [issuer, setIssuer] = useState("");
  const [period, setPeriod] = useState("");
  const [type, setType] = useState<DocumentType | "">("");

  const onFile = async (file: File | undefined) => {
    if (!file || !api.uploadDocument || uploading) return;
    if (file.type && file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Choose a PDF file.");
      return;
    }
    const meta: UploadMeta = { title: file.name.replace(/\.pdf$/i, "") };
    if (issuer.trim()) meta.issuer = issuer.trim();
    if (period.trim()) meta.period = period.trim();
    if (type) meta.type = type;
    setUploading(true);
    setProgress(0);
    try {
      const { document } = await api.uploadDocument(file, meta, setProgress);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("PDF received. The report will open as soon as its pages are ready.");
      await navigate({ to: "/intelligence", search: { doc: document.id } });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Upload failed.";
      toast.error(message);
    } finally {
      setUploading(false);
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <section className="border-y py-5">
      <label
        data-pointer-surface
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          const file = Array.from(event.dataTransfer.files).find((item) =>
            item.name.toLowerCase().endsWith(".pdf"),
          );
          void onFile(file ?? event.dataTransfer.files[0]);
        }}
        className={cn(
          "intake-surface flex cursor-pointer flex-col items-start gap-2 rounded-md border border-dashed px-5 py-6 transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
          over ? "border-primary bg-primary-soft" : "border-border bg-background hover:bg-muted/40",
          uploading && "pointer-events-none opacity-70",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          disabled={uploading}
          onChange={(event) => void onFile(event.target.files?.[0])}
        />
        <span className="grid size-9 place-items-center rounded-md bg-primary-soft text-primary">
          <FileUp className="size-4" />
        </span>
        <span className="text-sm font-semibold">
          {uploading ? "Uploading PDF…" : "Drop a financial PDF"}
        </span>
        <span className="max-w-xl text-sm text-muted-foreground">
          PDF · optional issuer and period
        </span>
      </label>
      {progress !== null && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-muted-foreground">
            Sending PDF · {Math.round(progress * 100)}%
          </p>
          <Progress value={progress * 100} />
        </div>
      )}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          Add issuer, period, or type
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="intake-issuer">Issuer</Label>
            <Input
              id="intake-issuer"
              value={issuer}
              onChange={(event) => setIssuer(event.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="intake-period">Period</Label>
            <Input
              id="intake-period"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="intake-type">Type</Label>
            <select
              id="intake-type"
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
        </div>
      </details>
    </section>
  );
}
