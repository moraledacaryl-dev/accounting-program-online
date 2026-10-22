'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useAppShell } from '../../components/app-shell/AppShellContext';
import { canAccess } from '../../lib/permissions';
import { fetchIntegrationReviewSummary, fetchAcceptedIntegrationLinkageAudit, fetchJournalLinkageReview, fetchManagementReport } from '../../lib/api';
import { fetchCashflowSummary } from '../../lib/cashflowApi';
import { businessDateISO } from '../../lib/businessDate';

const SOURCES = [
  { key: 'journals', label: 'Historical journal linkage', permission: 'reports.view', ownerOnly: true },
  { key: 'cash', label: 'Cash and account reconciliation', permission: 'cashflow.view' },
  { key: 'integrations', label: 'Connected-app intake', permission: 'integrations.view', alternate: 'approvals.view' },
  { key: 'close', label: 'Period close readiness', permission: 'reports.view' },
];
const number = (n) => Number(n || 0).toLocaleString('en-PH');
const count = (source, get) => source?.state === 'ready' ? number(get(source.value)) : '—';

function SourceStatus({ source }) {
  const labels = { ready: 'Checked', restricted: 'Restricted', error: 'Unavailable', loading: 'Checking…' };
  return <span className={'control-source-status ' + (source?.state || 'loading')}>{labels[source?.state] || labels.loading}</span>;
}

