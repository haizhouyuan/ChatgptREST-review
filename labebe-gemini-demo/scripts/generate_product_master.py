#!/usr/bin/env python3
"""
Regenerate products.ts from canonical product master JSON.
Merges probe facts with existing curated merchandising fields.
"""
import json, os, re, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANONICAL = os.path.join(SCRIPT_DIR, 'product_master_canonical.json')
PRODUCTS_TS = os.path.join(SCRIPT_DIR, '..', 'src', 'data', 'products.ts')

# Broken slugs to remove (404 on live site)
BROKEN_SLUGS = {'lion-plush-rocker', 'zebra-baby-push-walker', 'hedgehog-baby-push-walker', 'childrens-bed-with-safety-barrier'}

# Slug remapping (local broken -> correct canonical)
SLUG_REMAP = {
    'childrens-bed-with-safety-barrier': 'children-s-bed-with-safety-barrier-and-slatted-base',
}

# Collection mapping from probe collection_probe field
COLLECTION_MAP = {
    'rockers-ride-ons': 'rockers-ride-ons',
    'furniture': 'furniture',
    'pretend-play': 'pretend-play',
    'activity-educational-toys': 'art-creativity',
    'new-in': 'walkers',
    'all': None,  # needs manual assignment
}

# World assignment based on collection
WORLD_MAP = {
    'rockers-ride-ons': 'Giftable Rockers',
    'furniture': 'Montessori at Home',
    'pretend-play': 'Tiny Pretend Worlds',
    'walkers': 'First Steps & Walkers',
    'art-creativity': 'Art & Creativity',
}

# Default curated fields for NEW products not in existing data
def default_curated(slug, title, collection):
    world = WORLD_MAP.get(collection, 'Uncategorized')
    age = '1-3Y' if 'walker' in slug or 'rocker' in slug else '3-6Y' if 'kitchen' in slug or 'playset' in slug else '2-8Y'
    room = ['Playroom']
    if 'rocker' in slug: room = ['Nursery', 'Playroom']
    elif 'kitchen' in slug or 'tower' in slug: room = ['Kitchen']
    elif 'desk' in slug or 'bed' in slug: room = ['Bedroom']
    elif 'outdoor' in slug or 'mud' in slug: room = ['Outdoor']
    
    return {
        'world': world,
        'ageRange': age,
        'roomTags': room,
        'playTags': [],
        'giftTags': [],
        'shortBenefit': f'{title} for creative play and learning.',
        'story': 'Newly added from canonical product master.',
        'badges': ['New'],
        'allowedClaims': ['price'],
        'bundleSlugs': [],
    }

