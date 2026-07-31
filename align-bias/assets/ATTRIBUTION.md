# Scenario data attribution

Method and scenarios from **OptimismBench** (Cho & Koshiyama, Holistic AI/UCL,
arXiv 2607.26981, CC BY 4.0).

The bundled JSONL files were derived from the public dataset release
[`seonglae/OptimismBench`](https://huggingface.co/datasets/seonglae/OptimismBench)
on Hugging Face (distributed there under the Apache-2.0 license), retrieved
2026-07-31, revision `64df46d8`.

- `track-b-60.jsonl` — the 60 English naturalistic inverted pairs
  (Track B, complementarity axiom), 6 domains × 10 pairs
  (academic, business, everyday, health_habits, policy, project).
  Positive and negative question phrasings are taken verbatim from the dataset
  (`B_en_*` / `B_en_*inv` items) and merged into one record per pair.
- `track-a-calibration-15.jsonl` — the 15 English controlled calibration items
  (Track A, `A_en_001`–`A_en_015`) with stated base rates. The dataset provides
  one phrasing per item; the complementary (inverted) phrasing for each item was
  authored for AlignBias following the paper's construction rules (third-person,
  minimal-wording change, complement of the same event). `p_true_positive` is
  the stated base rate of the positive-outcome phrasing.

AlignBias itself (the auditing/routing/calibration layer) is Apache-2.0.
