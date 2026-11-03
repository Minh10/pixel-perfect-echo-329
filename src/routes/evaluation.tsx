import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { PageHeader } from "@/components/app/states";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import baseline from "@/lib/research/layout-baseline.json";

export const Route = createFileRoute("/evaluation")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Evaluation — FINAUDIT AI" },
      { name: "description", content: "Reproducible layout-detection baseline and explicit financial QA evaluation limitations." },
      { property: "og:title", content: "Evaluation — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Reproducible layout-detection baseline and explicit financial QA evaluation limitations.",
      },
    ],
  }),
  component: Evaluation,
});

function Evaluation() {
  return <div className="page-layout space-y-7">
    <PageHeader eyebrow="RESEARCH & METHODOLOGY" title="Evaluation" description="Reproducible experiments, observed results and explicit limits." />
    <section aria-label="Layout detection baseline">
      <div className="flex items-center gap-2"><FlaskConical className="size-4 text-primary" /><h2 className="text-lg font-semibold">PubLayNet · layout detection baseline</h2></div>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">Raw pretrained Heron detector on biomedical journal JPEG pages. This experiment measures region detection, not financial-document accuracy or AI answer quality.</p>
      <dl className="my-5 grid grid-cols-2 gap-4 border-y py-4 md:grid-cols-4">
        {[['Validation pages', baseline.sampleSize], ['IoU threshold', baseline.iou], ['Detection score threshold', baseline.scoreThreshold], ['Sampling seed', baseline.seed]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 font-mono text-lg">{value}</dd></div>)}
      </dl>
      <Table><TableHeader><TableRow><TableHead>Class / mapping</TableHead><TableHead>Role</TableHead><TableHead className="text-right">Precision</TableHead><TableHead className="text-right">Recall</TableHead><TableHead className="text-right">F1</TableHead><TableHead className="text-right">TP / FP / FN</TableHead></TableRow></TableHeader><TableBody>
        {baseline.metrics.map((row) => <TableRow key={row.class}><TableCell><span className="font-medium capitalize">{row.class}</span><span className="mt-1 block text-xs text-muted-foreground">{row.docling_labels}</span></TableCell><TableCell className="text-xs capitalize">{row.role}</TableCell>{[row.precision, row.recall, row.f1].map((value, index) => <TableCell key={index} className="text-right font-mono">{value.toFixed(3)}</TableCell>)}<TableCell className="text-right font-mono text-xs">{row.tp} / {row.fp} / {row.fn}</TableCell></TableRow>)}
      </Table>
      <p className="mt-4 border-l-2 border-warning pl-3 text-sm leading-relaxed text-muted-foreground">Figure recall is high, but precision is 0.286: 215 false positives were recorded. Split multi-panel figures are one observed source of errors, not an explanation for every false positive.</p>
      <details className="mt-4 border-t pt-3 text-xs text-muted-foreground"><summary className="cursor-pointer font-medium">Reproducibility & class definitions</summary><div className="mt-3 space-y-2 leading-relaxed"><p>Docling {baseline.doclingVersion} · {baseline.model} · revision <span className="break-all font-mono">{baseline.modelRevision}</span></p><p>Seeded sample after sorting validation image IDs; greedy one-to-one IoU matching. Title and text are secondary many-to-one mappings. List is not scored because whole-list versus list-item granularity differs.</p><p>Source: <span className="break-all font-mono">{baseline.source}</span>. Full report and reproducibility artifacts are retained in the project research folder.</p><p>No fine-tuning experiment or end-to-end financial-document benchmark was performed.</p></div></details>
    </section>
    <section className="border-t pt-5" aria-label="Evaluation scope">
      <h2 className="text-base font-semibold">What has—and has not—been measured</h2>
      <dl className="mt-3 divide-y">
        {[["Layout detection", "Measured baseline above; PDF post-processing and table structure are outside this experiment."], ["Retrieval evaluation", "No aggregate retrieval benchmark published here."], ["Financial evidence grounding", "Source and numerical regression checks are separate from dataset-level QA accuracy."], ["Model demonstrations", "Individual cited answers and chart readings are demonstrations, not benchmark scores."], ["End-to-end validation", "No comprehensive financial parsing, chart-audit or answer-accuracy score is claimed."]].map(([label, detail]) => <div key={label} className="grid gap-2 py-3 sm:grid-cols-[14rem_1fr]"><dt className="text-sm font-medium">{label}</dt><dd className="text-sm leading-relaxed text-muted-foreground">{detail}</dd></div>)}
      </dl>
    </section>
  </div>;
}
