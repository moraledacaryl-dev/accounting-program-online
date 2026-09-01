from __future__ import annotations


def ensure_public_receivable_creation_unsettled(payload) -> None:
    amount_collected = float(getattr(payload, 'amount_collected', 0) or 0)
    if abs(amount_collected) > 0.0001:
        raise ValueError(
            'New receivables must start with amount_collected=0. '
            'Use the Collect workflow so received cash is recorded in a financial account.'
        )


def ensure_public_payable_creation_unsettled(payload) -> None:
    amount_paid = float(getattr(payload, 'amount_paid', 0) or 0)
    if abs(amount_paid) > 0.0001:
        raise ValueError(
            'New payables must start with amount_paid=0. '
            'Use the Pay workflow so paid cash is recorded in a financial account.'
        )
