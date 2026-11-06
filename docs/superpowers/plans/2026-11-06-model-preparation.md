# Local model preparation plan

> Execute inline with superpowers:executing-plans; fresh review before publication. Existing next-step authorization covers local preparation; environment permissions remain separate.

**Goal:** reproducible local checkpoint preparation and real dense/hybrid benchmark when source access/artifact available.
**Architecture:** explicit trusted files/profile → bounded verified staged bundle → actual CPU smoke → atomic new directory; no auto downloads in inference.
**Tech stack:** existing Python3.12/locked optional ONNX profile, unittest, no new dependencies.
**Spec:** [design](../specs/2026-11-06-model-preparation-design.md).

## Global constraints / Review focus

No credentials/model dumps/indexes in Git. No source approvals or site writes. No proxy/domain bypass after observed403. Distinguish artifact smoke from semantic quality. Check revision/provenance, mutable input swaps, symlink/path containment, existing destination and error cleanup.

### Task 1 — local artifact preparation

Files: backend/src/saturn_ai/retrieval/model_preparation.py, scripts/prepare_local_embedding.py, backend/tests/unit/test_model_preparation.py.
Interfaces: prepare_local_model(profile_raw, model_path, tokenizer_path, card_path, license_path, destination)->receipt; profile strict immutable versioned schema, output valid LocalONNXEncoder bundle.
- [ ] Write tests and observe RED for absent feature.
- [ ] Implement bounded explicit import, pinned hashes/provenance and validation before atomic publish; no downloads.
- [ ] Actual numeric ONNX smoke/determinism/external-data/cleanup tests in optional profile; base metadata validation tests with no weights. GREEN and commit.

### Task 2 — actual source/benchmark or precise blocker

- [ ] Confirm actual runtime source access after owner publishes network change; do not retry denied operation until configuration changes.
- [ ] If access/artifact available, check pinned official model card/license/config; import actual checkpoint and run existing unchanged dense/hybrid evaluation, save measured report.
- [ ] Otherwise record exact403/policy/required host and not_run; no substitute graph quality or guessed model SHA/license.

### Task 3 — durable result

- [ ] Independent review, RED→GREEN fixes and full verification in base+optional CI.
- [ ] Update ADR/stage/status/handoff with PR #4 merge a1093fb and main CI42097546595 success.
- [ ] Publish feature PR and check actual CI; no automatic merge, real neural gate remains explicit if blocked.
