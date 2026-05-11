'use client';

import { useEffect, useMemo, useState } from 'react';
import { getSystemSettings, updateSystemSettings } from '../../lib/api';

const TABS = [
  { key: 'general', label: 'General' },
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'code_generation', label: 'Code Generation' },
  { key: 'financial_defaults', label: 'Financial' },
  { key: 'workflow', label: 'Workflow' },
  { key: 'hospitality', label: 'Hospitality' },
  { key: 'payroll', label: 'Payroll' },
  { key: 'ui', label: 'UI Defaults' },
];

function asBool(value) {
  return value === true || value === 'true';
}

export default function SystemSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [meta, setMeta] = useState({ dashboard_roles: [], dashboard_widgets: [], code_entities: [] });
  const [activeTab, setActiveTab] = useState('general');
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

  function patchNested(sectionKey, nestedKey, patch) {
    setSettings((prev) => ({
      ...(prev || {}),
      [sectionKey]: {
        ...((prev || {})[sectionKey] || {}),
        [nestedKey]: {
          ...(((prev || {})[sectionKey] || {})[nestedKey] || {}),
          ...patch,
        },
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
    return (
      <div className="stack">
        <section className="section">
          <h1>System Settings</h1>
          <p className="muted">Loading settings...</p>
        </section>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="stack">
        <section className="section">
          <h1>System Settings</h1>
          <p className="error-text">{error || 'Unable to load settings.'}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>System Settings</h1>
            <p className="muted">Configure business defaults, dashboard layouts, numbering rules, and workflow controls.</p>
          </div>
          <button type="button" onClick={saveAll} disabled={saving}>{saving ? 'Saving...' : 'Save Settings'}</button>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
        <div className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? 'tab active' : 'tab'}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {activeTab === 'general' && (
        <section className="section">
          <h2>General System</h2>
          <div className="form-grid">
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

      {activeTab === 'dashboard' && (
        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h2>Dashboard Layouts</h2>
              <p className="muted">Choose visible widgets and order per role.</p>
            </div>
            <label style={{ minWidth: 240 }}>
              Dashboard Role
              <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
                {(meta.dashboard_roles || []).map((role) => <option key={role.key} value={role.key}>{role.label}</option>)}
              </select>
            </label>
          </div>

          <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <label>
              Allow Per-user Overrides
              <select
                value={String(asBool(settings.dashboard?.allow_user_overrides))}
                onChange={(e) => patchSection('dashboard', { allow_user_overrides: asBool(e.target.value) })}
              >
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </label>
          </div>

          <div className="grid" style={{ marginTop: 10 }}>
            <div className="section" style={{ marginBottom: 0 }}>
              <h3>Widget Visibility</h3>
              <div className="stack">
                {(meta.dashboard_widgets || []).map((widget) => (
                  <label key={widget.key} className="toggle-field" style={{ marginBottom: 0 }}>
                    <div>
                      <div className="toggle-label">{widget.label}</div>
                      <div className="toggle-hint">{widget.description}</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={selectedRoleWidgets.includes(widget.key)}
                      onChange={() => toggleWidget(selectedRole, widget.key)}
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="section" style={{ marginBottom: 0 }}>
              <h3>Widget Order</h3>
              <div className="stack">
                {selectedRoleWidgets.map((key) => {
                  const info = dashboardWidgetsByKey.get(key) || { label: key };
                  return (
                    <div key={key} className="row" style={{ justifyContent: 'space-between', border: '1px solid var(--line)', borderRadius: 10, padding: '8px 10px' }}>
                      <div>
                        <div className="toggle-label">{info.label}</div>
                        <div className="toggle-hint">{key}</div>
                      </div>
                      <div className="row wrap">
                        <button type="button" className="secondary" onClick={() => moveWidget(selectedRole, key, 'up')}>Up</button>
                        <button type="button" className="secondary" onClick={() => moveWidget(selectedRole, key, 'down')}>Down</button>
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

      {activeTab === 'code_generation' && (
        <section className="section">
          <h2>Code Generation Rules</h2>
          <p className="muted">Codes are generated automatically by entity. Users can still manually override when allowed.</p>
          <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <label>
              Allow Manual Override
              <select
                value={String(asBool(settings.code_generation?.allow_manual_override))}
                onChange={(e) => patchSection('code_generation', { allow_manual_override: asBool(e.target.value) })}
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>
          <table className="table" style={{ marginTop: 10 }}>
            <thead>
              <tr>
                <th>Entity</th>
                <th>Prefix</th>
                <th>Digits</th>
                <th>Include Year</th>
                <th>Include Month</th>
                <th>Separator</th>
                <th>Editable After Create</th>
              </tr>
            </thead>
            <tbody>
              {(meta.code_entities || []).map((entity) => {
                const row = ((settings.code_generation || {}).entities || {})[entity.key] || {};
                return (
                  <tr key={entity.key}>
                    <td>{entity.label}<br /><span className="small muted">{entity.key}</span></td>
                    <td><input value={row.prefix || ''} onChange={(e) => patchCodeEntity(entity.key, { prefix: e.target.value.toUpperCase() })} /></td>
                    <td><input type="number" min="2" max="8" value={row.digits ?? 4} onChange={(e) => patchCodeEntity(entity.key, { digits: Number(e.target.value || 4) })} /></td>
                    <td>
                      <select value={String(asBool(row.include_year))} onChange={(e) => patchCodeEntity(entity.key, { include_year: asBool(e.target.value) })}>
                        <option value="false">No</option>
                        <option value="true">Yes</option>
                      </select>
                    </td>
                    <td>
                      <select value={String(asBool(row.include_month))} onChange={(e) => patchCodeEntity(entity.key, { include_month: asBool(e.target.value) })}>
                        <option value="false">No</option>
                        <option value="true">Yes</option>
                      </select>
                    </td>
                    <td><input value={row.separator || '-'} onChange={(e) => patchCodeEntity(entity.key, { separator: e.target.value || '-' })} /></td>
                    <td>
                      <select value={String(asBool(row.editable_after_create))} onChange={(e) => patchCodeEntity(entity.key, { editable_after_create: asBool(e.target.value) })}>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      {activeTab === 'financial_defaults' && (
        <section className="section">
          <h2>Financial Defaults</h2>
          <div className="form-grid">
            <label>Default Cash Account ID<input value={settings.financial_defaults?.default_cash_account_id ?? ''} onChange={(e) => patchSection('financial_defaults', { default_cash_account_id: e.target.value ? Number(e.target.value) : null })} /></label>
            <label>Default Bank Account ID<input value={settings.financial_defaults?.default_bank_account_id ?? ''} onChange={(e) => patchSection('financial_defaults', { default_bank_account_id: e.target.value ? Number(e.target.value) : null })} /></label>
            <label>Auto Require Daily Reconciliation
              <select value={String(asBool(settings.financial_defaults?.auto_require_daily_reconciliation))} onChange={(e) => patchSection('financial_defaults', { auto_require_daily_reconciliation: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Default BIR Include
              <select value={String(asBool(settings.financial_defaults?.default_bir_include))} onChange={(e) => patchSection('financial_defaults', { default_bir_include: asBool(e.target.value) })}>
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </label>
          </div>
        </section>
      )}

      {activeTab === 'workflow' && (
        <section className="section">
          <h2>Workflow Controls</h2>
          <div className="form-grid">
            <label>Require PR Approval
              <select value={String(asBool(settings.workflow?.require_approval_purchase_requests))} onChange={(e) => patchSection('workflow', { require_approval_purchase_requests: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Require PO Approval
              <select value={String(asBool(settings.workflow?.require_approval_purchase_orders))} onChange={(e) => patchSection('workflow', { require_approval_purchase_orders: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Require Cashflow Approval
              <select value={String(asBool(settings.workflow?.require_approval_cashflow))} onChange={(e) => patchSection('workflow', { require_approval_cashflow: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Require Payroll Review Before Posting
              <select value={String(asBool(settings.workflow?.require_approval_payroll_posting))} onChange={(e) => patchSection('workflow', { require_approval_payroll_posting: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Allow Reopen Locked Periods
              <select value={String(asBool(settings.workflow?.allow_reopen_locked_periods))} onChange={(e) => patchSection('workflow', { allow_reopen_locked_periods: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>
        </section>
      )}

      {activeTab === 'hospitality' && (
        <section className="section">
          <h2>Booking & Hospitality Defaults</h2>
          <div className="form-grid">
            <label>Default Check-in Time<input value={settings.hospitality?.default_check_in_time || ''} onChange={(e) => patchSection('hospitality', { default_check_in_time: e.target.value })} /></label>
            <label>Default Check-out Time<input value={settings.hospitality?.default_check_out_time || ''} onChange={(e) => patchSection('hospitality', { default_check_out_time: e.target.value })} /></label>
            <label>Default Booking Status<input value={settings.hospitality?.default_booking_status || ''} onChange={(e) => patchSection('hospitality', { default_booking_status: e.target.value })} /></label>
          </div>
        </section>
      )}

      {activeTab === 'payroll' && (
        <section className="section">
          <h2>Payroll Defaults</h2>
          <div className="form-grid">
            <label>Period Name Pattern<input value={settings.payroll?.default_period_name_pattern || ''} onChange={(e) => patchSection('payroll', { default_period_name_pattern: e.target.value })} /></label>
            <label>Require Review Before Post
              <select value={String(asBool(settings.payroll?.require_review_before_post))} onChange={(e) => patchSection('payroll', { require_review_before_post: asBool(e.target.value) })}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>
        </section>
      )}

      {activeTab === 'ui' && (
        <section className="section">
          <h2>UI / Operational Defaults</h2>
          <div className="form-grid">
            <label>Table Page Size
              <input
                type="number"
                min="10"
                max="200"
                value={settings.ui?.table_page_size ?? 20}
                onChange={(e) => patchSection('ui', { table_page_size: Number(e.target.value || 20) })}
              />
            </label>
            <label>Show Inactive Items by Default
              <select value={String(asBool(settings.ui?.show_inactive_by_default))} onChange={(e) => patchSection('ui', { show_inactive_by_default: asBool(e.target.value) })}>
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </label>
          </div>
          <label>Default Landing by Role (JSON)
            <textarea
              value={JSON.stringify(settings.ui?.default_landing_by_role || {}, null, 2)}
              onChange={(e) => {
                try {
                  patchSection('ui', { default_landing_by_role: JSON.parse(e.target.value || '{}') });
                  setError('');
                } catch {
                  setError('Default landing JSON is invalid.');
                }
              }}
            />
          </label>
        </section>
      )}
    </div>
  );
}