def main():
    with open(CANONICAL) as f:
        canonical = {p['slug']: p for p in json.load(f)}
    
    # Read existing products.ts to extract curated fields
    with open(PRODUCTS_TS) as f:
        content = f.read()
    
    # Parse existing product blocks
    existing = {}
    pattern = r"\{\s*slug:\s*'([^']+)'.*?\},"
    for match in re.finditer(pattern, content, re.DOTALL):
        slug = match.group(1)
        block = match.group(0)
        existing[slug] = block
    
    # Also extract curated fields from existing blocks
    def extract_field(block, field):
        m = re.search(rf"{field}:\s*(.+?)(?:,\s*$|\n)", block, re.MULTILINE)
        return m.group(1).strip().rstrip(',') if m else None
    
    def extract_array(block, field):
        m = re.search(rf"{field}:\s*\[([^\]]*)\]", block)
        if not m: return []
        items = re.findall(r"'([^']*)'", m.group(1))
        return items
    
    existing_curated = {}
    for slug, block in existing.items():
        if slug in BROKEN_SLUGS:
            # Check if remappable
            new_slug = SLUG_REMAP.get(slug)
            if new_slug:
                existing_curated[new_slug] = {
                    'world': extract_field(block, 'world'),
                    'ageRange': extract_field(block, 'ageRange'),
                    'roomTags': extract_array(block, 'roomTags'),
                    'playTags': extract_array(block, 'playTags'),
                    'giftTags': extract_array(block, 'giftTags'),
                    'shortBenefit': extract_field(block, 'shortBenefit'),
                    'story': extract_field(block, 'story'),
                    'badges': extract_array(block, 'badges'),
                    'allowedClaims': extract_array(block, 'allowedClaims'),
                    'bundleSlugs': extract_array(block, 'bundleSlugs'),
                }
            continue
        existing_curated[slug] = {
            'world': extract_field(block, 'world'),
            'ageRange': extract_field(block, 'ageRange'),
            'roomTags': extract_array(block, 'roomTags'),
            'playTags': extract_array(block, 'playTags'),
            'giftTags': extract_array(block, 'giftTags'),
            'shortBenefit': extract_field(block, 'shortBenefit'),
            'story': extract_field(block, 'story'),
            'badges': extract_array(block, 'badges'),
            'allowedClaims': extract_array(block, 'allowedClaims'),
            'bundleSlugs': extract_array(block, 'bundleSlugs'),
        }
    
    # Build final product list
    products = []
    for slug, probe in sorted(canonical.items()):
        # Skip the problematic CSV parse issue row
        if 'kids-wooden-desk---chair-set' in slug:
            continue  # duplicate of children-s-writing-desk, CSV parse artifact
            
        curated = existing_curated.get(slug) or default_curated(slug, probe['title'], guess_collection(slug, probe))
        collection = guess_collection(slug, probe)
        
        # Clean world field (remove quotes if extracted from source)
        world = curated.get('world', '') or WORLD_MAP.get(collection, 'Uncategorized')
        if world.startswith("'"): world = world.strip("'")
        
        # Clean shortBenefit
        benefit = curated.get('shortBenefit', '') or f"{probe['title']} for play and learning."
        if benefit.startswith("'"): benefit = benefit.strip("'")
        
        story = curated.get('story', '') or 'Added from canonical product master.'
        if story.startswith("'"): story = story.strip("'")
        
        age = curated.get('ageRange', '2-6Y') or '2-6Y'
        if age.startswith("'"): age = age.strip("'")
        
        data_status = 'scraped' if slug in existing_curated else 'to-confirm'
        
        products.append({
            'slug': slug,
            'title': probe['title'],
            'collection': collection,
            'world': world,
            'price': probe['price'],
            'compareAtPrice': probe['compareAtPrice'],
            'reviewCount': probe['reviewCount'],
            'ageRange': age,
            'roomTags': curated.get('roomTags', ['Playroom']),
            'playTags': curated.get('playTags', []),
            'giftTags': curated.get('giftTags', []),
            'image': slug,
            'productUrl': probe['productUrl'],
            'shortBenefit': benefit,
            'story': story,
            'badges': curated.get('badges', ['New']),
            'source': 'canonical probe 2026-04-27',
            'dataStatus': data_status,
            'unknownFields': ['verified rating', 'dimensions', 'materials detail'],
            'allowedClaims': curated.get('allowedClaims', ['price']),
            'bundleSlugs': curated.get('bundleSlugs', []),
        })
    
    # Generate TS
    generate_ts(products)
    print(f"Generated {len(products)} products in products.ts")

def guess_collection(slug, probe):
    cp = probe.get('collection_probe', '')
    if cp in ('rockers-ride-ons',): return 'rockers-ride-ons'
    if cp in ('furniture',): return 'furniture'
    if cp in ('pretend-play',): return 'pretend-play'
    if cp in ('activity-educational-toys',): return 'art-creativity'
    # Heuristic for 'all' or 'new-in'
    if 'rocker' in slug or 'rocking' in slug: return 'rockers-ride-ons'
    if 'walker' in slug: return 'walkers'
    if 'tower' in slug: return 'furniture'
    if 'easel' in slug or 'busy-board' in slug: return 'art-creativity'
    if 'kitchen' in slug or 'playset' in slug or 'washer' in slug: return 'pretend-play'
    if 'shelf' in slug or 'storage' in slug or 'cabinet' in slug or 'desk' in slug or 'bookshelf' in slug or 'stool' in slug: return 'furniture'
    if 'spinner' in slug or 'spin' in slug: return 'rockers-ride-ons'
    if 'bench' in slug and 'outdoor' in slug: return 'pretend-play'
    if 'sensory' in slug or 'table' in slug: return 'furniture'
    if 'bed' in slug: return 'furniture'
    return 'uncategorized'

def fmt_price(p):
    if p is None: return 'undefined'
    return str(p)

def fmt_review(r):
    if r is None: return 'null'
    return str(r)

def fmt_str_array(arr):
    if not arr: return '[]'
    items = ', '.join(f"'{a}'" for a in arr)
    return f'[{items}]'

