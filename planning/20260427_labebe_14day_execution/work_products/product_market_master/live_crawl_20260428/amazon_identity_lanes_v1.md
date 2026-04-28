# Amazon Identity Lanes v1

Date: 2026-04-28

## Scope

This file turns the machine visual gate plus first human review into execution lanes for review/VOC crawling, variant research, retry, and negative training.

No row in this table authorizes public DTC copy. Even identity-whitelist candidates still require claim gating and authorized review access.

## Counts

- blocked_negative_example: 7
- identity_whitelist_candidate: 7
- retry_or_provider_required: 10
- variant_cluster_research: 4

## Review/VOC Seed

Use only these seven rows for the next authorized review/VOC crawl pilot:

- `crocodile-plush-rocker` -> `B071774PWC` | rating `4.6` | reviews `662` | sold by `Labebe Store`
- `pink-unicorn-plush-rocker` -> `B072LXVM36` | rating `4.7` | reviews `2657` | sold by `Labebe Store`
- `llama-plush-rocker` -> `B07MFXJ28Y` | rating `4.7` | reviews `358` | sold by `Labebe Store`
- `white-swan-plush-rocker` -> `B0BVR63LRR` | rating `4.8` | reviews `560` | sold by `Labebe Store`
- `fox-plush-rocker` -> `B0DSVJB5QH` | rating `4.8` | reviews `69` | sold by `Labebe Store`
- `cream-wooden-play-kitchen-set-with-storage` -> `B0FH1KX7XQ` | rating `4.4` | reviews `25` | sold by `Pretty valley`
- `blue-squirrel-plush-rocker` -> `B0FSQ48N93` | rating `4.9` | reviews `77` | sold by `Labebe Store`

## Files

- `amazon_identity_lanes_v1.csv`
- `amazon_review_voc_seed_v1.csv`