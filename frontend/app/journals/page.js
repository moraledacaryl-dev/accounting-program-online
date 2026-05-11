'use client';
import { useEffect, useMemo, useState } from 'react';
import { createJournalEntry, fetchJournalEntries } from '../../lib/api';

function newLine() {
  return { account_code: '', account_name: '', debit: '0', credit: '0', memo: '' };
}

export default function JournalsPage() {
  const [rows, setRows] = useState([]);
  const [entry, setEntry] = useState({ entry_date: '', reference_no: '', description: '', source_module: 'finance', status: 'draft' });
  const [lines, setLines] = useState([newLine(), newLine()]);

  async function load() {
    setRows(await fetchJournalEntries());
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const totals = useMemo(() => {
    const debit = lines.reduce((sum, line) => sum + Number(line.debit || 0), 0);
    const credit = lines.reduce((sum, line) => sum + Number(line.credit || 0), 0);
    return { debit, credit, balanced: Math.round(debit * 100) === Math.round(credit * 100) };
  }, [lines]);

  async function submit(e) {
    e.preventDefault();
    await createJournalEntry({
      ...entry,
      lines: lines
        .filter(l => l.account_code || l.account_name || Number(l.debit || 0) > 0 || Number(l.credit || 0) > 0)
        .map(l => ({ ...l, debit: Number(l.debit || 0), credit: Number(l.credit || 0) })),
    });
    setEntry({ entry_date: '', reference_no: '', description: '', source_module: 'finance', status: 'draft' });
    setLines([newLine(), newLine()]);
    await load();
  }

  function setLine(i, key, value) {
    setLines(prev => prev.map((line, idx) => (idx === i ? { ...line, [key]: value } : line)));
  }

  return (
    <div>
      <section className="section">
        <h1>Journal Entries</h1>
        <p className="muted">Create balanced entries with debit and credit lines.</p>
      </section>

      <div className="grid">
        <section className="section">
          <h2>Create Entry</h2>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>Date<input type="date" value={entry.entry_date} onChange={e => setEntry(f => ({ ...f, entry_date: e.target.value }))} /></label>
              <label>Reference<input value={entry.reference_no} onChange={e => setEntry(f => ({ ...f, reference_no: e.target.value }))} /></label>
              <label>Source Module
                <select value={entry.source_module} onChange={e => setEntry(f => ({ ...f, source_module: e.target.value }))}>
                  <option value="finance">finance</option>
                  <option value="payroll">payroll</option>
                  <option value="rooms">rooms</option>
                  <option value="restaurant">restaurant</option>
                  <option value="inventory">inventory</option>
                </select>
              </label>
            </div>

            <label>Description<textarea value={entry.description} onChange={e => setEntry(f => ({ ...f, description: e.target.value }))} /></label>

            <div className="row" style={{ justifyContent: 'space-between', marginTop: 8 }}>
              <h3>Lines</h3>
              <span className={totals.balanced ? 'badge' : 'error-text'}>
                Debit {totals.debit.toLocaleString()} / Credit {totals.credit.toLocaleString()}
              </span>
            </div>

            {lines.map((line, i) => (
              <div key={i} className="form-grid" style={{ marginBottom: 8 }}>
                <label>Code<input value={line.account_code} onChange={e => setLine(i, 'account_code', e.target.value)} /></label>
                <label>Name<input value={line.account_name} onChange={e => setLine(i, 'account_name', e.target.value)} /></label>
                <label>Debit<input type="number" step="0.01" inputMode="decimal" min="0" value={line.debit} onChange={e => setLine(i, 'debit', e.target.value)} /></label>
                <label>Credit<input type="number" step="0.01" inputMode="decimal" min="0" value={line.credit} onChange={e => setLine(i, 'credit', e.target.value)} /></label>
                <label>Memo<input value={line.memo} onChange={e => setLine(i, 'memo', e.target.value)} /></label>
              </div>
            ))}

            <div className="row wrap">
              <button type="button" className="secondary" onClick={() => setLines(prev => [...prev, newLine()])}>Add Line</button>
              <button type="submit">Save Entry</button>
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Entries</h2>
          {rows.map(r => (
            <div key={r.id} className="section" style={{ marginBottom: 12 }}>
              <h3>{r.reference_no || `JE-${r.id}`}</h3>
              <p className="small muted">{r.entry_date} · {r.description}</p>
              <table className="table">
                <thead><tr><th>Code</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead>
                <tbody>
                  {r.lines.map(l => (
                    <tr key={l.id}>
                      <td>{l.account_code}</td>
                      <td>{l.account_name}</td>
                      <td>{Number(l.debit || 0).toLocaleString()}</td>
                      <td>{Number(l.credit || 0).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
