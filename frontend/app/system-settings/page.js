'use client';

import { useEffect, useMemo, useState } from 'react';
import { getSystemSettings, updateSystemSettings } from '../../lib/api';

const SECTIONS = [
  { key: 'general', label: 'General', hint: 'Business identity and locale' },
  { key: 'dashboard', label: 'Dashboard', hint: 'Role-based workspace layout' },
  { key: 'code_generation', label: 'Code Generation', hint: 'Numbering and document codes' },
  { key: 'financial_defaults', label: 'Financial', hint: 'Accounts and reconciliation defaults' },
  { key: 'workflow', label: 'Workflow', hint: 'Approvals and period controls' },
  { key: 'hospitality', label: 'Hospitality', hint: 'Booking and stay defaults' },
  { key: 'payroll', label: 'Payroll', hint: 'Payroll period and review defaults' },
  { key: 'ui', label: 'UI Defaults', hint: 'Density and landing behavior' },
];

function asBool(value) {
  return value === true || value === 'true';
}

function SectionHeader({ title, description }) {
  return (
    <div className="settings-section-header">
      <div>
        <h2>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </div>
    </div>
  );
}

export default function SystemSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [meta, setMeta] = useState({ dashboard_roles: [], dashboard_widgets: [], code_entities: [] });
  const [activeSection, setActiveSection] = useState('general');
  const [selectedRole, setSelectedRole] = useState('owner');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const data = await getSystemSettings();
      setSettings(data?.settings || null);
      setMeta(data?.meta || { dashboard_roles: [], dashboard_widgets: [], code_entities: [] });
      const firstRole = (data?.meta?.dashboard_roles || [])[0]?.key || 'owner';
      setSelectedRole(firstRole);
    } catch (err) {
      setError(err.message || 'Failed to load system settings.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function patchSection(sectionKey, patch) {
    setSettings((prev) => ({
      ...(prev || {}),
      [sectionKey]: {
        ...((prev || {})[sectionKey] || {}),
        ...patch,
      },
    }));
  }

  function patchCodeEntity(entityKey, patch) {
    setSettings((prev) => ({
      ...(prev || {}),
      code_generation: {
        ...((prev || {}).code_generation || {}),
        entities: {
          ...(((prev || {}).code_generation || {}).entities || {}),
          [entityKey]: {
            ...((((prev || {}).code_generation || {}).entities || {})[entityKey] || {}),
            ...patch,
          },
        },
      },
    }));
  }

  function getRoleWidgetKeys(roleKey) {
    return (((settings || {}).dashboard || {}).role_widgets || {})[roleKey] || [];
  }

  function setRoleWidgetKeys(roleKey, keys) {
    const roleWidgets = {
      ...((((settings || {}).dashboard || {}).role_widgets) || {}),
      [roleKey]: keys,
    };
    patchSection('dashboard', { role_widgets: roleWidgets });
  }

  function toggleWidget(roleKey, widgetKey) {
    const keys = getRoleWidgetKeys(roleKey);
    if (keys.includes(widgetKey)) {
      setRoleWidgetKeys(roleKey, keys.filter((key) => key !== widgetKey));
      return;
    }
    setRoleWidgetKeys(roleKey, [...keys, widgetKey]);
  }

  function moveWidget(roleKey, widgetKey, direction) {
    const keys = [...getRoleWidgetKeys(roleKey)];
    const index = keys.indexOf(widgetKey);
    if (index < 0) return;
    const nextIndex = direction === 'up' ? index - 1 : index + 1;
    if (nextIndex < 0 || nextIndex >= keys.length) return;
    const swap = keys[nextIndex];
    keys[nextIndex] = keys[index];
    keys[index] = swap;
    setRoleWidgetKeys(roleKey, keys);
  }

  const selectedRoleWidgets = useMemo(() => getRoleWidgetKeys(selectedRole), [settings, selectedRole]);
  const dashboardWidgetsByKey = useMemo(() => {
    const map = new Map();
    for (const row of meta.dashboard_widgets || []) map.set(row.key, row);
    return map;
  }, [meta.dashboard_widgets]);

  const activeMeta = SECTIONS.find((item) => item.key === activeSection) || SECTIONS[0];

  async function saveAll() {
    if (!settings) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const payload = {
        general: settings.general || {},
        dashboard: settings.dashboard || {},
        code_generation: settings.code_generation || {},
        financial_defaults: settings.financial_defaults || {},
        workflow: settings.workflow || {},
        hospitality: settings.hospitality || {},
        payroll: settings.payroll || {},
        ui: settings.ui || {},
      };
      const data = await updateSystemSettings(payload);
      setSettings(data?.settings || settings);
      setMeta(data?.meta || meta);
      setNotice('System settings saved.');
    } catch (err) {
      setError(err.message || 'Failed to save settings.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <section className="section"><h1>System Settings</h1><p className="muted">Loading settings...</p></section>;
  }

  if (!settings) {
    return <section className="section"><h1>System Settings</h1><p className="error-text">{error || 'Unable to load settings.'}</p></section>;
  }

  return (
    <div className="settings-workspace">
      <header className="settings-page-header">
        <div>
          <div className="eyebrow">Administration</div>
          <h1>System Settings</h1>
          <p className="muted">Business defaults, operational controls, numbering rules, and workspace behavior.</p>
        </div>
        <div className="settings-header-actions">
          {notice && <span className="success-text">{notice}</span>}
          {error && <span className="error-text">{error}</span>}
          <button type="button" onClick={saveAll} disabled={saving}>{saving ? 'Saving…' : 'Save Settings'}</button>
        </div>
      </header>

      <div className="settings-layout">
        <aside className="settings-nav" aria-label="Settings sections">
          <div className="settings-nav-title">Configuration</div>
          {SECTIONS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={activeSection === item.key ? 'settings-nav-item active' : 'settings-nav-item'}
              onClick={() => setActiveSection(item.key)}
              aria-current={activeSection === item.key ? 'page' : undefined}
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </button>
          ))}
        </aside>

        <main className="settings-content">
          <div className="settings-context-bar">
            <div>
              <div className="eyebrow">Current section</div>
              <strong>{activeMeta.label}</strong>
              <span className="muted">{activeMeta.hint}</span>
            </div>
          </div>

          {activeSection === 'general' && (
            <section className="section settings-panel">
              <SectionHeader title="General System" description="Core business identity and regional defaults used throughout the application." />
              <div className="form-grid settings-form-grid">
                <label>Business Name<input value={settings.general?.business_name || ''} onChange={(e) => patchSection('general', { business_name: e.target.value })} /></label>
                <label>Property / Resort Name<input value={settings.general?.property_name || ''} onChange={(e) => patchSection('general', { property_name: e.target.value })} /></label>
                <label>Timezone<input value={settings.general?.timezone || ''} onChange={(e) => patchSection('general', { timezone: e.target.value })} /></label>
                <label>Currency<input value={settings.general?.currency || ''} onChange={(e) => patchSection('general', { currency: e.target.value })} /></label>
                <label>Default Language<input value={settings.general?.default_language || ''} onChange={(e) => patchSection('general', { default_language: e.target.value })} /></label>
                <label>Date Format<input value={settings.general?.date_format || ''} onChange={(e) => patchSection('general', { date_format: e.target.value })} /></label>
                <label>Number Format<input value={settings.general?.number_format || ''} onChange={(e) => patchSection('general', { number_format: e.target.value })} /></label>
              </div>
            </section>
          )}

          {activeSection === 'dashboard' && (
            <section className="section settings-panel">
              <SectionHeader title="Dashboard Layouts" description="Control widget visibility and ordering by operational role." />
              <div className="settings-inline-controls">
                <label>Dashboard Role
                  <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
                    {(meta.dashboard_roles || []).map((role) => <option key={role.key} value={role.key}>{role.label}</option>)}
                  </select>
                </label>
                <label>Allow Per-user Overrides
                  <select value={String(asBool(settings.dashboard?.allow_user_overrides))} onChange={(e) => patchSection('dashboard', { allow_user_overrides: asBool(e.target.value) })}>
                    <option value="false">No</option><option value="true">Yes</option>
                  </select>
                </label>
              </div>
              <div className="settings-dual-panel">
                <div className="settings-subpanel">
                  <h3>Widget visibility</h3>
                  <div className="settings-toggle-list">
                    {(meta.dashboard_widgets || []).map((widget) => (
                      <label key={widget.key} className="toggle-field">
                        <div><div className="toggle-label">{widget.label}</div><div className="toggle-hint">{widget.description}</div></div>
                        <input type="checkbox" checked={selectedRoleWidgets.includes(widget.key)} onChange={() => toggleWidget(selectedRole, widget.key)} />
                      </label>
                    ))}
                  </div>
                </div>
                <div className="settings-subpanel">
                  <h3>Widget order</h3>
                  <div className="settings-order-list">
                    {selectedRoleWidgets.map((key, index) => {
                      const info = dashboardWidgetsByKey.get(key) || { label: key };
                      return (
                        <div key={key} className="settings-order-row">
                          <span className="settings-order-index">{index + 1}</span>
                          <div><strong>{info.label}</strong><small>{key}</small></div>
                          <div className="row">
                            <button type="button" className="secondary" onClick={() => moveWidget(selectedRole, key, 'up')} aria-label={`Move ${info.label} up`}>↑</button>
                            <button type="button" className="secondary" onClick={() => moveWidget(selectedRole, key, 'down')} aria-label={`Move ${info.label} down`}>↓</button>
                          </div>
                        </div>
                      );
                    })}
                    {!selectedRoleWidgets.length && <p className="muted">No widgets selected for this role.</p>}
                  </div>
                </div>
              </div>
            </section>
          )}

          {activeSection === 'code_generation' && (
            <section className="section settings-panel">
              <SectionHeader title="Code Generation Rules" description="Automatic identifiers for operational and accounting records." />
              <div className="settings-inline-controls">
                <label>Allow Manual Override
                  <select value={String(asBool(settings.code_generation?.allow_manual_override))} onChange={(e) => patchSection('code_generation', { allow_manual_override: asBool(e.target.value) })}>
                    <option value="true">Yes</option><option value="false">No</option>
                  </select>
                </label>
              </div>
              <div className="table-scroll settings-table-wrap">
                <table className="table dense-table">
                  <thead><tr><th>Entity</th><th>Prefix</th><th>Digits</th><th>Year</th><th>Month</th><th>Separator</th><th>Editable</th></tr></thead>
                  <tbody>
                    {(meta.code_entities || []).map((entity) => {
                      const row = ((settings.code_generation || {}).entities || {})[entity.key] || {};
                      return (
                        <tr key={entity.key}>
                          <td><strong>{entity.label}</strong><br /><span className="small muted">{entity.key}</span></td>
                          <td><input value={row.prefix || ''} onChange={(e) => patchCodeEntity(entity.key, { prefix: e.target.value.toUpperCase() })} /></td>
                          <td><input type="number" min="2" max="8" value={row.digits ?? 4} onChange={(e) => patchCodeEntity(entity.key, { digits: Number(e.target.value || 4) })} /></td>
                          <td><select value={String(asBool(row.include_year))} onChange={(e) => patchCodeEntity(entity.key, { include_year: asBool(e.target.value) })}><option value="false">No</option><option value="true">Yes</option></select></td>
                          <td><select value={String(asBool(row.include_month))} onChange={(e) => patchCodeEntity(entity.key, { include_month: asBool(e.target.value) })}><option value="false">No</option><option value="true">Yes</option></select></td>
                          <td><input value={row.separator || '-'} onChange={(e) => patchCodeEntity(entity.key, { separator: e.target.value || '-' })} /></td>
                          <td><select value={String(asBool(row.editable_after_create))} onChange={(e) => patchCodeEntity(entity.key, { editable_after_create: asBool(e.target.value) })}><option value="true">Yes</option><option value="false">No</option></select></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {activeSection === 'financial_defaults' && (
            <section className="section settings-panel">
              <SectionHeader title="Financial Defaults" description="Default ledger accounts and reconciliation behavior." />
              <div className="form-grid settings-form-grid">
                <label>Default Cash Account ID<input value={settings.financial_defaults?.default_cash_account_id ?? ''} onChange={(e) => patchSection('financial_defaults', { default_cash_account_id: e.target.value ? Number(e.target.value) : null })} /></label>
                <label>Default Bank Account ID<input value={settings.financial_defaults?.default_bank_account_id ?? ''} onChange={(e) => patchSection('financial_defaults', { default_bank_account_id: e.target.value ? Number(e.target.value) : null })} /></label>
                <label>Require Daily Reconciliation<select value={String(asBool(settings.financial_defaults?.auto_require_daily_reconciliation))} onChange={(e) => patchSection('financial_defaults', { auto_require_daily_reconciliation: asBool(e.target.value) })}><option value="true">Yes</option><option value="false">No</option></select></label>
                <label>Default BIR Include<select value={String(asBool(settings.financial_defaults?.default_bir_include))} onChange={(e) => patchSection('financial_defaults', { default_bir_include: asBool(e.target.value) })}><option value="false">No</option><option value="true">Yes</option></select></label>
              </div>
            </section>
          )}

          {activeSection === 'workflow' && (
            <section className="section settings-panel">
              <SectionHeader title="Workflow Controls" description="Approval gates and period-management safeguards." />
              <div className="settings-toggle-grid">
                {[
                  ['Require PR Approval', 'require_approval_purchase_requests'],
                  ['Require PO Approval', 'require_approval_purchase_orders'],
                  ['Require Cashflow Approval', 'require_approval_cashflow'],
                  ['Require Payroll Review Before Posting', 'require_approval_payroll_posting'],
                  ['Allow Reopen Locked Periods', 'allow_reopen_locked_periods'],
                ].map(([label, key]) => (
                  <label key={key} className="toggle-field">
                    <div><div className="toggle-label">{label}</div><div className="toggle-hint">{key.replaceAll('_', ' ')}</div></div>
                    <input type="checkbox" checked={asBool(settings.workflow?.[key])} onChange={(e) => patchSection('workflow', { [key]: e.target.checked })} />
                  </label>
                ))}
              </div>
            </section>
          )}

          {activeSection === 'hospitality' && (
            <section className="section settings-panel">
              <SectionHeader title="Booking & Hospitality Defaults" description="Defaults applied to new stays and booking operations." />
              <div className="form-grid settings-form-grid">
                <label>Default Check-in Time<input value={settings.hospitality?.default_check_in_time || ''} onChange={(e) => patchSection('hospitality', { default_check_in_time: e.target.value })} /></label>
                <label>Default Check-out Time<input value={settings.hospitality?.default_check_out_time || ''} onChange={(e) => patchSection('hospitality', { default_check_out_time: e.target.value })} /></label>
                <label>Default Booking Status<input value={settings.hospitality?.default_booking_status || ''} onChange={(e) => patchSection('hospitality', { default_booking_status: e.target.value })} /></label>
              </div>
            </section>
          )}

          {activeSection === 'payroll' && (
            <section className="section settings-panel">
              <SectionHeader title="Payroll Defaults" description="Period naming and review behavior for payroll processing." />
              <div className="form-grid settings-form-grid">
                <label>Period Name Pattern<input value={settings.payroll?.default_period_name_pattern || ''} onChange={(e) => patchSection('payroll', { default_period_name_pattern: e.target.value })} /></label>
                <label>Require Review Before Post<select value={String(asBool(settings.payroll?.require_review_before_post))} onChange={(e) => patchSection('payroll', { require_review_before_post: asBool(e.target.value) })}><option value="true">Yes</option><option value="false">No</option></select></label>
              </div>
            </section>
          )}

          {activeSection === 'ui' && (
            <section className="section settings-panel">
              <SectionHeader title="UI / Operational Defaults" description="Default density and role landing behavior." />
              <div className="form-grid settings-form-grid">
                <label>Table Page Size<input type="number" min="10" max="200" value={settings.ui?.table_page_size ?? 20} onChange={(e) => patchSection('ui', { table_page_size: Number(e.target.value || 20) })} /></label>
                <label>Show Inactive Items by Default<select value={String(asBool(settings.ui?.show_inactive_by_default))} onChange={(e) => patchSection('ui', { show_inactive_by_default: asBool(e.target.value) })}><option value="false">No</option><option value="true">Yes</option></select></label>
              </div>
              <label>Default Landing by Role (JSON)
                <textarea className="settings-json-editor" value={JSON.stringify(settings.ui?.default_landing_by_role || {}, null, 2)} onChange={(e) => {
                  try {
                    patchSection('ui', { default_landing_by_role: JSON.parse(e.target.value || '{}') });
                    setError('');
                  } catch {
                    setError('Default landing JSON is invalid.');
                  }
                }} />
              </label>
            </section>
          )}

          <div className="settings-save-bar">
            <div><strong>{activeMeta.label}</strong><span className="muted">Changes are saved across all settings sections.</span></div>
            <button type="button" onClick={saveAll} disabled={saving}>{saving ? 'Saving…' : 'Save Settings'}</button>
          </div>
        </main>
      </div>
    </div>
  );
}
