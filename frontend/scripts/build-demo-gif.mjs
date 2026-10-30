/**
 * Build the README media: a short GIF of a real conversation and the WebP
 * stills used in the documentation.
 *
 * It drives the running app with Playwright, so it needs a live stack with a
 * provider key configured (Groq by default):
 *
 *   npm run dev            # or any stack you already have
 *   npm run demo:media     # from the repository root
 *
 * Point it elsewhere with E2E_BASE_URL. `--stills` writes only the images and
 * no GIF. The output goes to docs/ and docs/images/.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";
import gifenc from "gifenc";
import sharp from "sharp";

const { GIFEncoder, applyPalette, quantize } = gifenc;

const STILLS_ONLY = process.argv.includes("--stills");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const docsDir = path.join(repoRoot, "docs");
const imgDir = path.join(docsDir, "images");
const frameDir = mkdtempSync(path.join(tmpdir(), "lucid-frames-"));

const BASE_URL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173";
const VIEWPORT = { width: 1120, height: 860 };
const FPS = 6;
const GIF_WIDTH = 680;
const GIF_HEIGHT = 522;

const frames = [];
let index = 0;

const COMPOSER = "#composer";
const PICKER = 'button[aria-label^="Model:"]';
const OPTIONS = '[role="option"]';
const STREAMING = "Generating response";

async function still(page, name) {
  mkdirSync(imgDir, { recursive: true });
  const file = path.join(imgDir, `${name}.webp`);
  const png = await page.screenshot();
  await sharp(png).webp({ lossless: true, effort: 6 }).toFile(file);
  console.log(`[demo] still ${path.relative(repoRoot, file)}`);
}

async function hold(page, ms) {
  if (STILLS_ONLY) {
    return;
  }
  const shots = Math.max(1, Math.round((ms / 1000) * FPS));
  for (let i = 0; i < shots; i += 1) {
    const file = path.join(frameDir, `frame-${String(index).padStart(4, "0")}.png`);
    index += 1;
    await page.screenshot({ path: file });
    frames.push(file);
  }
}

async function waitForIdle(page) {
  await page.getByText(STREAMING, { exact: true }).waitFor({ state: "hidden", timeout: 60_000 });
}

async function send(page, prompt) {
  await page.locator(COMPOSER).click();
  await page.locator(COMPOSER).fill(prompt);
  await hold(page, 500);
  await page.locator(COMPOSER).press("Enter");
}

async function startChat(page) {
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.locator(COMPOSER).waitFor({ timeout: 30_000 });
  // Start from an empty composer and a new conversation.
  await page
    .getByRole("button", { name: /New chat/ })
    .first()
    .click();
}

async function captureConversation(page) {
  console.log("[demo] first turn");
  await send(page, "Explain what a tokenizer does, in two sentences.");
  await hold(page, 3200);
  await waitForIdle(page);
  await hold(page, 1200);

  console.log("[demo] model picker");
  await page.locator(PICKER).click();
  await hold(page, 1400);
  await still(page, "model-picker");
  await page.locator(OPTIONS).filter({ hasText: "gpt-oss-20b" }).click();
  await hold(page, 900);

  console.log("[demo] second turn on another model");
  await send(page, "Why does the model never see the whole conversation?");
  await hold(page, 3200);
  await waitForIdle(page);
  await hold(page, 1600);
  await still(page, "chat");
}

async function captureDashboard(page) {
  console.log("[demo] dashboard");
  await page.getByRole("button", { name: "Dashboard" }).click();
  await page.getByRole("heading", { name: "Latest 25 attempts" }).waitFor({ timeout: 30_000 });
  await hold(page, 2600);
  await still(page, "dashboard");

  console.log("[demo] generation details");
  const details = page.locator('button[aria-label^="Open details for"]').first();
  if (await details.count()) {
    await details.click();
    await hold(page, 2200);
    await still(page, "generation-details");
    await page.keyboard.press("Escape");
  }
}

async function captureStopped(page) {
  console.log("[demo] stopped generation");
  await page
    .getByRole("button", { name: /New chat/ })
    .first()
    .click();

  await send(page, "Write a 500-word essay about how HTTP streaming reaches a browser.");

  // Groq streams very fast, so stop on a fixed short delay: by then a few
  // hundred tokens are usually on screen, which is what the still should show.
  await page.waitForTimeout(700);
  const stop = page.getByRole("button", { name: "Stop" });
  if (await stop.isVisible().catch(() => false)) {
    await stop.click();
  } else {
    console.warn("[demo] the reply finished before Stop could be clicked");
    return;
  }

  await waitForIdle(page);
  await page.waitForTimeout(400);

  const interrupted = await page.evaluate(() =>
    document.body.innerText.includes("You stopped this response"),
  );
  if (!interrupted) {
    console.warn("[demo] the attempt was not marked interrupted");
  }
  await still(page, "stopped");
}

async function captureMobile(page) {
  console.log("[demo] mobile shell");
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.locator(COMPOSER).waitFor({ timeout: 30_000 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.waitForTimeout(500);
  await still(page, "mobile-sidebar");
}

async function stitchGif() {
  console.log(`[demo] stitching ${frames.length} frames at ${FPS}fps`);
  const rgba = (file) =>
    sharp(file)
      .resize(GIF_WIDTH, GIF_HEIGHT, { fit: "cover", position: "top" })
      .ensureAlpha()
      .raw()
      .toBuffer();

  const encoder = GIFEncoder();
  const first = await rgba(frames[0]);
  const palette = quantize(first, 128, { format: "rgb565" });

  for (const [i, file] of frames.entries()) {
    const pixels = i === 0 ? first : await rgba(file);
    encoder.writeFrame(applyPalette(pixels, palette), GIF_WIDTH, GIF_HEIGHT, {
      ...(i === 0 ? { palette } : {}),
      delay: 1000 / FPS,
    });
  }
  encoder.finish();

  const target = path.join(docsDir, "demo.gif");
  mkdirSync(docsDir, { recursive: true });
  writeFileSync(target, Buffer.from(encoder.bytes()));
  console.log(
    `[demo] wrote ${path.relative(repoRoot, target)} (${(encoder.bytes().length / 1024).toFixed(0)} kB, ` +
      `${frames.length} frames, ${(frames.length / FPS).toFixed(1)}s)`,
  );
}

const browser = await chromium.launch();

try {
  const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });

  await startChat(page);
  await captureConversation(page);
  await captureDashboard(page);

  if (STILLS_ONLY) {
    await captureStopped(page);

    const mobile = await browser.newPage({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
    });
    await captureMobile(mobile);
    await mobile.close();
  } else {
    await stitchGif();
  }

  console.log("[demo] done");
} finally {
  await browser.close();
  rmSync(frameDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 });
}
