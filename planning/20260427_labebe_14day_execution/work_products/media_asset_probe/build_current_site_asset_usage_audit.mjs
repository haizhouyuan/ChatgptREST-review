import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('../../../..', import.meta.url).pathname);
const SITE = path.join(ROOT, 'labebe-gemini-demo');
const OUT = path.join(ROOT, 'planning/20260427_labebe_14day_execution/work_products/media_asset_probe');
const productsTs = fs.readFileSync(path.join(SITE, 'src/data/products.ts'), 'utf8');

const csvEscape = (value) => {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

const fileHash = (filePath) => crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');

const productRows = [];
const productRegex = /\{\s*slug: '([^']+)'[\s\S]*?image: img\('([^']+)'\)[\s\S]*?source: '([^']*)'[\s\S]*?dataStatus: '([^']*)'[\s\S]*?\n  \}/g;
let match;
while ((match = productRegex.exec(productsTs))) {
  const block = match[0];
  productRows.push({
    slug: match[1],
    title: block.match(/title: '([^']+)'/)?.[1] ?? '',
    collection: block.match(/collection: '([^']+)'/)?.[1] ?? '',
    world: block.match(/world: '([^']+)'/)?.[1] ?? '',
    price: block.match(/price: ([0-9.]+)/)?.[1] ?? '',
    reviewCount: (block.match(/reviewCount: ([^,\n]+)/)?.[1] ?? '').trim(),
    imageBase: match[2],
    imageFile: `${match[2]}.jpg`,
    source: match[3],
    dataStatus: match[4],
  });
}

const productByImage = new Map(productRows.map((row) => [row.imageFile, row]));
const publicProductDir = path.join(SITE, 'public/assets/products');
const distProductDir = path.join(SITE, 'dist/assets/products');
const sourceCatalogDir = path.join(ROOT, 'data/labebe/images');
const liveProbeImageDir = path.join(ROOT, 'data/labebe/live_probe_images_20260428');
const liveProbeCsv = path.join(
  ROOT,
  'planning/20260427_labebe_14day_execution/work_products/product_market_master/live_crawl_20260428/labebe_products_live_probe.csv',
);

const parseCsvLine = (line) => {
  const cells = [];
  let current = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"' && quoted && line[i + 1] === '"') {
      current += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ',' && !quoted) {
      cells.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
};

const liveProbeRows = [];
if (fs.existsSync(liveProbeCsv)) {
  const [headerLine, ...lines] = fs.readFileSync(liveProbeCsv, 'utf8').replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean);
  const headers = parseCsvLine(headerLine);
  for (const line of lines) {
    const values = parseCsvLine(line);
    liveProbeRows.push(Object.fromEntries(headers.map((header, idx) => [header, values[idx] ?? ''])));
  }
}
const liveProbeBySlug = new Map();
for (const row of liveProbeRows) {
  if (!liveProbeBySlug.has(row.slug)) liveProbeBySlug.set(row.slug, row);
}

const publicFiles = fs.readdirSync(publicProductDir).filter((file) => /\.(jpg|jpeg|png|webp)$/i.test(file)).sort();

