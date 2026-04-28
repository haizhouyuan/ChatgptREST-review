#!/usr/bin/env bash
set -euo pipefail

# Validate Labebe product catalog consistency
# Checks: canonical coverage, duplicate slugs, images, collection references, assignment.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRODUCTS_TS="$PROJECT_DIR/src/data/products.ts"
COLLECTIONS_TS="$PROJECT_DIR/src/data/collections.ts"
IMG_DIR="$PROJECT_DIR/public/assets/products"
CANONICAL_JSON="$PROJECT_DIR/scripts/product_master_canonical.json"

ERRORS=0

echo "=== Labebe Product Catalog Validator ==="
echo ""

# 1. Check products.ts covers canonical product master exactly
echo "[1/7] Checking canonical product coverage..."
PRODUCT_SLUGS=$(grep "slug:" "$PRODUCTS_TS" | grep -v "slug: string" | sed "s/.*slug: '//;s/',.*//" | sort)
CANONICAL_SLUGS=$(node -e "const fs=require('fs'); const data=JSON.parse(fs.readFileSync('$CANONICAL_JSON','utf8')); console.log(data.map(p=>p.slug).sort().join('\\n'))")
CANONICAL_MISSING=$(comm -23 <(echo "$CANONICAL_SLUGS") <(echo "$PRODUCT_SLUGS"))
CANONICAL_EXTRA=$(comm -13 <(echo "$CANONICAL_SLUGS") <(echo "$PRODUCT_SLUGS"))
if [ -n "$CANONICAL_MISSING" ] || [ -n "$CANONICAL_EXTRA" ]; then
    if [ -n "$CANONICAL_MISSING" ]; then
        echo "  FAIL: Canonical products missing from products.ts:"
        echo "$CANONICAL_MISSING" | sed 's/^/    /'
    fi
    if [ -n "$CANONICAL_EXTRA" ]; then
        echo "  FAIL: products.ts contains products absent from canonical master:"
        echo "$CANONICAL_EXTRA" | sed 's/^/    /'
    fi
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: products.ts matches canonical product master"
fi

# 2. Check duplicate slugs
echo "[2/7] Checking duplicate slugs..."
DUPES=$(grep "slug:" "$PRODUCTS_TS" | grep -v "slug: string" | sed "s/.*slug: '//;s/',.*//" | sort | uniq -d)
if [ -n "$DUPES" ]; then
    echo "  FAIL: Duplicate slugs found:"
    echo "$DUPES" | sed 's/^/    /'
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: No duplicate slugs"
fi

# 3. Check missing images
echo "[3/7] Checking product images..."
SLUGS="$PRODUCT_SLUGS"
IMG_MISSING=0
for slug in $SLUGS; do
    if [ ! -f "$IMG_DIR/${slug}.jpg" ]; then
        echo "  FAIL: Missing image for $slug"
        IMG_MISSING=$((IMG_MISSING + 1))
    fi
done
if [ "$IMG_MISSING" -eq 0 ]; then
    echo "  OK: All product images present"
else
    ERRORS=$((ERRORS + IMG_MISSING))
fi

# 4. Check orphan images
echo "[4/7] Checking orphan product images..."
ORPHAN_IMAGES=0
for img in "$IMG_DIR"/*.jpg; do
    [ -e "$img" ] || continue
    slug="$(basename "$img" .jpg)"
    if ! echo "$PRODUCT_SLUGS" | grep -qx "$slug"; then
        echo "  FAIL: Orphan product image without product: $slug"
        ORPHAN_IMAGES=$((ORPHAN_IMAGES + 1))
    fi
done
if [ "$ORPHAN_IMAGES" -eq 0 ]; then
    echo "  OK: No orphan product images"
else
    ERRORS=$((ERRORS + ORPHAN_IMAGES))
fi

# 5. Check products referenced in collections actually exist in products.ts
echo "[5/7] Checking collection slug references..."
COLLECTION_SLUGS=$(grep "'" "$COLLECTIONS_TS" | grep -v "id:\|name:\|subtitle:\|description:\|image:\|href:\|bestFor:" | grep -oP "'[a-z][a-z0-9-]+'" | tr -d "'" | sort -u)
COL_BAD=0
for cs in $COLLECTION_SLUGS; do
    if ! echo "$PRODUCT_SLUGS" | grep -qx "$cs"; then
        echo "  FAIL: Collection references non-existent product: $cs"
        COL_BAD=$((COL_BAD + 1))
    fi
done
if [ "$COL_BAD" -eq 0 ]; then
    echo "  OK: All collection references valid"
else
    ERRORS=$((ERRORS + COL_BAD))
fi

# 6. Check products NOT in any collection
echo "[6/7] Checking unassigned products..."
UNASSIGNED=0
for ps in $PRODUCT_SLUGS; do
    if ! echo "$COLLECTION_SLUGS" | grep -qx "$ps"; then
        echo "  WARN: Product not in any collection: $ps"
        UNASSIGNED=$((UNASSIGNED + 1))
    fi
done
if [ "$UNASSIGNED" -eq 0 ]; then
    echo "  OK: All products assigned to collections"
else
    echo "  WARN: $UNASSIGNED products not in any collection"
fi

# 7. Count totals
echo "[7/7] Summary..."
TOTAL=$(echo "$PRODUCT_SLUGS" | wc -l)
CANONICAL_TOTAL=$(echo "$CANONICAL_SLUGS" | wc -l)
echo "  Total products: $TOTAL"
echo "  Canonical products: $CANONICAL_TOTAL"
echo "  Total collections: $(grep "id:" "$COLLECTIONS_TS" | wc -l)"

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo "FAILED: $ERRORS errors found"
    exit 1
else
    echo "PASSED: All critical checks passed"
    exit 0
fi