def escape_ts(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")

def generate_ts(products):
    lines = []
    lines.append("export type ProductStatus = 'scraped' | 'curated' | 'to-confirm';")
    lines.append("")
    lines.append("export type Product = {")
    lines.append("  slug: string;")
    lines.append("  title: string;")
    lines.append("  collection: string;")
    lines.append("  world: string;")
    lines.append("  price: number;")
    lines.append("  compareAtPrice?: number;")
    lines.append("  reviewCount: number | null;")
    lines.append("  ageRange: string;")
    lines.append("  roomTags: string[];")
    lines.append("  playTags: string[];")
    lines.append("  giftTags: string[];")
    lines.append("  image: string;")
    lines.append("  productUrl: string;")
    lines.append("  shortBenefit: string;")
    lines.append("  story: string;")
    lines.append("  badges: string[];")
    lines.append("  source: string;")
    lines.append("  dataStatus: ProductStatus;")
    lines.append("  unknownFields: string[];")
    lines.append("  allowedClaims: string[];")
    lines.append("  bundleSlugs: string[];")
    lines.append("};")
    lines.append("")
    lines.append("const img = (name: string) => `/assets/products/${name}.jpg`;")
    lines.append("")
    lines.append("export const productList: Product[] = [")
    
    for p in products:
        lines.append("  {")
        lines.append(f"    slug: '{p['slug']}',")
        lines.append(f"    title: '{escape_ts(p['title'])}',")
        lines.append(f"    collection: '{p['collection']}',")
        lines.append(f"    world: '{escape_ts(p['world'])}',")
        lines.append(f"    price: {fmt_price(p['price'])},")
        if p['compareAtPrice'] is not None:
            lines.append(f"    compareAtPrice: {fmt_price(p['compareAtPrice'])},")
        lines.append(f"    reviewCount: {fmt_review(p['reviewCount'])},")
        lines.append(f"    ageRange: '{p['ageRange']}',")
        lines.append(f"    roomTags: {fmt_str_array(p['roomTags'])},")
        lines.append(f"    playTags: {fmt_str_array(p['playTags'])},")
        lines.append(f"    giftTags: {fmt_str_array(p['giftTags'])},")
        lines.append(f"    image: img('{p['image']}'),")
        lines.append(f"    productUrl: '{p['productUrl']}',")
        lines.append(f"    shortBenefit: '{escape_ts(p['shortBenefit'])}',")
        lines.append(f"    story: '{escape_ts(p['story'])}',")
        lines.append(f"    badges: {fmt_str_array(p['badges'])},")
        lines.append(f"    source: '{p['source']}',")
        lines.append(f"    dataStatus: '{p['dataStatus']}',")
        lines.append(f"    unknownFields: {fmt_str_array(p['unknownFields'])},")
        lines.append(f"    allowedClaims: {fmt_str_array(p['allowedClaims'])},")
        lines.append(f"    bundleSlugs: {fmt_str_array(p['bundleSlugs'])},")
        lines.append("  },")
    
    lines.append("];")
    lines.append("")
    lines.append("export const products: Record<string, Product> = Object.fromEntries(")
    lines.append("  productList.map((product) => [product.slug, product]),")
    lines.append(");")
    lines.append("")
    lines.append("export const getProduct = (slug?: string) => (slug ? products[slug] : undefined);")
    lines.append("")
    lines.append("export const getBestSellers = () =>")
    lines.append("  productList")
    lines.append("    .filter((product) => product.reviewCount !== null)")
    lines.append("    .sort((a, b) => (b.reviewCount ?? 0) - (a.reviewCount ?? 0))")
    lines.append("    .slice(0, 8);")
    lines.append("")
    lines.append("export const getByWorld = (world: string) => productList.filter((product) => product.world === world);")
    lines.append("")
    lines.append("export const getBundleProducts = (product: Product) =>")
    lines.append("  product.bundleSlugs.map((slug) => products[slug]).filter(Boolean);")
    lines.append("")
    lines.append("export const formatPrice = (price: number) => `$${price.toFixed(2)}`;")
    lines.append("")
    lines.append("export const giftFinderRecommendations = (age: string, room: string, occasion: string) => {")
    lines.append("  const scored = productList.map((product) => {")
    lines.append("    let score = 0;")
    lines.append("    if (age && product.ageRange.toLowerCase().includes(age.toLowerCase())) score += 3;")
    lines.append("    if (room && product.roomTags.some((tag) => tag.toLowerCase() === room.toLowerCase())) score += 3;")
    lines.append("    if (occasion && product.giftTags.some((tag) => tag.toLowerCase().includes(occasion.toLowerCase()))) score += 2;")
    lines.append("    if (product.reviewCount) score += Math.min(product.reviewCount / 6, 2);")
    lines.append("    return { product, score };")
    lines.append("  });")
    lines.append("")
    lines.append("  return scored")
    lines.append("    .sort((a, b) => b.score - a.score)")
    lines.append("    .slice(0, 3)")
    lines.append("    .map(({ product }) => product);")
    lines.append("};")
    lines.append("")
    
    PRODUCTS_TS = os.path.join(SCRIPT_DIR, '..', 'src', 'data', 'products.ts')
    with open(PRODUCTS_TS, 'w') as f:
        f.write('\n'.join(lines))

if __name__ == '__main__':
    main()
