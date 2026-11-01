// Serve a WebGL build and capture screenshots with headless Chromium.
// Usage: node tools/playtest.js <buildDir> [outDir] [seconds]
// Optional keys: KEYS="ArrowUp:1000,Space:100" (key:holdMs, comma-separated)
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const buildDir = path.resolve(process.argv[2] || 'webgl-build');
const outDir = path.resolve(process.argv[3] || 'playtest-output');
const seconds = Number(process.argv[4] || 20);
const types = { '.html': 'text/html', '.js': 'application/javascript', '.wasm': 'application/wasm',
  '.data': 'application/octet-stream', '.css': 'text/css', '.png': 'image/png', '.ico': 'image/x-icon' };

const server = http.createServer((req, res) => {
  let p = path.join(buildDir, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(buildDir)) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, 'index.html');
  if (!fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  await new Promise(r => server.listen(8123, r));
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const logs = [];
  page.on('console', m => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
  await page.goto('http://localhost:8123/');

  const shots = 4;
  for (let i = 1; i <= shots; i++) {
    await page.waitForTimeout((seconds * 1000) / shots);
    await page.screenshot({ path: path.join(outDir, `shot-${i}.png`) });
  }
  if (process.env.KEYS) {
    await page.click('canvas').catch(() => {});
    for (const step of process.env.KEYS.split(',')) {
      const [key, ms] = step.split(':');
      await page.keyboard.down(key); await page.waitForTimeout(Number(ms || 100)); await page.keyboard.up(key);
    }
    await page.screenshot({ path: path.join(outDir, 'after-input.png') });
  }
  fs.writeFileSync(path.join(outDir, 'console.log'), logs.join('\n'));
  console.log(`Saved screenshots and console.log to ${outDir}`);
  await browser.close(); server.close();
})().catch(e => { console.error(e); server.close(); process.exit(1); });
