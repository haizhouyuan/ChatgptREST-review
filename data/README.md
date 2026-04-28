# Data

This directory contains Labebe product data, review samples and scraped asset
metadata.

Rules:

- Record source and observation date when adding product facts.
- Do not treat Amazon search results as product truth.
- Do not use old review samples as current DTC evidence unless the SKU/ASIN
  identity gate passes.
- Downloaded image corpora are ignored by git and should be regenerated or
  included in final packages only when needed.

Current important source:

```text
data/labebe/labebe_products.csv
data/labebe/labebe_products_with_images.csv
data/labebe/all_product_images.json
```