const auditRows = publicFiles.map((file, idx) => {
  const publicPath = path.join(publicProductDir, file);
  const distPath = path.join(distProductDir, file);
  const sourcePath = path.join(sourceCatalogDir, file);
  const liveDownloadPath = path.join(liveProbeImageDir, file);
  const product = productByImage.get(file);
  const hasSourceCatalog = fs.existsSync(sourcePath);
  const hasLiveDownload = fs.existsSync(liveDownloadPath);
  const sourceHash = hasSourceCatalog ? fileHash(sourcePath) : '';
  const liveDownloadHash = hasLiveDownload ? fileHash(liveDownloadPath) : '';
  const publicHash = fileHash(publicPath);
  const distHash = fs.existsSync(distPath) ? fileHash(distPath) : '';
  const sourceMatch = hasSourceCatalog && sourceHash === publicHash;
  const liveDownloadMatch = hasLiveDownload && liveDownloadHash === publicHash;
  const liveProbe = liveProbeBySlug.get(product?.slug ?? '');
  const hasLiveProbeUrl = Boolean(liveProbe?.image_url_probe);
  const distMatch = distHash && distHash === publicHash;
  const sourceClass = sourceMatch
    ? 'official_catalog_exact_copy'
    : liveDownloadMatch
      ? 'official_catalog_live_probe_exact_copy'
      : hasLiveProbeUrl
        ? 'official_catalog_live_probe_url'
        : hasSourceCatalog
          ? 'official_catalog_filename_hash_mismatch'
          : 'unknown_local_asset';
  const dtcPosture = sourceMatch || liveDownloadMatch || hasLiveProbeUrl
    ? 'conditional_for_dtc_after_brand_rights_confirmed'
    : 'blocked_until_origin_verified';
  const useStatus = product ? 'referenced_by_current_consumer_site' : 'available_not_referenced_by_current_site';

  return {
    asset_id: `SITE-ASSET-${String(idx + 1).padStart(3, '0')}`,
    filename: file,
    site_public_path: path.relative(ROOT, publicPath),
    site_dist_path: fs.existsSync(distPath) ? path.relative(ROOT, distPath) : '',
    referenced_product_slug: product?.slug ?? '',
    referenced_product_title: product?.title ?? '',
    collection: product?.collection ?? '',
    world: product?.world ?? '',
    source_class: sourceClass,
    source_catalog_path: hasSourceCatalog ? path.relative(ROOT, sourcePath) : '',
    source_live_probe_url: liveProbe?.image_url_probe ?? '',
    source_live_download_path: hasLiveDownload ? path.relative(ROOT, liveDownloadPath) : '',
    public_sha256_prefix: publicHash.slice(0, 16),
    source_sha256_prefix: sourceHash.slice(0, 16),
    live_download_sha256_prefix: liveDownloadHash.slice(0, 16),
    dist_copy_matches_public: distMatch ? 'yes' : 'no',
    current_site_usage: useStatus,
    dtc_usage_posture: dtcPosture,
    risk_note: sourceMatch || liveDownloadMatch || hasLiveProbeUrl
      ? 'Prototype uses Labebe catalog imagery or a live-probe catalog image reference; production still needs brand/legal confirmation.'
      : 'Do not use in production until the asset origin and rights are verified.',
  };
});

const siteVideoFiles = [];
for (const dir of ['public', 'dist']) {
  const base = path.join(SITE, dir);
  const stack = [base];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (/\.(mp4|webm|mov)$/i.test(entry.name)) siteVideoFiles.push(path.relative(ROOT, full));
    }
  }
}

const csvHeader = Object.keys(auditRows[0] ?? {
  asset_id: '',
  filename: '',
  site_public_path: '',
  site_dist_path: '',
  referenced_product_slug: '',
  referenced_product_title: '',
  collection: '',
  world: '',
  source_class: '',
  source_catalog_path: '',
  source_live_probe_url: '',
  source_live_download_path: '',
  public_sha256_prefix: '',
  source_sha256_prefix: '',
  live_download_sha256_prefix: '',
  dist_copy_matches_public: '',
  current_site_usage: '',
  dtc_usage_posture: '',
  risk_note: '',
});
const csv = [
  csvHeader.join(','),
  ...auditRows.map((row) => csvHeader.map((key) => csvEscape(row[key])).join(',')),
].join('\n') + '\n';
fs.writeFileSync(path.join(OUT, 'current_site_asset_usage_audit_v2.csv'), csv);

const referenced = auditRows.filter((row) => row.current_site_usage === 'referenced_by_current_consumer_site').length;
const exactCopies = auditRows.filter((row) => row.source_class === 'official_catalog_exact_copy').length;
const liveProbeExactCopies = auditRows.filter((row) => row.source_class === 'official_catalog_live_probe_exact_copy').length;
const liveProbeBacked = auditRows.filter((row) => row.source_class === 'official_catalog_live_probe_url').length;
const unreferenced = auditRows.length - referenced;
const blocked = auditRows.filter((row) => row.dtc_usage_posture === 'blocked_until_origin_verified').length;

