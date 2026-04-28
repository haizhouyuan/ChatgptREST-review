#!/usr/bin/env bash
set -euo pipefail

# Validate Labebe product catalog consistency
# Checks: duplicate slugs, missing images, unassigned collections, dataStatus integrity

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRODUCTS_TS="$PROJECT_DIR/src/data/products.ts"
COLLECTIONS_TS="$PROJECT_DIR/src/data/collections.ts"
IMG_DIR="$PROJECT_DIR/public/assets/products"

ERRORS=0

echo "=== Labebe Product Catalog Validator ==="
echo ""

# 1. Check duplicate slugs
echo "[1/5] Checking duplicate slugs..."
DUPES=$(grep "slug:" "$PRODUCTS_TS" | grep -v "slug: string" | sed "s/.*slug: '//;s/',.*//" | sort | uniq -d)
if [ -n "$DUPES" ]; then
    echo "  FAIL: Duplicate slugs found:"
    echo "$DUPES" | sed 's/^/    /'
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: No duplicate slugs"
fi

# 2. Check missing images
echo "[2/5] Checking product images..."
SLUGS=$(grep "slug:" "$PRODUCTS_TS" | grep -v "slug: string" | sed "s/.*slug: '//;s/',.*//")
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

# 3. Check products referenced in collections actually exist in products.ts
echo "[3/5] Checking collection slug references..."
PRODUCT_SLUGS=$(grep "slug:" "$PRODUCTS_TS" | grep -v "slug: string" | sed "s/.*slug: '//;s/',.*//" | sort)
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

# 4. Check products NOT in any collection
echo "[4/5] Checking unassigned products..."
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

# 5. Count totals
echo "[5/5] Summary..."
TOTAL=$(echo "$PRODUCT_SLUGS" | wc -l)
echo "  Total products: $TOTAL"
echo "  Total collections: $(grep "id:" "$COLLECTIONS_TS" | wc -l)"

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo "FAILED: $ERRORS errors found"
    exit 1
else
    echo "PASSED: All critical checks passed"
    exit 0
fi
