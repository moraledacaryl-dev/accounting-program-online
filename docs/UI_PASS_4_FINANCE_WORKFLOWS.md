# UI Pass 4 — Finance workflow hierarchy

This pass establishes a persistent Finance & Accounting context across Cash & Treasury, ledgers, daily close, payables, receivables, reconciliation, journals, tax close, fixed assets, and reports.

Implemented:

- persistent finance navigation with active-route state;
- direct Money in, Money out, and Transfer actions;
- clearer hierarchy for balances, variances, account positions, and reconciliation;
- more compact treasury hero and KPI presentation;
- stronger status and risk-state differentiation;
- sticky ledger filters and table headers;
- improved local finance drawers with stronger scrim, bounded width, internal scrolling, and persistent actions;
- responsive finance navigation and controls for tablet and mobile;
- improved high-risk action spacing for journals, tax close, and fixed assets.

Existing APIs, posting behavior, approval controls, permissions, reconciliation logic, tax logic, and asset calculations remain unchanged.