const md = `# Current Consumer Site Asset Usage Audit v2

**Date:** 2026-04-28  
**Scope:** \`labebe-gemini-demo/public\`, \`labebe-gemini-demo/dist\`, and current product data references.  
**Purpose:** Keep the Labebe consumer website separate from Paperclip / AI demo assets and make asset rights posture explicit.

## Summary

| Metric | Count |
| --- | ---: |
| Product image files in current consumer public bundle | ${auditRows.length} |
| Product images referenced by current site product data | ${referenced} |
| Extra product images available but not currently referenced | ${unreferenced} |
| Exact local copies of \`data/labebe/images\` catalog files | ${exactCopies} |
| Exact local copies of \`data/labebe/live_probe_images_20260428\` files | ${liveProbeExactCopies} |
| Backed by live catalog probe URL but not exact local hash copy | ${liveProbeBacked} |
| Assets blocked until origin verification | ${blocked} |
| Video files inside current consumer public/dist bundle | ${siteVideoFiles.length} |

## Findings

1. The current consumer site no longer exposes Paperclip, Boss Gallery, AI Growth Studio, or Pro context routes/assets.
2. The consumer bundle contains product images only; no MP4/WebM/MOV files are shipped with the Labebe DTC site.
3. The active design uses catalog product photography as the visual source of truth. Seventeen files are exact copies from the older canonical image folder; nine files are exact copies from the 2026-04-28 live-probe image folder.
4. Extra product images remain in the public bundle because they are real catalog candidates for collection expansion. They are not currently displayed unless the product data references them.

## Usage Policy

| Asset class | Current DTC stance | Notes |
| --- | --- | --- |
| Exact catalog product image copies | Conditional | Acceptable for prototype and internal review; production needs brand permission / terms confirmation. |
| Live-probe catalog exact copies | Conditional | Acceptable for prototype; promote into the canonical data folder after review. |
| Live-probe catalog URL images | Conditional | URL-backed only; re-download into the canonical data folder before production handoff. |
| Unknown local images | Blocked | Do not use until origin and rights are verified. |
| MiniMax / AI-generated video | Blocked from consumer site | Internal presentation only unless synthetic labeling and brand/legal approval are added. |
| Paperclip / Boss Gallery videos | Blocked from consumer site | Presentation artifacts, not shopper-facing media. |
| QA screenshots and contact sheets | Internal only | Evidence artifacts, not consumer assets. |

## Current Consumer-Site Guardrail

The site must stay a pure Labebe replacement commerce experience:

- No Paperclip route.
- No AI Growth route.
- No Boss Demo route.
- No Pro context folder in \`public\` or \`dist\`.
- No synthetic or unknown-origin lifestyle image on consumer pages unless explicitly reviewed.
- No video in consumer bundle until footage provenance and rights are clear.

## Files

- CSV audit: \`current_site_asset_usage_audit_v2.csv\`
- Build source checked: \`labebe-gemini-demo/src/data/products.ts\`
- Product image source directory: \`data/labebe/images\`
`;
fs.writeFileSync(path.join(OUT, 'current_site_asset_usage_audit_v2.md'), md);

const manifest = {
  generated_at: new Date().toISOString(),
  product_rows: productRows.length,
  product_image_files: auditRows.length,
  referenced_product_images: referenced,
  unreferenced_product_images: unreferenced,
  exact_catalog_copies: exactCopies,
  live_probe_catalog_exact_copies: liveProbeExactCopies,
  live_probe_catalog_url_backed: liveProbeBacked,
  blocked_until_origin_verified: blocked,
  consumer_bundle_video_files: siteVideoFiles,
  outputs: [
    'current_site_asset_usage_audit_v2.csv',
    'current_site_asset_usage_audit_v2.md',
  ],
};
fs.writeFileSync(path.join(OUT, 'current_site_asset_usage_audit_v2_manifest.json'), JSON.stringify(manifest, null, 2) + '\n');

console.log(JSON.stringify(manifest, null, 2));
