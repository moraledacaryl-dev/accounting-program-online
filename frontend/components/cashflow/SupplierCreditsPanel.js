'use client';

import { useMemo, useState } from 'react';
import { applySupplierCredit } from '../../lib/supplierCreditApi';
import { todayISO } from '../../app/cashflow/shared';

function sameSupplier(a, b) {
  return String(a || '').trim().toLocaleLowerCase() === String(b || '').trim().toLocaleLowerCase();
}

export default function SupplierCreditsPanel({ credits = [], payables = [], canApply = false, onApplied }) {
  const [targetCredit, setTargetCredit] = useState(null);
  const [payableId, setPayableId] = useState('');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const openCredits = credits.filter((row) => Number(row.balance_available || 0) > 0);
  const eligiblePayables = useMemo(() => {
    if (!targetCredit) return [];
    return payables.filter((row) => (
      Number(row.balance_due || 0) > 0
      && sameSupplier(row.supplier_name, targetCredit.supplier_name)
    ));
  }, [payables, targetCredit]);

  function chooseCredit(credit) {
    const eligible = payables.filter((row) => (
      Number(row.balance_due || 0) > 0
      && sameSupplier(row.supplier_name, credit.supplier_name)
    ));
    const first = eligible[0];
    setTargetCredit(credit);
    setPayableId(first ? String(first.id) : '');
    setAmount(first ? String(Math.min(Number(credit.balance_available || 0), Number(first.balance_due || 0))) : '');
    setNotes(`Apply supplier credit #${credit.id}`);
    setError('');
  }

  function changePayable(value) {
    setPayableId(value);
    const payable = payables.find((row) => String(row.id) === String(value));
    if (targetCredit && payable) {
      setAmount(String(Math.min(Number(targetCredit.balance_available || 0), Number(payable.balance_due || 0))));
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (!targetCredit) return;
    const numericPayable = Number(payableId || 0);
    const numericAmount = Number(amount || 0);
    if (!Number.isFinite(numericPayable) || numericPayable <= 0) {
      setError('Choose an open bill for the same supplier.');
      return;
    }
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError('Enter a valid credit amount.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await applySupplierCredit(targetCredit.id, {
        payable_id: numericPayable,
        amount: numericAmount,
        application_date: todayISO(),
        notes: notes || null,
      });
      setTargetCredit(null);
      setPayableId('');
      setAmount('');
      setNotes('');
      await onApplied?.();
    } catch (err) {
      setError(err.message || 'Failed to apply supplier credit.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="section">
      <div className="row wrap" style={{ justifyContent: 'space-between' }}>
        <div>
          <h2>Available Supplier Credits</h2>
          <p className="muted">Credits from purchase returns can reduce a later bill for the same supplier without recording a cash payment.</p>
        </div>
        <span className="badge">{openCredits.length} open</span>
      </div>

      {openCredits.length === 0 ? (
        <p className="muted">No unapplied supplier credits.</p>
      ) : (
        <div className="table-wrap" tabIndex="0" aria-label="Available supplier credits">
          <table>
            <thead>
              <tr>
                <th>Supplier</th>
                <th>PO</th>
                <th>Credit Date</th>
                <th>Original Credit</th>
                <th>Available</th>
                <th>Status</th>
                {canApply ? <th>Action</th> : null}
              </tr>
            </thead>
            <tbody>
              {openCredits.map((credit) => (
                <tr key={credit.id}>
                  <td>{credit.supplier_name}</td>
                  <td>{credit.purchase_order_id || '—'}</td>
                  <td>{credit.credit_date || '—'}</td>
                  <td>₱{Number(credit.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  <td>₱{Number(credit.balance_available || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  <td>{credit.status || 'open'}</td>
                  {canApply ? <td><button type="button" className="secondary" onClick={() => chooseCredit(credit)}>Apply Credit</button></td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {targetCredit && canApply ? (
        <form onSubmit={submit} className="stack" style={{ marginTop: '1rem' }}>
          <h3>Apply credit for {targetCredit.supplier_name}</h3>
          <div className="form-grid">
            <label>Bill
              <select required value={payableId} onChange={(event) => changePayable(event.target.value)}>
                <option value="">Choose bill</option>
                {eligiblePayables.map((row) => (
                  <option key={row.id} value={row.id}>#{row.id} — balance ₱{Number(row.balance_due || 0).toFixed(2)}</option>
                ))}
              </select>
            </label>
            <label>Credit to Apply
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                max={Math.min(
                  Number(targetCredit.balance_available || 0),
                  Number(payables.find((row) => String(row.id) === String(payableId))?.balance_due || 0),
                ) || undefined}
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </label>
          </div>
          <label>Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          {eligiblePayables.length === 0 ? <p role="alert" className="error-text">There is no open bill for this supplier yet.</p> : null}
          {!!error && <p role="alert" className="error-text">{error}</p>}
          <div className="row wrap">
            <button type="submit" disabled={saving || eligiblePayables.length === 0}>{saving ? 'Applying…' : 'Apply Supplier Credit'}</button>
            <button type="button" className="secondary" disabled={saving} onClick={() => setTargetCredit(null)}>Cancel</button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
