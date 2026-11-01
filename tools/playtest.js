// Serve a WebGL build and drive it with a scripted scenario in headless Chromium.
//
// Usage: node tools/playtest.js <buildDir> [outDir] [scenario]
//   scenario: comma-separated steps (default: a short drive)
//     wait:<ms>          wait
//     down:<key> / up:<key>   hold / release a key (Playwright key names: KeyW, Space, Escape, F1 ...)
//     press:<key>        tap a key
//     shot:<name>        screenshot to <outDir>/<name>.png
//     mouse:<dx>:<dy>    move the mouse by a delta (camera orbit)
//   Example: "wait:15000,shot:start,down:KeyW,wait:4000,shot:driving,up:KeyW"
// Also writes console.log (browser console) and fps.txt (requestAnimationFrame rate samples).
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const buildDir = path.resolve(process.argv[2] || 'webgl-build');
const outDir = path.resolve(process.argv[3] || 'playtest-output');
const scenario = (process.argv[4] ||
  'wait:20000,shot:01-start,press:F1,down:KeyW,wait:3000,shot:02-accelerating,down:KeyA,wait:1500,shot:03-turning,' +
  'up:KeyA,wait:2500,shot:04-cruising,up:KeyW,down:KeyS,wait:2000,up:KeyS,mouse:400:0,wait:300,shot:05-orbit,' +
  'wait:2500,press:Escape,wait:500,shot:06-menu').split(',');

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
  const browser = await chromium.launch({
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const logs = [];
  page.on('console', m => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
  await page.goto('http://localhost:8123/');
  // Measure the page's frame rate (software rendering here, so only useful as a relative number).
  await page.evaluate(() => {
    window.__fps = [];
    let last = performance.now(), frames = 0;
    const tick = (t) => { frames++; if (t - last > 1000) { window.__fps.push(frames * 1000 / (t - last)); frames = 0; last = t; } requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  // Focus the canvas so keyboard input reaches Unity.
  await page.waitForTimeout(1000);
  await page.mouse.click(640, 360).catch(() => {});

  for (const step of scenario) {
    const [cmd, a, b] = step.trim().split(':');
    if (cmd === 'wait') await page.waitForTimeout(Number(a));
    else if (cmd === 'down') await page.keyboard.down(a);
    else if (cmd === 'up') await page.keyboard.up(a);
    else if (cmd === 'press') await page.keyboard.press(a);
    else if (cmd === 'shot') await page.screenshot({ path: path.join(outDir, `${a}.png`) });
    else if (cmd === 'mouse') { await page.mouse.move(640, 360); await page.mouse.move(640 + Number(a), 360 + Number(b), { steps: 10 }); }
    else console.warn('Unknown step', step);
  }
  const fps = await page.evaluate(() => window.__fps);
  fs.writeFileSync(path.join(outDir, 'fps.txt'), fps.map(f => f.toFixed(1)).join('\n'));
  fs.writeFileSync(path.join(outDir, 'console.log'), logs.join('\n'));
  console.log(`Saved to ${outDir}. Median page FPS (software GL): ${fps.sort((x, y) => x - y)[Math.floor(fps.length / 2)]?.toFixed(1)}`);
  await browser.close(); server.close();
})().catch(e => { console.error(e); server.close(); process.exit(1); });
