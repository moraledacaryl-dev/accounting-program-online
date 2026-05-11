'use client';

import { useEffect, useMemo, useState } from 'react';
import { fetchBirBooks, fetchBirCandidates, fetchLocks, generateBirBooks, saveBirSelections, saveLock } from '../../lib/api';
import { useCurrentUser } from '../../lib/useCurrentUser';

const TABS = ['review', 'missing_docs', 'candidates', 'books', 'locks'];

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function normalizeCandidates(data) {
  const records = (data?.records || []).map((row) => ({ ...row, row_kind: 'record' }));
  const journals = (data?.journal_entries || []).map((row) => ({ ...row, row_kind: 'journal_entry' }));
  const rows = [...records, ...journals];
  return rows.map((row) => {
    const reasons = [];
    if (!row.raw_reference_no) reasons.push('Missing reference number');
    if (!row.book_type) reasons.push('Missing BIR book type');
    if (!row.tax_type || row.tax_type === 'unassigned') reasons.push('Tax type is unassigned');
    return {
      ...row,
      blocked_reasons: reasons,
      blocked: reasons.length > 0,
    };
  });
}

export default function BirPage() {
  const { can } = useCurrentUser();
  const [tab, setTab] = useState('review');
  const [periodKey, setPeriodKey] = useState(new Date().toISOString().slice(0, 7));
  const [books, setBooks] = useState([]);
  const [locks, setLocks] = useState([]);
  const [rows, setRows] = useState([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const includedRows = useMemo(() => rows.filter((row) => !!row.include_in_bir), [rows]);
  const missingRows = useMemo(() => includedRows.filter((row) => row.blocked), [includedRows]);
  const currentPeriodLock = useMemo(
    () => (locks || []).find((row) => row.period_key === periodKey && String(row.scope || '').toLowerCase() === 'bir') || null,
    [locks, periodKey],
  );

  const totals = useMemo(() => {
    let selected = 0;
    let blocked = 0;
    let selectedSales = 0;
    let selectedExpense = 0;
    for (const row of rows) {
      if (!row.include_in_bir) continue;
      selected += 1;
      if (row.blocked) blocked += 1;
      if (row.row_kind === 'record' && row.direction === 'income') selectedSales += Number(row.amount || 0);
      if (row.row_kind === 'record' && row.direction === 'expense') selectedExpense += Number(row.amount || 0);
    }
    return {
      selected,
      blocked,
      selectedSales,
      selectedExpense,
    };
  }, [rows]);

  async function load() {
    const [bookRows, lockRows, candidates] = await Promise.all([
      fetchBirBooks(periodKey),
      fetchLocks(),
      fetchBirCandidates(periodKey),
    ]);
    setBooks(Array.isArray(bookRows) ? bookRows : []);
    setLocks(Array.isArray(lockRows) ? lockRows : []);
    setRows(normalizeCandidates(candidates));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load BIR data.'));
  }, [periodKey]);

  function updateRow(index, patch) {
    setRows((prev) => prev.map((row, i) => {
      if (i !== index) return row;
      const next = { ...row, ...patch };
      const reasons = [];
      if (!next.raw_reference_no) reasons.push('Missing reference number');
      if (!next.book_type) reasons.push('Missing BIR book type');
      if (!next.tax_type || next.tax_type === 'unassigned') reasons.push('Tax type is unassigned');
      next.blocked_reasons = reasons;
      next.blocked = reasons.length > 0;
      return next;
    }));
  }

  async function saveSelections() {
    setError('');
    setNotice('');
    try {
      await saveBirSelections({
        period_key: periodKey,
        selections: rows.map((row) => ({
          source_type: row.source_type,
          source_id: row.source_id,
          include_in_bir: !!row.include_in_bir,
          book_type: row.book_type || null,
          tax_type: row.tax_type || null,
          notes: row.notes || null,
        })),
      });
      setNotice('BIR selections saved.');
      await load();
    } catch (e) {
      setError(e.message || 'Failed to save BIR selections.');
    }
  }

  async function runGenerate() {
    setError('');
    setNotice('');
    try {
      await saveSelections();
      await generateBirBooks({ period_key: periodKey });
      setNotice('BIR books generated from selected rows.');
      await load();
    } catch (e) {
      setError(e.message || 'Failed to generate BIR books.');
    }
  }

  async function setPeriodLock(isLocked) {
    if (!can('bir.manage')) return;
    const reason = window.prompt(isLocked ? 'Reason for lock' : 'Reason for reopen', '');
    if (reason === null) return;
    setError('');
    setNotice('');
    try {
      await saveLock({ period_key: periodKey, scope: 'bir', is_locked: !!isLocked, notes: reason || null });
      setNotice(isLocked ? 'Period locked.' : 'Period reopened.');
      await load();
    } catch (e) {
      setError(e.message || 'Failed to update period lock.');
    }
  }

  function exportBooksCsv() {
    const lines = [['book_type', 'entry_date', 'reference_no', 'description', 'amount', 'tax_type']];
    for (const row of books || []) {
      lines.push([
        row.book_type || '',
        row.entry_date || '',
        row.reference_no || '',
        row.description || '',
        Number(row.amount || 0).toFixed(2),
        row.tax_type || '',
      ]);
    }
    const csv = lines.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bir-books-${periodKey || 'period'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>BIR Workflow</h1>
        <p className="muted">Review queue, missing-doc checks, candidate selection, books generation, and period locks.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
        <div className="row wrap">
          <label>
            Period
            <input type="month" value={periodKey} onChange={(e) => setPeriodKey(e.target.value)} />
          </label>
          {can('bir.manage') && <button type="button" disabled={!!currentPeriodLock?.is_locked} onClick={saveSelections}>Save Selections</button>}
          {can('bir.manage') && <button type="button" disabled={!!currentPeriodLock?.is_locked} onClick={runGenerate}>Generate Books</button>}
          {can('bir.manage') && <button type="button" className="secondary" onClick={() => setPeriodLock(true)}>Lock Period</button>}
          {can('bir.manage') && <button type="button" className="secondary" onClick={() => setPeriodLock(false)}>Reopen Period</button>}
          <button type="button" className="secondary" onClick={exportBooksCsv}>Export Books CSV</button>
        </div>
        <div className="row wrap" style={{ marginTop: 8 }}>
          <span className={`badge ${currentPeriodLock?.is_locked ? 'badge-error' : 'badge-ok'}`}>
            {currentPeriodLock?.is_locked ? 'Period Status: Locked' : 'Period Status: Open'}
          </span>
          {currentPeriodLock?.is_locked && <span className="small muted">Reopen with reason to change selections or regenerate books.</span>}
        </div>
      </section>

      <section className="section">
        <div className="tabs" style={{ marginTop: 0 }}>
          {TABS.map((name) => (
            <button key={name} type="button" className={tab === name ? 'tab active' : 'tab'} onClick={() => setTab(name)}>
              {name}
            </button>
          ))}
        </div>
        <div className="row wrap" style={{ marginTop: 8 }}>
          <span className="badge">Selected: {totals.selected}</span>
          <span className="badge">Blocked: {totals.blocked}</span>
          <span className="badge">Sales: {currency(totals.selectedSales)}</span>
          <span className="badge">Expenses: {currency(totals.selectedExpense)}</span>
        </div>
      </section>

      {tab === 'review' && (
        <section className="section">
          <h2>Review Queue</h2>
          <table className="table">
            <thead><tr><th>Type</th><th>Date</th><th>Reference</th><th>Description</th><th>Include</th><th>Status</th></tr></thead>
            <tbody>
              {includedRows.map((row) => (
                <tr key={`${row.source_type}-${row.source_id}`}>
                  <td>{row.row_kind}</td>
                  <td>{row.entry_date || '-'}</td>
                  <td>{row.display_reference_no || row.reference_no || '-'}</td>
                  <td>{row.name || '-'}</td>
                  <td>{String(!!row.include_in_bir)}</td>
                  <td>{row.blocked ? row.blocked_reasons.join('; ') : 'Ready'}</td>
                </tr>
              ))}
              {!includedRows.length && <tr><td colSpan="6" className="muted">No selected rows yet.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'missing_docs' && (
        <section className="section">
          <h2>Missing Docs / Mapping</h2>
          <table className="table">
            <thead><tr><th>Type</th><th>Reference</th><th>Description</th><th>Issues</th></tr></thead>
            <tbody>
              {missingRows.map((row) => (
                <tr key={`missing-${row.source_type}-${row.source_id}`}>
                  <td>{row.row_kind}</td>
                  <td>{row.display_reference_no || row.reference_no || '-'}</td>
                  <td>{row.name || '-'}</td>
                  <td>{row.blocked_reasons.join('; ')}</td>
                </tr>
              ))}
              {!missingRows.length && <tr><td colSpan="4" className="muted">No blocked selected rows.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'candidates' && (
        <section className="section">
          <h2>Candidate Selection</h2>
          <table className="table dense-table">
            <thead><tr><th>Include</th><th>Type</th><th>Date</th><th>Ref</th><th>Description</th><th>Amount</th><th>Book</th><th>Tax</th><th>Notes</th></tr></thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.source_type}-${row.source_id}`}>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!row.include_in_bir}
                      onChange={(e) => updateRow(index, { include_in_bir: e.target.checked })}
                      disabled={!can('bir.manage') || !!currentPeriodLock?.is_locked}
                    />
                  </td>
                  <td>{row.row_kind}</td>
                  <td>{row.entry_date || '-'}</td>
                  <td>{row.display_reference_no || row.reference_no || '-'}</td>
                  <td>{row.name || '-'}</td>
                  <td>{currency(row.amount || 0)}</td>
                  <td><input value={row.book_type || ''} onChange={(e) => updateRow(index, { book_type: e.target.value })} disabled={!can('bir.manage') || !!currentPeriodLock?.is_locked} /></td>
                  <td><input value={row.tax_type || ''} onChange={(e) => updateRow(index, { tax_type: e.target.value })} disabled={!can('bir.manage') || !!currentPeriodLock?.is_locked} /></td>
                  <td><input value={row.notes || ''} onChange={(e) => updateRow(index, { notes: e.target.value })} disabled={!can('bir.manage') || !!currentPeriodLock?.is_locked} /></td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan="9" className="muted">No candidates for this period.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'books' && (
        <section className="section">
          <h2>Generated Books</h2>
          <table className="table">
            <thead><tr><th>Book</th><th>Date</th><th>Ref</th><th>Description</th><th>Amount</th></tr></thead>
            <tbody>
              {books.map((row) => (
                <tr key={row.id}>
                  <td>{row.book_type}</td>
                  <td>{row.entry_date}</td>
                  <td>{row.reference_no}</td>
                  <td>{row.description}</td>
                  <td>{currency(row.amount || 0)}</td>
                </tr>
              ))}
              {!books.length && <tr><td colSpan="5" className="muted">No generated books for this period.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'locks' && (
        <section className="section">
          <h2>Period Locks</h2>
          <table className="table">
            <thead><tr><th>Period</th><th>Scope</th><th>Locked</th><th>By</th><th>Notes</th></tr></thead>
            <tbody>
              {locks.map((row) => (
                <tr key={row.id}>
                  <td>{row.period_key}</td>
                  <td>{row.scope}</td>
                  <td>{String(row.is_locked)}</td>
                  <td>{row.locked_by || '-'}</td>
                  <td>{row.notes || '-'}</td>
                </tr>
              ))}
              {!locks.length && <tr><td colSpan="5" className="muted">No period locks yet.</td></tr>}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
