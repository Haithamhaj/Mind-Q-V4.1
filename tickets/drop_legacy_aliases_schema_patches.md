# Drop legacy aliases & schema patches

- **Opened by:** automation (Codex compliance sweep)
- **Opened on:** 2025-11-10
- **Target close date:** 2025-11-17

## Scope
1. Remove transitional delivery timestamp aliases once downstream warehouses confirm the canonical naming contract.
2. Delete deprecated Stage 08 schema patches after BI workloads fully adopt `contracts/bi/story_v1.1.schema.json`.
3. Collapse the telemetry guard once the low-signal threshold becomes immutable across environments.

## Next steps
- [ ] Confirm with Ops which alias variants are still present in raw feeds.
- [ ] Validate BI tests against the new schema and remove compatibility hooks.
- [ ] Update this ticket with final rollout notes before closing.
