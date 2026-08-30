'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createJournalEntry,
  fetchJournalEntryDetail,
  lockJournalEntry,
  postJournalEntry,
  request,
  reverseJournalEntry,
} from '../../lib/api';

const PAGE_SIZE = 100;

function newLine() {
  return { account_code: '', account_name: '', debit: '0', credit: '0', memo: '' };
}

export default function JournalsPage() {
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [entry, setEntry] = useState({ entry_date: '', reference_no: '', description: '', source_module: 'finance', status: 'draft' });
  const [lines, setLines] = useState([newLine(), newLine()]);

  async function load(targetPage = page) {
    const offset = targetPage * PAGE_SIZE;
    const data = await request(`/journals/entries?limit=${PAGE_SIZE + 1}&offset=${offset}`);
    setRows(data.slice(0, PAGE_SIZE));
    setHasNext(data.length > PAGE_SIZE);
    setPage(targetPage);
  }

  useEffect(() => {
    load(0).catch((e) => setError(e.message));
  }, []);

  const totals = useMemo(() => {
    const debit = lines.reduce((sum, line) => sum + Number(line.debit || 0), 0);
    const credit = lines.reduce((sum, line) => sum + Number(line.credit || 0), 0);
    return { debit, credit, balanced: Math.round(debit * 100) === Math.round(credit * 100) };
  }, [lines]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      await createJournalEntry({
        ...entry,
        lines: lines
          .filter((line) => line.account_code || line.account_name || Number(line.debit) || Number(line.credit))
          .map((line) => ({ ...line, debit: Number(line.debit || 0), credit: Number(line.credit || 0) })),
      });
      setEntry({ entry_date: '', reference_no: '', description: '', source_module: 'finance', status: 'draft' });
      setLines([newLine(), newLine()]);
      await load(0);
    } catch (e) {
      setError(e.message);
    }
  }

  async function open(id) {
    setSelected(await fetchJournalEntryDetail(id));
  }

  async function act(fn, id) {
    await fn(id);
    setSelected(await fetchJournalEntryDetail(id));
    await load(page);
  }

  async function changePage(targetPage) {
    setError('');
    try {
      await load(targetPage);
      setSelected(null);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <h1>Journals</h1>
        <p className="muted">Balanced entries, posting, journal locks, reversals, and audit history.</p>
        {error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>Create Entry</h2>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>Date<input type="date" value={entry.entry_date} onChange={(e) => setEntry((value) => ({ ...value, entry_date: e.target.value }))} /></label>
              <label>Reference<input value={entry.reference_no} onChange={(e) => setEntry((value) => ({ ...value, reference_no: e.target.value }))} /></label>
              <label>Status<select value={entry.status} onChange={(e) => setEntry((value) => ({ ...value, status: e.target.value }))}><option value="draft">Draft</option><option value="posted">Post immediately</option></select></label>
            </div>
            <label>Description<textarea value={entry.description} onChange={(e) => setEntry((value) => ({ ...value, description: e.target.value }))} /></label>
            <div className="row" style={{ justifyContent: 'space-between' }}><h3>Lines</h3><span className={totals.balanced ? 'badge' : 'error-text'}>Debit {totals.debit.toLocaleString()} / Credit {totals.credit.toLocaleString()}</span></div>
            {lines.map((line, index) => (
              <div key={index} className="form-grid">
                <label>Code<input value={line.account_code} onChange={(e) => setLines((value) => value.map((item, itemIndex) => itemIndex === index ? { ...item, account_code: e.target.value } : item))} /></label>
                <label>Name<input value={line.account_name} onChange={(e) => setLines((value) => value.map((item, itemIndex) => itemIndex === index ? { ...item, account_name: e.target.value } : item))} /></label>
                <label>Debit<input type="number" step="0.01" value={line.debit} onChange={(e) => setLines((value) => value.map((item, itemIndex) => itemIndex === index ? { ...item, debit: e.target.value } : item))} /></label>
                <label>Credit<input type="number" step="0.01" value={line.credit} onChange={(e) => setLines((value) => value.map((item, itemIndex) => itemIndex === index ? { ...item, credit: e.target.value } : item))} /></label>
              </div>
            ))}
            <div className="row"><button type="button" className="secondary" onClick={() => setLines((value) => [...value, newLine()])}>Add line</button><button disabled={!totals.balanced}>Save entry</button></div>
          </form>
        </section>

        <section className="section">
          <div className="row wrap" style={{ justifyContent: 'space-between' }}>
            <div><h2>Entry Register</h2><p className="small muted">Page {page + 1} · up to {PAGE_SIZE} entries per page</p></div>
            <div className="row">
              <button type="button" className="secondary" disabled={page === 0} onClick={() => changePage(page - 1)}>Previous</button>
              <button type="button" className="secondary" disabled={!hasNext} onClick={() => changePage(page + 1)}>Next</button>
            </div>
          </div>
          <table className="table"><thead><tr><th>Date</th><th>Reference</th><th>Status</th><th>Source</th><th>Control</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} onClick={() => open(row.id)} style={{ cursor: 'pointer' }}><td>{row.entry_date || '-'}</td><td>{row.reference_no || `JE-${row.id}`}</td><td><span className="badge">{row.is_reversed ? 'reversed' : row.status}</span></td><td>{row.source_module || '-'}</td><td>{row.locked ? 'Locked' : 'Open'}</td></tr>)}</tbody></table>
        </section>
      </div>

      {selected && (
        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between' }}><div><h2>{selected.entry.reference_no || `JE-${selected.entry.id}`}</h2><p className="muted">{selected.entry.description}</p></div><button className="secondary" onClick={() => setSelected(null)}>Close</button></div>
          <div className="row wrap"><span className="badge">{selected.entry.status}</span>{selected.entry.locked && <span className="badge">Locked by {selected.entry.locked_by || 'user'}</span>}{selected.entry.is_reversed && <span className="badge">Reversed</span>}</div>
          <table className="table"><thead><tr><th>Code</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{selected.entry.lines.map((line) => <tr key={line.id}><td>{line.account_code}</td><td>{line.account_name}</td><td>{Number(line.debit || 0).toLocaleString()}</td><td>{Number(line.credit || 0).toLocaleString()}</td></tr>)}</tbody></table>
          <div className="row wrap">{selected.entry.status === 'draft' && <button onClick={() => act(postJournalEntry, selected.entry.id)}>Post</button>}{selected.entry.status === 'posted' && !selected.entry.locked && !selected.entry.is_reversed && <button onClick={() => act(lockJournalEntry, selected.entry.id)}>Lock journal</button>}{selected.entry.status === 'posted' && !selected.entry.is_reversed && <button className="secondary" onClick={() => act(reverseJournalEntry, selected.entry.id)}>Reverse</button>}</div>
          <h3 style={{ marginTop: 18 }}>Audit history</h3>
          <div className="stack">{selected.audit.map((audit) => <div className="card" key={audit.id}><strong>{audit.action}</strong><div className="small muted">{audit.username || 'system'} · {audit.created_at}</div></div>)}{!selected.audit.length && <p className="muted">No audit events yet.</p>}</div>
        </section>
      )}
    </div>
  );
}
