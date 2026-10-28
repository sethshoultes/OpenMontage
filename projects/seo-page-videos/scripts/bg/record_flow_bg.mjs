// Record the sethshoultes.com data-flow scene and scroll orb (#149, PR #150) as video loops for the page videos.
// Usage: node record_flow_bg.mjs <site-checkout-dir> <out-dir>
// Serves the checkout statically, opens bg/rec.html (the page's own canvases, no copy) in headless Chrome at
// 1920x1080 and records three clips: flow-idle.webm, flow-sweep.webm (cursor-driven), orb-form.webm (scroll to the orb).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_DIR || '/usr/local/lib/node_modules/playwright');

const [root, out] = process.argv.slice(2);
if (!root || !out) { console.error('usage: record_flow_bg.mjs <site-checkout-dir> <out-dir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
const here = path.dirname(fileURLToPath(import.meta.url));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
const srv = http.createServer((req, res) => {
  const u = req.url.split('?')[0];
  const f = u === '/rec.html' ? path.join(here, 'rec.html') : path.join(root, u);
  fs.readFile(f, (e, b) => e ? (res.writeHead(404), res.end()) : (res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }), res.end(b)));
}).listen(0);
const base = `http://127.0.0.1:${srv.address().port}/rec.html`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clip(browser, name, seconds, act) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
  const page = await ctx.newPage();
  await page.goto(base, { waitUntil: 'load' });
  await sleep(2500); // flow.js mounts on idle after load
  const t0 = Date.now();
  await act(page);
  await sleep(Math.max(0, seconds * 1000 - (Date.now() - t0)));
  const vid = page.video();
  await ctx.close();
  fs.renameSync(await vid.path(), path.join(out, `${name}.webm`));
  console.log('recorded', name);
}

const browser = await chromium.launch();
await clip(browser, 'flow-idle', 16, async () => {});
await clip(browser, 'flow-sweep', 16, async (p) => {
  await p.mouse.move(200, 700);
  for (let i = 0; i <= 240; i++) { // a slow sweep left to right and back, 8s
    const t = i / 240, x = 200 + 1520 * (t < 0.5 ? t * 2 : 2 - t * 2);
    await p.mouse.move(x, 620 + 140 * Math.sin(t * 6.28));
    await sleep(33);
  }
  await p.mouse.move(960, 10); // leave: the stream eases back
});
await clip(browser, 'orb-form', 16, async (p) => {
  const total = await p.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  for (let i = 0; i <= 150; i++) { // scroll down to the orb over 5s, then hold while it turns
    await p.evaluate((y) => scrollTo(0, y), total * (i / 150));
    await sleep(33);
  }
});
await browser.close();
srv.close();
