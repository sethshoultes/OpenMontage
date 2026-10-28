// Record the site and the dashboard that the running Playground serves (piece 3 clip). Run while `start` is up.
// Usage: node record_browser.mjs <out-dir>   (needs http://127.0.0.1:9400 up)
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_DIR || '/usr/local/lib/node_modules/playwright');
const out = process.argv[2];
fs.mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
// Playground logs the browser in with a cookie and redirects; wait until the site (not its 'not ready yet' stub) answers,
// in a throwaway context, so the recorded take starts on the real site.
{
  const probe = await browser.newContext();
  const pp = await probe.newPage();
  for (let i = 0; i < 90; i++) {
    const ok = await pp.goto('http://127.0.0.1:9400/', { waitUntil: 'load', timeout: 20000 }).then(async () => (await pp.content()).includes('wp-block') || (await pp.content()).includes('wp-site-blocks')).catch(() => false);
    if (ok) break;
    await sleep(1000);
  }
  await probe.close();
}
const page = await ctx.newPage();
// the page is shown at 1.8x so its text stays legible when the 1080p frame is watched at phone width
await page.addInitScript(() => { document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = '1.8'; }); });
await page.goto('http://127.0.0.1:9400/', { waitUntil: 'load' });
await sleep(5000);
await page.goto('http://127.0.0.1:9400/wp-admin/', { waitUntil: 'load' }); // signed in as admin by default
await sleep(6000);
const v = page.video();
await ctx.close();
fs.renameSync(await v.path(), path.join(out, 'browser-take.webm'));
await browser.close();
console.log('browser take recorded');
