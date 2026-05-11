'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createAsset,
  createAssetMaintenance,
  depreciateAsset,
  depreciateAssetsBatch,
  disposeAsset,
  fetchAssets,
  fetchDepreciationLogs,
  fetchDisposalLogs,
  fetchMaintenanceLogs,
  updateAsset,
} from '../../lib/api';

const PAYMENT_METHODS = ['cash', 'gcash', 'card', 'bank_transfer', 'on_account'];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function currentPeriodKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

const EMPTY_ASSET_FORM = {
  name: '',
  asset_class: '',
  location: '',
  acquisition_cost: '',
  acquisition_date: '',
  payment_method: 'cash',
  counterparty: '',
  auto_post_accounting: false,
  useful_life_months: '60',
  salvage_value: '0',
  condition_status: 'Good',
  operational_status: 'Active',
  notes: '',
};

export default function AssetsPage() {
  const [assets, setAssets] = useState([]);
  const [depLogs, setDepLogs] = useState([]);
  const [maintenanceLogs, setMaintenanceLogs] = useState([]);
  const [disposalLogs, setDisposalLogs] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_ASSET_FORM });

  const [depreciationForm, setDepreciationForm] = useState({
    asset_id: '',
    period_key: currentPeriodKey(),
    depreciation_date: '',
    amount: '',
    auto_post_accounting: false,
    notes: '',
  });
  const [batchDepForm, setBatchDepForm] = useState({
    period_key: currentPeriodKey(),
    depreciation_date: '',
    amount: '',
    auto_post_accounting: false,
    notes: '',
  });
  const [maintenanceForm, setMaintenanceForm] = useState({
    asset_id: '',
    service_date: todayISO(),
    vendor: '',
    amount: '',
    payment_method: 'cash',
    auto_post_accounting: false,
    notes: '',
  });
  const [disposalForm, setDisposalForm] = useState({
    asset_id: '',
    disposal_date: todayISO(),
    proceeds_amount: '',
    writeoff_amount: '',
    payment_method: 'cash',
    auto_post_accounting: false,
    notes: '',
  });

  const assetById = useMemo(() => Object.fromEntries(assets.map((a) => [a.id, a])), [assets]);

  async function load() {
    const [assetRows, depRows, maintenanceRows, disposalRows] = await Promise.all([
      fetchAssets(),
      fetchDepreciationLogs(),
      fetchMaintenanceLogs(),
      fetchDisposalLogs(),
    ]);
    setAssets(Array.isArray(assetRows) ? assetRows : []);
    setDepLogs(Array.isArray(depRows) ? depRows : []);
    setMaintenanceLogs(Array.isArray(maintenanceRows) ? maintenanceRows : []);
    setDisposalLogs(Array.isArray(disposalRows) ? disposalRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load asset data.'));
  }, []);

  function resetAssetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_ASSET_FORM });
  }

  async function submitAsset(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...form,
        acquisition_cost: Number(form.acquisition_cost || 0),
        useful_life_months: Number(form.useful_life_months || 60),
        salvage_value: Number(form.salvage_value || 0),
        auto_post_accounting: !!form.auto_post_accounting,
      };
      if (editingId) {
        await updateAsset(editingId, payload);
        setNotice('Asset updated.');
      } else {
        await createAsset(payload);
        setNotice(payload.auto_post_accounting ? 'Asset saved and linked to accounting acquisition entry.' : 'Asset saved.');
      }
      resetAssetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save asset.');
    }
  }

  function editAsset(row) {
    setEditingId(row.id);
    setForm({
      name: row.name || '',
      asset_class: row.asset_class || '',
      location: row.location || '',
      acquisition_cost: row.acquisition_cost ?? '',
      acquisition_date: '',
      payment_method: 'cash',
      counterparty: '',
      auto_post_accounting: false,
      useful_life_months: row.useful_life_months ?? '60',
      salvage_value: row.salvage_value ?? '0',
      condition_status: row.condition_status || 'Good',
      operational_status: row.operational_status || 'Active',
      notes: row.notes || '',
    });
  }

  async function postDepreciation(e) {
    e.preventDefault();
    setError('');
    try {
      if (!depreciationForm.asset_id) {
        setError('Select an asset for depreciation posting.');
        return;
      }
      await depreciateAsset(Number(depreciationForm.asset_id), {
        period_key: depreciationForm.period_key,
        depreciation_date: depreciationForm.depreciation_date || null,
        amount: depreciationForm.amount === '' ? null : Number(depreciationForm.amount),
        auto_post_accounting: !!depreciationForm.auto_post_accounting,
        notes: depreciationForm.notes || null,
      });
      setNotice(depreciationForm.auto_post_accounting ? 'Asset depreciation posted and connected to accounting.' : 'Asset depreciation posted.');
      setDepreciationForm((f) => ({ ...f, amount: '', notes: '' }));
      await load();
    } catch (err) {
      setError(err.message || 'Failed to post depreciation.');
    }
  }

  async function postBatchDepreciation(e) {
    e.preventDefault();
    setError('');
    try {
      await depreciateAssetsBatch({
        period_key: batchDepForm.period_key,
        depreciation_date: batchDepForm.depreciation_date || null,
        amount: batchDepForm.amount === '' ? null : Number(batchDepForm.amount),
        auto_post_accounting: !!batchDepForm.auto_post_accounting,
        notes: batchDepForm.notes || null,
      });
      setNotice(batchDepForm.auto_post_accounting ? 'Batch depreciation completed with accounting links.' : 'Batch depreciation completed.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to run batch depreciation.');
    }
  }

  async function postMaintenance(e) {
    e.preventDefault();
    setError('');
    try {
      if (!maintenanceForm.asset_id) {
        setError('Select an asset for maintenance.');
        return;
      }
      await createAssetMaintenance(Number(maintenanceForm.asset_id), {
        service_date: maintenanceForm.service_date || null,
        vendor: maintenanceForm.vendor || null,
        amount: Number(maintenanceForm.amount || 0),
        payment_method: maintenanceForm.payment_method,
        auto_post_accounting: !!maintenanceForm.auto_post_accounting,
        notes: maintenanceForm.notes || null,
      });
      setNotice(maintenanceForm.auto_post_accounting ? 'Maintenance log posted and connected to accounting.' : 'Maintenance log posted.');
      setMaintenanceForm((f) => ({ ...f, amount: '', notes: '', vendor: '' }));
      await load();
    } catch (err) {
      setError(err.message || 'Failed to post maintenance.');
    }
  }

  async function postDisposal(e) {
    e.preventDefault();
    setError('');
    try {
      if (!disposalForm.asset_id) {
        setError('Select an asset to dispose.');
        return;
      }
      await disposeAsset(Number(disposalForm.asset_id), {
        disposal_date: disposalForm.disposal_date || null,
        proceeds_amount: Number(disposalForm.proceeds_amount || 0),
        writeoff_amount: Number(disposalForm.writeoff_amount || 0),
        payment_method: disposalForm.payment_method,
        auto_post_accounting: !!disposalForm.auto_post_accounting,
        notes: disposalForm.notes || null,
      });
      setNotice(disposalForm.auto_post_accounting ? 'Asset disposal posted and connected to accounting.' : 'Asset disposal posted.');
      setDisposalForm((f) => ({ ...f, proceeds_amount: '', writeoff_amount: '', notes: '' }));
      await load();
    } catch (err) {
      setError(err.message || 'Failed to dispose asset.');
    }
  }

  return (
    <div>
      <section className="section">
        <h1>Assets</h1>
        <p className="muted">Manage acquisition, depreciation, maintenance, and disposal with optional accounting posting.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>{editingId ? `Edit Asset #${editingId}` : 'Add Asset'}</h2>
          <form onSubmit={submitAsset}>
            <div className="form-grid">
              <label>Name<input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></label>
              <label>Asset Class<input value={form.asset_class} onChange={e => setForm(f => ({ ...f, asset_class: e.target.value }))} /></label>
              <label>Location<input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} /></label>
              <label>Acquisition Cost<input type="number" step="0.01" min="0" value={form.acquisition_cost} onChange={e => setForm(f => ({ ...f, acquisition_cost: e.target.value }))} /></label>
              <label>Acquisition Date<input type="date" value={form.acquisition_date} onChange={e => setForm(f => ({ ...f, acquisition_date: e.target.value }))} /></label>
              <label>Payment Method
                <select value={form.payment_method} onChange={e => setForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Counterparty<input value={form.counterparty} onChange={e => setForm(f => ({ ...f, counterparty: e.target.value }))} placeholder="Supplier / vendor" /></label>
              <label>Auto Post Accounting
                <select value={String(form.auto_post_accounting)} onChange={e => setForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
              <label>Useful Life (months)<input type="number" min="1" step="1" value={form.useful_life_months} onChange={e => setForm(f => ({ ...f, useful_life_months: e.target.value }))} /></label>
              <label>Salvage Value<input type="number" step="0.01" min="0" value={form.salvage_value} onChange={e => setForm(f => ({ ...f, salvage_value: e.target.value }))} /></label>
              <label>Condition
                <select value={form.condition_status} onChange={e => setForm(f => ({ ...f, condition_status: e.target.value }))}>
                  <option value="Good">Good</option>
                  <option value="Needs Repair">Needs Repair</option>
                  <option value="For Disposal">For Disposal</option>
                </select>
              </label>
              <label>Operational Status
                <select value={form.operational_status} onChange={e => setForm(f => ({ ...f, operational_status: e.target.value }))}>
                  <option value="Active">Active</option>
                  <option value="Inactive">Inactive</option>
                  <option value="Under Maintenance">Under Maintenance</option>
                  <option value="Disposed">Disposed</option>
                </select>
              </label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingId ? 'Update Asset' : 'Save Asset'}</button>
              {editingId && <button type="button" className="secondary" onClick={resetAssetForm}>Cancel Edit</button>}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Asset List</h2>
          <table className="table">
            <thead><tr><th>Name</th><th>Class</th><th>Cost</th><th>Life</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {assets.map(a => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>{a.asset_class}</td>
                  <td>{currency(a.acquisition_cost)}</td>
                  <td>{a.useful_life_months}</td>
                  <td>{a.operational_status}</td>
                  <td><button className="secondary" type="button" onClick={() => editAsset(a)}>Edit</button></td>
                </tr>
              ))}
              {!assets.length && <tr><td colSpan="6" className="muted">No assets yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Depreciation</h2>
          <form onSubmit={postDepreciation} className="stack">
            <div className="form-grid">
              <label>Asset
                <select value={depreciationForm.asset_id} onChange={e => setDepreciationForm(f => ({ ...f, asset_id: e.target.value }))}>
                  <option value="">Select</option>
                  {assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label>Period (YYYY-MM)<input value={depreciationForm.period_key} onChange={e => setDepreciationForm(f => ({ ...f, period_key: e.target.value }))} /></label>
              <label>Depreciation Date<input type="date" value={depreciationForm.depreciation_date} onChange={e => setDepreciationForm(f => ({ ...f, depreciation_date: e.target.value }))} /></label>
              <label>Amount (blank = auto monthly)<input type="number" step="0.01" min="0" value={depreciationForm.amount} onChange={e => setDepreciationForm(f => ({ ...f, amount: e.target.value }))} /></label>
              <label>Auto Post Accounting
                <select value={String(depreciationForm.auto_post_accounting)} onChange={e => setDepreciationForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>
            <label>Notes<input value={depreciationForm.notes} onChange={e => setDepreciationForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit">Post Depreciation</button>
          </form>

          <form onSubmit={postBatchDepreciation} className="stack" style={{ marginTop: 14 }}>
            <h3>Batch Depreciation</h3>
            <div className="form-grid">
              <label>Period (YYYY-MM)<input value={batchDepForm.period_key} onChange={e => setBatchDepForm(f => ({ ...f, period_key: e.target.value }))} /></label>
              <label>Depreciation Date<input type="date" value={batchDepForm.depreciation_date} onChange={e => setBatchDepForm(f => ({ ...f, depreciation_date: e.target.value }))} /></label>
              <label>Amount Override (optional)<input type="number" step="0.01" min="0" value={batchDepForm.amount} onChange={e => setBatchDepForm(f => ({ ...f, amount: e.target.value }))} /></label>
              <label>Auto Post Accounting
                <select value={String(batchDepForm.auto_post_accounting)} onChange={e => setBatchDepForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>
            <label>Notes<input value={batchDepForm.notes} onChange={e => setBatchDepForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit" className="secondary">Run Batch Depreciation</button>
          </form>
        </section>

        <section className="section">
          <h2>Maintenance / Disposal</h2>
          <form onSubmit={postMaintenance} className="stack">
            <h3>Maintenance</h3>
            <div className="form-grid">
              <label>Asset
                <select value={maintenanceForm.asset_id} onChange={e => setMaintenanceForm(f => ({ ...f, asset_id: e.target.value }))}>
                  <option value="">Select</option>
                  {assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label>Service Date<input type="date" value={maintenanceForm.service_date} onChange={e => setMaintenanceForm(f => ({ ...f, service_date: e.target.value }))} /></label>
              <label>Vendor<input value={maintenanceForm.vendor} onChange={e => setMaintenanceForm(f => ({ ...f, vendor: e.target.value }))} /></label>
              <label>Amount<input type="number" step="0.01" min="0" value={maintenanceForm.amount} onChange={e => setMaintenanceForm(f => ({ ...f, amount: e.target.value }))} /></label>
              <label>Payment Method
                <select value={maintenanceForm.payment_method} onChange={e => setMaintenanceForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Auto Post Accounting
                <select value={String(maintenanceForm.auto_post_accounting)} onChange={e => setMaintenanceForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>
            <label>Notes<input value={maintenanceForm.notes} onChange={e => setMaintenanceForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit">Post Maintenance</button>
          </form>

          <form onSubmit={postDisposal} className="stack" style={{ marginTop: 14 }}>
            <h3>Disposal</h3>
            <div className="form-grid">
              <label>Asset
                <select value={disposalForm.asset_id} onChange={e => setDisposalForm(f => ({ ...f, asset_id: e.target.value }))}>
                  <option value="">Select</option>
                  {assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label>Disposal Date<input type="date" value={disposalForm.disposal_date} onChange={e => setDisposalForm(f => ({ ...f, disposal_date: e.target.value }))} /></label>
              <label>Proceeds<input type="number" step="0.01" min="0" value={disposalForm.proceeds_amount} onChange={e => setDisposalForm(f => ({ ...f, proceeds_amount: e.target.value }))} /></label>
              <label>Writeoff<input type="number" step="0.01" min="0" value={disposalForm.writeoff_amount} onChange={e => setDisposalForm(f => ({ ...f, writeoff_amount: e.target.value }))} /></label>
              <label>Payment Method
                <select value={disposalForm.payment_method} onChange={e => setDisposalForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Auto Post Accounting
                <select value={String(disposalForm.auto_post_accounting)} onChange={e => setDisposalForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>
            <label>Notes<input value={disposalForm.notes} onChange={e => setDisposalForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit" className="secondary">Post Disposal</button>
          </form>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Depreciation Logs</h2>
          <table className="table dense-table">
            <thead><tr><th>Asset</th><th>Period</th><th>Date</th><th>Amount</th><th>Record</th></tr></thead>
            <tbody>
              {depLogs.map(log => (
                <tr key={log.id}>
                  <td>{assetById[log.asset_id]?.name || `#${log.asset_id}`}</td>
                  <td>{log.period_key}</td>
                  <td>{log.depreciation_date || '-'}</td>
                  <td>{currency(log.amount)}</td>
                  <td>{log.record_id || '-'}</td>
                </tr>
              ))}
              {!depLogs.length && <tr><td colSpan="5" className="muted">No depreciation logs yet.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Maintenance / Disposal Logs</h2>
          <table className="table dense-table">
            <thead><tr><th>Type</th><th>Asset</th><th>Date</th><th>Amount</th><th>Record</th></tr></thead>
            <tbody>
              {maintenanceLogs.map(log => (
                <tr key={`m-${log.id}`}>
                  <td>maintenance</td>
                  <td>{assetById[log.asset_id]?.name || `#${log.asset_id}`}</td>
                  <td>{log.service_date || '-'}</td>
                  <td>{currency(log.amount)}</td>
                  <td>{log.record_id || '-'}</td>
                </tr>
              ))}
              {disposalLogs.map(log => (
                <tr key={`d-${log.id}`}>
                  <td>disposal</td>
                  <td>{assetById[log.asset_id]?.name || `#${log.asset_id}`}</td>
                  <td>{log.disposal_date || '-'}</td>
                  <td>{currency(Number(log.proceeds_amount || 0) + Number(log.writeoff_amount || 0))}</td>
                  <td>{log.income_record_id || log.expense_record_id || '-'}</td>
                </tr>
              ))}
              {!maintenanceLogs.length && !disposalLogs.length && <tr><td colSpan="5" className="muted">No maintenance/disposal logs yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
