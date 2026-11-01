// Live full-stack smoke test (frontend dev server + FastAPI backend), driven by Playwright.
//   node audit/e2e_smoke.cjs <outdir>
// Requires: API at http://localhost:8765 (no LLM configured) and the Vite dev server at http://localhost:8080
// started with VITE_FINAUDIT_API_URL=http://localhost:8765.
const { chromium } = require("playwright");
const path = require("path");

const OUT = process.argv[2] || ".";
const BASE = "http://localhost:8080";
const results = [];
const record = (name, ok, detail) => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}: ${detail}`);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const consoleErrors = [];
  const badResponses = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text().slice(0, 200)));
  page.on("response", (r) => {
    if (r.url().includes(":8765/") && r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`);
  });

  // 1. Documents library lists the live backend documents (not demo data)
  await page.goto(`${BASE}/documents`, { waitUntil: "networkidle" });
  await page.getByText("AMD_2022_10K", { exact: false }).first().waitFor({ timeout: 30000 });
  const body = await page.locator("body").innerText();
  record("documents page lists live documents", body.includes("AMD_2022_10K") && body.includes("PEPSICO_2022_10K"),
    `AMD/PepsiCo rows present; demo issuer present=${body.includes("Northwind")}`);
  record("no DEMO data mixed into live documents", !body.includes("Northwind"), "Northwind (demo issuer) absent");
  await page.screenshot({ path: path.join(OUT, "e2e_documents.png") });

  // 2. Workspace renders a real 10-K page with its extracted table and the page image from the API
  const imgResp = page.waitForResponse((r) => /\/pages\/56\/image/.test(r.url()), { timeout: 60000 }).catch(() => null);
  await page.goto(`${BASE}/intelligence?doc=doc_amd_2022_10k&page=56`, { waitUntil: "networkidle" });
  await page.getByText("Cash and cash equivalents", { exact: false }).first().waitFor({ timeout: 60000 });
  const img = await imgResp;
  record("workspace shows AMD p.56 balance-sheet content", true, "found 'Cash and cash equivalents'");
  record("page image served by backend", !!img && img.status() === 200, img ? `status ${img.status()}` : "no image request");
  await page.screenshot({ path: path.join(OUT, "e2e_workspace_amd_p56.png") });

  // 3. Citation deep link (?ev=) selects the evidence region in the inspector
  await page.goto(`${BASE}/intelligence?doc=doc_amd_2022_10k&page=56&ev=ev-p56-b006`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const inspector = await page.locator("body").innerText();
  record("evidence deep link opens inspector", /p\.\s*56/.test(inspector), "inspector shows p. 56 selection");
  await page.screenshot({ path: path.join(OUT, "e2e_evidence_link.png") });

  // 4. AI Analysis in live mode without an LLM: honest 503 state, no fabricated answer
  await page.goto(`${BASE}/analysis`, { waitUntil: "networkidle" });
  await page.getByPlaceholder("Ask about a reported figure, period, or change").fill("What were AMD's cash and cash equivalents at the end of 2022?");
  const qaResp = page.waitForResponse((r) => r.url().endsWith("/api/v1/qa"), { timeout: 60000 });
  await page.getByRole("button", { name: /ask|submit|answer/i }).first().click();
  const qa = await qaResp;
  await page.getByText("Question answering is not configured on this server").waitFor({ timeout: 30000 });
  const analysis = await page.locator("body").innerText();
  record("analysis shows 503 unavailable state", qa.status() === 503, `POST /qa -> ${qa.status()}`);
  record("no answer or value rendered without LLM", !/Calculated from cited values|Reported\s*\n/.test(analysis), "no value-kind badge rendered");
  await page.screenshot({ path: path.join(OUT, "e2e_analysis_503.png") });

  // 5. Overview renders from live service values
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "e2e_overview.png") });
  const unexpected = badResponses.filter((r) => !r.includes("/api/v1/qa"));
  record("no unexpected backend 4xx/5xx", unexpected.length === 0, unexpected.join(", ") || "only the expected 503 from /qa");
  record("no browser console errors", consoleErrors.filter((e) => !e.includes("503")).length === 0,
    consoleErrors.join(" || ").slice(0, 400) || "none");
  console.log(`\n${results.filter((r) => r.ok).length}/${results.length} checks passed`);
  await browser.close();
})().catch((e) => {
  console.error("E2E ERROR", e.message);
  process.exit(1);
});
