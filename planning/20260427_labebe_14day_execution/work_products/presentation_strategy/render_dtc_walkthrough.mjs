#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const root = resolve('/vol1/1000/projects/toyresearch');
const output = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4');
const poster = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_poster.jpg');
const contact = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_contact_sheet.jpg');
const mobileOutput = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_mobile.mp4');
const mobilePoster = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_mobile_poster.jpg');
const mobileContact = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_mobile_contact_sheet.jpg');
const tmpList = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/frames.txt');
const mobileTmpList = resolve(root, 'paperclip_runtime_duel/outputs/labebe_site_walkthrough/mobile_frames.txt');

const frames = [
  ['qa/labebe-commerce-v2/home-design-gift-desktop-v5.png', 8],
  ['qa/labebe-commerce-v2/home-design-room-desktop-v3.png', 8],
  ['qa/labebe-commerce-v2/home-design-play-desktop-v3.png', 8],
  ['qa/labebe-commerce-v2/shop-by-age-desktop-v1.png', 7],
  ['qa/labebe-commerce-v2/giftable-rockers-collection-desktop-v1.png', 7],
  ['qa/labebe-commerce-v2/pink-unicorn-pdp-desktop-v1.png', 8],
  ['qa/labebe-commerce-v2/home-design-gift-mobile-v5.png', 7],
  ['qa/labebe-commerce-v2/pink-unicorn-pdp-mobile-v1.png', 7],
];

const mobileFrames = [
  ['qa/labebe-commerce-v2/home-design-gift-mobile-v5.png', 8],
  ['qa/labebe-commerce-v2/home-design-play-mobile-v3.png', 8],
  ['qa/labebe-commerce-v2/giftable-rockers-collection-mobile-v1.png', 8],
  ['qa/labebe-commerce-v2/pink-unicorn-pdp-mobile-v1.png', 8],
];

mkdirSync(dirname(output), { recursive: true });

function writeList(path, frameList) {
  writeFileSync(
    path,
    frameList.map(([framePath, duration]) => `file '${resolve(root, framePath)}'\nduration ${duration}`).join('\n') +
      `\nfile '${resolve(root, frameList.at(-1)[0])}'\n`,
  );
}

function renderVideo({ listPath, frameList, out, posterPath, contactPath, width, height, contactTile }) {
  writeList(listPath, frameList);
  const filter =
    `scale=${width}:${height}:force_original_aspect_ratio=decrease,` +
    `pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=0xfbf5e9,` +
    'format=yuv420p';

  const video = spawnSync('ffmpeg', [
    '-y',
    '-f',
    'concat',
    '-safe',
    '0',
    '-i',
    listPath,
    '-vf',
    filter,
    '-r',
    '30',
    '-c:v',
    'libx264',
    '-pix_fmt',
    'yuv420p',
    out,
  ], { stdio: 'inherit' });

  if (video.status !== 0) process.exit(video.status ?? 1);

  spawnSync('ffmpeg', ['-y', '-i', out, '-frames:v', '1', '-q:v', '2', '-update', '1', posterPath], { stdio: 'inherit' });
  spawnSync('ffmpeg', [
    '-y',
    '-i',
    out,
    '-vf',
    contactTile,
    '-frames:v',
    '1',
    '-q:v',
    '2',
    '-update',
    '1',
    contactPath,
  ], { stdio: 'inherit' });
}

renderVideo({
  listPath: tmpList,
  frameList: frames,
  out: output,
  posterPath: poster,
  contactPath: contact,
  width: 1920,
  height: 1080,
  contactTile: 'fps=1/8,scale=360:-1,tile=8x1:padding=10:margin=10:color=0xfbf5e9',
});

renderVideo({
  listPath: mobileTmpList,
  frameList: mobileFrames,
  out: mobileOutput,
  posterPath: mobilePoster,
  contactPath: mobileContact,
  width: 1080,
  height: 1920,
  contactTile: 'fps=1/8,scale=240:-1,tile=4x1:padding=10:margin=10:color=0xfbf5e9',
});

console.log(JSON.stringify({ output, poster, contact, mobileOutput, mobilePoster, mobileContact }, null, 2));
