import { expect, test } from "@playwright/test";

// Canned agent responses captured from the live agent, so the smoke is hermetic
// (no live agent, no network). The SSE stream is intentionally not asserted here:
// Playwright's route.fulfill does not reliably drive an EventSource, so this smoke
// covers the data-loaded dashboard (the surface where the graph-edge regression
// lived) rather than the streamed reveal.
import drift from "./fixtures/drift.json";
import lineage from "./fixtures/lineage.json";
import modelCard from "./fixtures/model-card.json";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/lineage*", (r) => r.fulfill({ json: lineage }));
  await page.route("**/api/drift*", (r) => r.fulfill({ json: drift }));
  await page.route("**/api/model-card*", (r) => r.fulfill({ json: modelCard }));
});

test("lineage graph renders connected edges", async ({ page }) => {
  // Regression guard for the node-handle bug: without React Flow <Handle>
  // components on the custom node, every edge is silently dropped and the graph
  // renders as disconnected nodes. Assert edges actually render.
  await page.goto("/dashboard");
  await expect(page.locator(".react-flow__node").first()).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(() => page.locator(".react-flow__edge").count(), { timeout: 20_000 })
    .toBeGreaterThan(0);
});

test("dashboard renders its three data panels from the catalog", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("AGENT REASONING")).toBeVisible();
  await expect(page.getByText("DATAHUB ML LINEAGE")).toBeVisible();
  await expect(page.getByText("DRIFT SIGNAL")).toBeVisible();
  // the model card renders from the mocked /api/model-card
  await expect(page.getByText("MODEL CARD")).toBeVisible({ timeout: 15_000 });
});
