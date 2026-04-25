# Data Truth Policy

Allowed labels:

- Verified fact: directly supported by a cited local source or user-provided source.
- Demo sample: synthetic or partial sample data created only for the demo.
- Assumption: plausible working assumption that needs review.
- Forbidden: claim type that must not be used.

Current source boundary:

- Intake: `/vol1/1000/projects/toyresearch/my - 红队审核与建议.md`
- Local product seed: `data/products_seed.json`
- Local review samples: `data/review_signal_samples.csv`
- Local competitor samples: `data/competitor_samples.csv`
- Frozen truth table: `data/truth_base_frozen.csv`

All outputs must carry the source label beside important claims.