export default function ReconciliationCenterPage() {
  const { user } = useAppShell();
  const [refresh, setRefresh] = useState(0);
  const [sources, setSources] = useState({});
  const [checkedAt, setCheckedAt] = useState('');
  const [linkage, setLinkage] = useState({ state: 'loading' });

  useEffect(() => {
    if (!user) return undefined;
    let alive = true;
    const allowed = (item) => (!item.ownerOnly || ['owner', 'admin'].includes(user.role)) &&
      (canAccess(user, item.permission) || (item.alternate && canAccess(user, item.alternate)));
    const initial = Object.fromEntries(SOURCES.map((item) => [
      item.key, allowed(item) ? { state: 'loading' } : { state: 'restricted' },
    ]));
    setSources(initial);
    if (allowed(SOURCES[2])) {
      setLinkage({ state: 'loading' });
      fetchAcceptedIntegrationLinkageAudit()
        .then((value) => { if (alive) setLinkage({ state: 'ready', value }); })
        .catch(() => { if (alive) setLinkage({ state: 'error' }); });
    } else {
      setLinkage({ state: 'restricted' });
    }
    const calls = {
      journals: () => fetchJournalLinkageReview({ queue: 'all', page: 1, limit: 1 }),
      cash: () => fetchCashflowSummary({ date: businessDateISO() }),
      integrations: fetchIntegrationReviewSummary,
      close: fetchManagementReport,
    };
    const active = SOURCES.filter(allowed);
    Promise.allSettled(active.map((item) => calls[item.key]())).then((results) => {
      if (!alive) return;
      const next = { ...initial };
      active.forEach((item, index) => {
        const result = results[index];
        next[item.key] = result.status === 'fulfilled'
          ? { state: 'ready', value: result.value }
          : { state: 'error' };
      });
      setSources(next);
      setCheckedAt(new Date().toLocaleString('en-PH'));
    });
    return () => { alive = false; };
  }, [user, refresh]);

  const journal = sources.journals;
  const cash = sources.cash;
  const integrations = sources.integrations;
  const close = sources.close;
  const checks = close?.state === 'ready' ? (close.value.close_readiness?.checks || []) : [];
  const criticalCategories = checks.filter((c) => c.severity === 'critical' && !c.passed).length;
  const work = useMemo(() => [
    {
      id: 'journal', title: 'Investigate historical journal links',
      value: count(journal, (v) => v.review_summary?.never_reviewed),
      unit: 'transactions awaiting first evidence review',
      description: journal?.state === 'ready'
        ? number(journal.value.review_summary?.missing_journal_links) + ' still lack a direct journal link; ' +
          number(journal.value.review_summary?.evidence_recorded) + ' have evidence recorded, not necessarily resolved.'
        : 'Inspect historical source documents and existing journal records before proposing corrections.',
      href: '/reports?view=journal-review', link: 'Open Journal Review', source: journal,
    },
    {
      id: 'cash', title: 'Complete cash and account reconciliation',
      value: count(cash, (v) => v.summary_cards?.unreconciled_accounts),
      unit: 'accounts requiring reconciliation',
      description: 'Count physical cash and verify bank and GCash statements against transaction evidence.',
      href: '/cashflow?tab=close', link: 'Open daily close', source: cash,
    },
    {
      id: 'integrations', title: 'Review connected financial events',
      value: count(integrations, (v) => v.needs_review),
      unit: 'incoming events needing review',
      description: 'Review POS, Inventory, Payroll and other proposed accounting effects before acceptance.',
      href: '/review-inbox', link: 'Open Review Inbox', source: integrations,
    },
    {
      id: 'close', title: 'Clear period-close blockers',
      value: close?.state === 'ready' ? number(criticalCategories) : '—',
      unit: 'critical close-check categories',
      description: close?.state === 'ready'
        ? number(checks.filter((c) => !c.passed).length) + ' categories contain findings; passing checks do not certify financial balances.'
        : 'Check approvals, unreconciled accounts, aging balances and payroll.',
      href: '/reports', link: 'Open close-readiness report', source: close,
    },
  ], [journal, cash, integrations, close, criticalCategories, checks]);
  const visible = SOURCES.filter((item) => sources[item.key]?.state !== 'restricted');
  const checked = visible.filter((item) => sources[item.key]?.state === 'ready').length;
  const failed = visible.filter((item) => sources[item.key]?.state === 'error').length;

  return <div className="stack control-center-page">
    <section className="section control-center-hero">
      <div><div className="eyebrow">Accounting · Read-only control view</div>
        <h1>Reconciliation Control Center</h1>
        <p>See outstanding accounting checks in one place. This view does not classify, reconcile, post, or adjust transactions.</p>
      </div>
      <div className="control-center-toolbar">
        <button type="button" className="secondary" onClick={() => setRefresh((n) => n + 1)}>Refresh checks</button>
        <span className="small muted" role="status">{checkedAt ? 'Last checked ' + checkedAt : 'Checking available sources…'}</span>
      </div>
    </section>
    <section className="section control-center-coverage" aria-label="Control coverage">
      <div><strong>{checked} / {visible.length}</strong><span>Accessible sources checked</span></div>
      <div><strong>{failed}</strong><span>Sources unavailable</span></div>
      <div><strong>{SOURCES.length - visible.length}</strong><span>Role-restricted sources</span></div>
      <p className="muted">Unavailable and restricted sources never count as zero exceptions. These are separate controls, not amounts to sum.</p>
    </section>
    <section className="control-center-list" aria-label="Reconciliation workstreams">
      {work.map((item, index) => <article className="section control-center-work" key={item.id}>
        <div className="control-center-work-head">
          <div><div className="eyebrow">Priority {index + 1}</div><h2>{item.title}</h2></div>
          <SourceStatus source={item.source} />
        </div>
        <div className="control-center-count"><strong>{item.value}</strong><span>{item.unit}</span></div>
        <p className="muted">{item.description}</p>
        {item.source?.state === 'error' && <p className="error-text" role="alert">This source could not be checked. Refresh or open its original workspace.</p>}
        {item.source?.state === 'restricted'
          ? <span className="small muted">An authorized Accounting reviewer must open this source.</span>
          : <Link href={item.href} className="button-link secondary-link">{item.link} →</Link>}
      </article>)}
    </section>

    {integrations?.state === 'ready' && integrations.value?.delivery_evidence && <section className="section" aria-label="Integration delivery evidence">
      <div className="section-title-row"><div><h2>Source intake evidence</h2>
        <p className="small muted">Events retained in Accounting, including hidden payroll revision history. This is not a live source connectivity check.</p>
      </div><Link href="/review-inbox">Open Review Inbox</Link></div>
      <div className="control-center-check-grid">
        {integrations.value.delivery_evidence.sources.map((item) => <div className="control-center-check" key={item.source_app}>
          <strong>{item.source_app.replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</strong>
          <span>{number(item.received_records)} retained intake records</span>
          <small>Last received: {item.last_received_at ? new Date(item.last_received_at).toLocaleString('en-PH') : 'Not observed'}</small>
          <small>Needs validation: {number(item.validation_failed)} · Awaiting review: {number(item.ready_for_review)}</small>
          <small>Pending over 7 days: {number(item.pending_over_7d)} · Age unavailable: {number(item.pending_age_unknown)}</small>
          <small>Oldest pending: {item.oldest_pending_at ? new Date(item.oldest_pending_at).toLocaleDateString('en-PH') : 'Not observed'}</small>
          <small>Accepted with direct link: {number(item.accepted_with_direct_link)} · Without: {number(item.accepted_without_direct_link)}</small>
          <small>Revised source events: {number(item.multi_revision_events)} · Rejected: {number(item.rejected)}</small>
          <span className="small muted">Sender connectivity: unverified. Unreceived events: unknown.</span>
        </div>)}
      </div>
      <p className="small muted">An accepted reference-only event may correctly have no direct financial link. Duplicate delivery attempts cannot be counted from a deduplicated inbox. Verify transport and upstream outbox evidence separately.</p>
    </section>}

    {linkage.state !== 'restricted' && <section className="section" aria-label="Accepted record linkage audit">
      <div className="section-title-row">
        <div>
          <h2>Accepted Accounting record links</h2>
          <p className="small muted">Checks whether accepted connected-app events reference existing local Accounting records. This does not certify financial balances or upstream delivery.</p>
        </div>
        <Link href="/review-inbox">Review Inbox</Link>
      </div>
      {linkage.state === 'loading' && <p className="muted" role="status">Checking accepted record links…</p>}
      {linkage.state === 'error' && <p className="error-text" role="alert">Record-link verification unavailable. No zero-exception conclusion can be made; refresh checks.</p>}
      {linkage.state === 'ready' && <>
        <div className="control-center-check-grid">
          <div className="control-center-check"><strong>{number(linkage.value.total_accepted)}</strong><span>Accepted events examined</span></div>
          <div className="control-center-check"><strong>{number(linkage.value.verified_record_links)}</strong><span>Existing local record links</span></div>
          <div className="control-center-check"><strong>{number(linkage.value.needs_review)}</strong><span>Links needing review</span></div>
          <div className="control-center-check"><strong>{number(linkage.value.reference_only)}</strong><span>Reference-only effects</span></div>
          <div className="control-center-check"><strong>{number(linkage.value.reversed_targets)}</strong><span>Reversed linked records</span></div>
        </div>
        {linkage.value.findings?.length > 0 && <div className="stack" aria-label="Accepted link exceptions">
          <h3>Linkage exceptions</h3>
          {linkage.value.findings.slice(0, 8).map((item) => <div className="control-center-check" key={item.review_id}>
            <strong>{item.source_app} · Review #{item.review_id}</strong>
            <span>{item.financial_effect.replace(/_/g, ' ')} · {item.state.replace(/_/g, ' ')}</span>
            <small>{item.reason}</small>
          </div>)}
          {linkage.value.findings_truncated && <p className="small muted">More exceptions exist beyond this preview. Open the Review Inbox to inspect individual source events.</p>}
        </div>}
        <p className="small muted">Reversed records are shown separately because a legitimate reversal is not automatically an error. Existing links do not prove the ledger, bank statement or original producer event agrees.</p>
      </>}
    </section>}
    {close?.state === 'ready' && checks.length > 0 && <section className="section">
      <div className="section-title-row"><h2>Period-close checklist</h2><Link href="/reports">Full reports</Link></div>
      <div className="control-center-check-grid">{checks.map((item) => <div className="control-center-check" key={item.key}>
        <span className={item.passed ? 'control-check-clear' : 'control-check-open'}>{item.passed ? 'No findings' : 'Needs attention'}</span>
        <strong>{item.label}</strong><span>{number(item.value)} flagged</span>
        {!item.passed && <small>{item.action}</small>}
      </div>)}</div>
    </section>}
    <p className="small muted">Counts are from the last successful source check. Missing journal links do not prove missing money; saved review evidence does not automatically resolve a linkage. Separate bank, cash and ledger sign-off remains required.</p>
  </div>;
}
