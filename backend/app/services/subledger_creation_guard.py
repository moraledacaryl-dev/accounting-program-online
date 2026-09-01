from __future__ import annotations


def _as_amount(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def ensure_receivable_starts_unsettled(payload) -> None:
    amount_collected = _as_amount(getattr(payload, 'amount_collected', 0))
    if abs(amount_collected) > 0.0001:
        raise ValueError(
            'New receivables must start with amount_collected = 0. '
            'Record actual collections through the receivable collection workflow.'
        )

    status = str(getattr(payload, 'status', 'open') or 'open').strip().lower()
    if status != 'open':
        raise ValueError(
            'New receivables must start open. '
            'Use the collection or write-off workflow to change settlement state.'
        )


def ensure_payable_starts_unsettled(payload) -> None:
    amount_paid = _as_amount(getattr(payload, 'amount_paid', 0))
    if abs(amount_paid) > 0.0001:
        raise ValueError(
            'New payables must start with amount_paid = 0. '
            'Record actual payments through the payable payment workflow.'
        )

    status = str(getattr(payload, 'status', 'open') or 'open').strip().lower()
    if status != 'open':
        raise ValueError(
            'New payables must start open. '
            'Use the payment or write-off workflow to change settlement state.'
        )
