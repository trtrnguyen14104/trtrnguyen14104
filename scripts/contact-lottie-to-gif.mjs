import { copyFile, mkdtemp, readFile, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'animations/contact_me_alien.json');
const output = path.join(root, 'animations/contact_me_alien.gif');
const animation = JSON.parse(await readFile(source, 'utf8'));
// Render at twice the README display width to keep the small illustration crisp.
const width = 192;
const height = Math.round(width * animation.h / animation.w);
const fps = 20;
const duration = (animation.op - animation.ip) / animation.fr;
const frames = Math.ceil(duration * fps);
const temporary = await mkdtemp(path.join(tmpdir(), 'nguyen-contact-lottie-'));
let browser;

try {
  browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });
  await page.setContent('<html><head><style>html,body{margin:0}#animation{width:100vw;height:100vh}</style></head><body><div id="animation"></div></body></html>');
  await page.addScriptTag({ path: path.join(root, 'node_modules/lottie-web/build/player/lottie.min.js') });
  await page.evaluate(async (animationData) => {
    window.animation = window.lottie.loadAnimation({
      container: document.getElementById('animation'),
      renderer: 'svg',
      loop: false,
      autoplay: false,
      animationData,
    });
    await new Promise((resolve, reject) => {
      window.animation.addEventListener('DOMLoaded', resolve);
      window.animation.addEventListener('data_failed', () => reject(new Error('Lottie could not load')));
    });
    await Promise.all([...document.images].map((image) => image.decode()));
  }, animation);

  for (let index = 0; index < frames; index++) {
    await page.evaluate((frame) => window.animation.goToAndStop(frame, true), animation.ip + index * animation.fr / fps);
    await page.screenshot({
      path: path.join(temporary, `frame-${String(index).padStart(4, '0')}.png`),
      omitBackground: true,
    });
    if (index % fps === 0) console.log(`Rendered ${index}/${frames} frames`);
  }
  await browser.close();
  browser = undefined;

  await new Promise((resolve, reject) => {
    const ffmpeg = spawn('ffmpeg', [
      '-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(fps),
      '-i', path.join(temporary, 'frame-%04d.png'),
      '-filter_complex', '[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=full:reserve_transparent=1[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle:alpha_threshold=128',
      '-loop', '0', path.join(temporary, 'animation.gif'),
    ], { stdio: 'inherit' });
    ffmpeg.on('error', reject);
    ffmpeg.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)));
  });
  await copyFile(path.join(temporary, 'animation.gif'), output);
  console.log(`Created ${output}: ${width}x${height}, ${frames / fps}s, ${fps}fps, ${((await stat(output)).size / 1024).toFixed(0)} KiB`);
} finally {
  await browser?.close();
  await rm(temporary, { recursive: true, force: true });
}
