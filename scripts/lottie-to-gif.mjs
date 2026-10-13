import { copyFile, readFile, mkdtemp, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'animations/space-hi-there.json');
const output = path.join(root, 'animations/hi_im_nguyen.gif');
const animation = JSON.parse(await readFile(source, 'utf8'));
const width = 851;
const fps = 25;
const duration = (animation.op - animation.ip) / animation.fr;
const frames = Math.ceil(duration * fps);
const temporary = await mkdtemp(path.join(tmpdir(), 'nguyen-lottie-'));
let browser;

try {
  browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width, height: Math.round(width * animation.h / animation.w) },
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
  const bounds = await page.evaluate(({ frames, fps, frameRate, firstFrame, width, height }) => {
    const renderer = window.animation.renderer;
    // Remove only the composition's outer clipping; keep individual layer masks.
    renderer.layerElement.removeAttribute('clip-path');
    let left = 0;
    let top = 0;
    let right = width;
    let bottom = height;
    // Include every exported frame so moving and rotating objects also fit.
    for (let index = 0; index < frames; index++) {
      window.animation.goToAndStop(firstFrame + index * frameRate / fps, true);
      const box = renderer.layerElement.getBBox();
      left = Math.min(left, box.x);
      top = Math.min(top, box.y);
      right = Math.max(right, box.x + box.width);
      bottom = Math.max(bottom, box.y + box.height);
    }
    const padding = 24;
    const x = Math.floor(left) - padding;
    const y = Math.floor(top) - padding;
    const canvasWidth = Math.ceil(right) + padding - x;
    const canvasHeight = Math.ceil(bottom) + padding - y;
    renderer.svgElement.setAttribute('viewBox', `${x} ${y} ${canvasWidth} ${canvasHeight}`);
    return { x, y, width: canvasWidth, height: canvasHeight };
  }, { frames, fps, frameRate: animation.fr, firstFrame: animation.ip, width: animation.w, height: animation.h });
  const height = Math.round(width * bounds.height / bounds.width);
  await page.setViewportSize({ width, height });
  console.log(`Expanded canvas: ${JSON.stringify(bounds)}, output: ${width}x${height}`);
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
      '-filter_complex', '[0:v]split[a][b];[a]palettegen=max_colors=256:stats_mode=full:reserve_transparent=1[p];[b][p]paletteuse=dither=sierra2_4a:alpha_threshold=128',
      '-loop', '0', path.join(temporary, 'animation.gif'),
    ], { stdio: 'inherit' });
    ffmpeg.on('error', reject);
    ffmpeg.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)));
  });
  // Replace the previous GIF only after encoding finishes successfully.
  await copyFile(path.join(temporary, 'animation.gif'), output);
  console.log(`Created ${output}: ${width}x${height}, ${duration}s, ${fps}fps, ${((await stat(output)).size / 1024 / 1024).toFixed(2)} MiB`);
} finally {
  await browser?.close();
  await rm(temporary, { recursive: true, force: true });
}
