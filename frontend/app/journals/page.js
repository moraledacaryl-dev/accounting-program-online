'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createJournalEntry, fetchChartAccounts, fetchJournalEntryDetail, lockJournalEntry, postJournalEntry, request, reverseJournalEntry } from '../../lib/api';
import { useCurrentUser } from '../../lib/useCurrentUser';
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import { todayISO } from '../cashflow/shared';

const PAGE_SIZE = 100;
const newLine = () => ({ account_code: '', debit: '', credit: '' });
const newEntry = () => ({ entry_date: todayISO(), reference_no: '', description: '', source_module: 'finance', status: 'draft' });
const amount = (value) => Number(value || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 4 });

export default function JournalsPage() {
  const { can } = useCurrentUser();
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const detailRef = useRef(null);
  const [showForm, setShowForm] = useState(false);
  const [page, setPage] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [entry, setEntry] = useState(newEntry);
  const [lines, setLines] = useState([newLine(), newLine()]);

  async function load(targetPage = page) {
    const data = await request(`/journals/entries?limit=${PAGE_SIZE + 1}&offset=${targetPage * PAGE_SIZE}`);
    setRows(data.slice(0, PAGE_SIZE)); setHasNext(data.length > PAGE_SIZE); setPage(targetPage);
  }
  useEffect(() => {
    Promise.all([load(0), fetchChartAccounts(true).then(setAccounts)]).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { if (selected) detailRef.current?.focus(); }, [selected?.entry?.id]);

  const totals = useMemo(() => {
    const debit = lines.reduce((sum, line) => sum + Math.round(Number(line.debit || 0) * 10000), 0);
    const credit = lines.reduce((sum, line) => sum + Math.round(Number(line.credit || 0) * 10000), 0);
    const valid = lines.length >= 2 && lines.every((line) => line.account_code && Number.isFinite(Number(line.debit || 0)) && Number.isFinite(Number(line.credit || 0)) && Number(line.debit || 0) >= 0 && Number(line.credit || 0) >= 0 && (Number(line.debit || 0) > 0) !== (Number(line.credit || 0) > 0));
    return { debit: debit / 10000, credit: credit / 10000, balanced: valid && debit === credit && debit > 0 };
  }, [lines]);

  async function submit(event) {
    event.preventDefault();
    if (busyRef.current || !totals.balanced) return;
    busyRef.current = true; setBusy(true); setError(''); setNotice('');
    try {
      await createJournalEntry({ ...entry, lines: lines.map((line) => ({ ...line, debit: line.debit || '0', credit: line.credit || '0' })) });
      setShowForm(false); setEntry(newEntry()); setLines([newLine(), newLine()]);
      setNotice(entry.status === 'posted' ? 'Journal posted successfully.' : 'Draft saved. Review it before posting.');
      await load(0);
    } catch (e) { setError(e.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function changePage(next) {
    setLoading(true); setError('');
    try { await load(next); } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  async function open(id) {
    setError('');
    try { setSelected(await fetchJournalEntryDetail(id)); } catch (e) { setError(e.message); }
  }
  async function act(fn, id, label) {
    if (busyRef.current) return;
    if (!await confirmAction({ title: `${label} this journal?`, description: label === 'Reverse' ? 'A linked journal will offset the original. Both entries remain in the audit trail.' : 'Review the journal date, accounts, and amounts before continuing.', confirmLabel: label, tone: label === 'Reverse' ? 'danger' : 'primary' })) return;
    busyRef.current = true; setBusy(true); setError('');
    try { await fn(id); await open(id); await load(); setNotice(`${label} completed.`); }
    catch (e) { setError(e.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  function setLine(index, field, value) { setLines((old) => old.map((line, i) => i === index ? { ...line, [field]: value } : line)); }

  return <div className="stack journal-workspace">
    <section className="section">
      <div className="row wrap" style={{ justifyContent: 'space-between' }}><div><h1>Journals</h1><p className="muted">Review the ledger, create balanced entries, and trace every correction.</p></div>
        {can('journals.post') && <button onClick={() => setShowForm(true)} disabled={showForm}>Create Entry</button>}
      </div>
      {error && <p role="alert" className="error-text">{error}</p>}
      {notice && <p role="status" className="notice success">{notice}</p>}
    </section>

    {showForm && can('journals.post') && <section className="section">
      <h2>Create Entry</h2>
      {!accounts.length && <div className="setup-notice"><span>Set up active chart accounts before creating a journal.</span>{can('chart_of_accounts.manage') ? <Link href="/chart-of-accounts">Set up chart of accounts</Link> : <span>Ask your administrator to set up active accounts.</span>}</div>}
      <form onSubmit={submit} aria-busy={busy}>
        <fieldset disabled={busy} className="journal-fields">
          <div className="form-grid">
            <label>Date<input autoFocus required type="date" value={entry.entry_date} onChange={(e) => setEntry({ ...entry, entry_date: e.target.value })} /></label>
            <label>Reference<input maxLength={255} value={entry.reference_no} onChange={(e) => setEntry({ ...entry, reference_no: e.target.value })} /></label>
            <label>Status<select value={entry.status} onChange={(e) => setEntry({ ...entry, status: e.target.value })}><option value="draft">Draft — review before posting</option><option value="posted">Post immediately</option></select></label>
          </div>
          <label>Description<textarea value={entry.description} onChange={(e) => setEntry({ ...entry, description: e.target.value })} /></label>
          <p className="muted">Select an account and enter one positive debit or credit per line. Amounts are in PHP.</p>
          {lines.map((line, index) => <div className="form-grid journal-line" key={index}>
            <label>Account {index + 1}<select aria-label={`Account ${index + 1}`} required value={line.account_code} onChange={(e) => setLine(index, 'account_code', e.target.value)}><option value="">Choose an account</option>{accounts.map((account) => <option key={account.code} value={account.code}>{account.code} · {account.name}</option>)}</select></label>
            <label>Debit {index + 1}<input aria-label={`Debit ${index + 1}`} type="number" min="0" step="0.0001" value={line.debit} onChange={(e) => setLine(index, 'debit', e.target.value)} /></label>
            <label>Credit {index + 1}<input aria-label={`Credit ${index + 1}`} type="number" min="0" step="0.0001" value={line.credit} onChange={(e) => setLine(index, 'credit', e.target.value)} /></label>
            <button type="button" className="secondary" aria-label={`Remove line ${index + 1}`} disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</button>
          </div>)}
          <p role="status" className={totals.balanced ? 'notice success' : 'notice'}>Debit ₱{amount(totals.debit)} · Credit ₱{amount(totals.credit)} · {totals.balanced ? 'Balanced and ready' : 'Complete the lines and balance both totals'}</p>
          <div className="row wrap"><button type="button" className="secondary" disabled={lines.length >= 500} onClick={() => setLines([...lines, newLine()])}>Add line</button><button disabled={!totals.balanced || busy}>{busy ? 'Saving…' : 'Save entry'}</button><button type="button" className="secondary" onClick={() => setShowForm(false)}>Cancel</button></div>
        </fieldset>
      </form>
    </section>}

    <section className="section" aria-busy={loading}>
      <div className="row wrap" style={{ justifyContent: 'space-between' }}><div><h2>Entry Register</h2><p className="small muted">Page {page + 1} · up to 100 entries per page · PHP</p></div>
        <div className="row"><button className="secondary" disabled={page === 0 || loading} onClick={() => changePage(page - 1)}>Previous</button><button className="secondary" disabled={!hasNext || loading} onClick={() => changePage(page + 1)}>Next</button></div>
      </div>
      <div className="table-wrap"><table className="table"><thead><tr><th>Date</th><th>Reference</th><th>Status</th><th>Source</th><th>Control</th></tr></thead><tbody>
        {rows.map((row) => <tr key={row.id}><td>{row.entry_date || 'Date missing'}</td><td><button className="secondary" onClick={() => open(row.id)} aria-label={`View journal ${row.reference_no || row.id}`}>{row.reference_no || `JE-${row.id}`}</button></td><td><span className="badge">{row.is_reversed ? 'reversed' : row.status}</span></td><td>{row.source_module || 'Manual'}</td><td>{row.locked ? 'Locked' : 'Open'}</td></tr>)}
        {!rows.length && <tr><td colSpan="5" className="muted">{loading ? 'Loading journals…' : 'No journal entries on this page. Create an entry or return to the previous page.'}</td></tr>}
      </tbody></table></div>
    </section>

    {selected && <section className="section" ref={detailRef} tabIndex={-1} aria-label="Journal details">
      <div className="row wrap" style={{ justifyContent: 'space-between' }}><div><h2>{selected.entry.reference_no || `JE-${selected.entry.id}`}</h2><p className="muted">{selected.entry.description}</p></div><button className="secondary" onClick={() => setSelected(null)}>Close details</button></div>
      <p>{selected.entry.entry_date} · {selected.entry.is_reversed ? 'Reversed' : selected.entry.status}{selected.entry.locked ? ' · Locked' : ''}</p>
      <div className="table-wrap"><table className="table"><thead><tr><th>Code</th><th>Account</th><th>Debit (PHP)</th><th>Credit (PHP)</th></tr></thead><tbody>{selected.entry.lines.map((line) => <tr key={line.id}><td>{line.account_code}</td><td>{line.account_name}</td><td>{amount(line.debit)}</td><td>{amount(line.credit)}</td></tr>)}</tbody></table></div>
      {can('journals.post') && <div className="row wrap">{selected.entry.status === 'draft' && <button disabled={busy} onClick={() => act(postJournalEntry, selected.entry.id, 'Post')}>Post</button>}{selected.entry.status === 'posted' && !selected.entry.locked && !selected.entry.is_reversed && <button disabled={busy} onClick={() => act(lockJournalEntry, selected.entry.id, 'Lock')}>Lock journal</button>}{selected.entry.status === 'posted' && !selected.entry.is_reversed && <button disabled={busy} className="secondary" onClick={() => act(reverseJournalEntry, selected.entry.id, 'Reverse')}>Reverse</button>}</div>}
      <h3>Audit history</h3>{selected.audit.map((audit) => <div className="card" key={audit.id}><strong>{audit.action}</strong><div className="small muted">{audit.username || 'system'} · {audit.created_at}</div></div>)}{!selected.audit.length && <p className="muted">No audit events yet.</p>}
    </section>}
  </div>;
}
