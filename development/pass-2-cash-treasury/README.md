# Pass 2 — Unified Cash & Treasury

This branch preserves the Pass 2 implementation package built on top of Pass 1.

## Scope

- Unified Cash & Treasury workspace with Overview, Ledger, Daily Close, and Settings
- Backend-calculated running balances
- Unified Money In, Money Out, and Transfer actions
- Transaction detail with approve, cancel, and reverse lifecycle
- Transfer lifecycle and linked account effects
- Daily Close for physical cash accounts
- Configurable reconciliation modes: daily, weekly, monthly, per settlement, manual, or none
- Compatibility redirects from legacy cashflow and treasury routes
- Financial-account reconciliation configuration fields and migration support

## Important integration note

The live `main` branch had moved beyond the original ZIP snapshot used to build Pass 1 and Pass 2. To avoid overwriting newer code, the implementation is stored as a reviewable patch package under this development branch. It must be adapted or rebased against the latest application source before merge.

## Files

- `accounting-pass2-part1.patch`
- `accounting-pass2-part2.patch`

The two parts are consecutive chunks of the original complete patch and should be concatenated before use:

```bash
cat accounting-pass2-part1.patch accounting-pass2-part2.patch > accounting-pass2.patch
```

Nothing in this branch is deployed or merged to `main`.
