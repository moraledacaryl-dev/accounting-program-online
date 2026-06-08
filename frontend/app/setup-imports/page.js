'use client';

import { useState } from 'react';
import { downloadSetupImportTemplate, importSetupWorkbook } from '../../lib/api';
import { useCurrentUser } from '../../lib/useCurrentUser';

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const UPLOAD_PERMISSIONS = ['inventory.manage', 'menu.manage', 'recipes.manage', 'master_data.manage'];

function countLabel(result) {
  const counts = result?.counts || {};
  return [
    `${counts.created || 0} created`,
    `${counts.updated || 0} updated`,
    `${counts.skipped || 0} skipped`,
    `${counts.warnings || 0} warnings`,
    `${counts.errors || 0} errors`,
  ].join(' / ');
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadResultCsv(rows) {
  const csv = [
    ['Sheet', 'Row', 'Action', 'Message'],
    ...rows.map((row) => [row.sheet, row.row, row.action, row.message]),
  ].map((row) => row.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\n');
  saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), 'accounting-setup-import-results.csv');
}

export default function SetupImportsPage() {
  const { can } = useCurrentUser();
  const canUpload = UPLOAD_PERMISSIONS.some((permission) => can(permission));
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [replaceRecipeLines, setReplaceRecipeLines] = useState(true);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  function chooseFile(nextFile) {
    setError('');
    setResult(null);
    if (!nextFile) return setFile(null);
    if (!nextFile.name.toLowerCase().endsWith('.xlsx')) return setError('Choose an .xlsx workbook created from one of the templates.');
    if (nextFile.size > MAX_FILE_BYTES) return setError('Workbook is too large. Keep the .xlsx file under 10 MB.');
    setFile(nextFile);
  }

  async function downloadTemplate(scope) {
    setError(''); setNotice('');
    try {
      const blob = await downloadSetupImportTemplate(scope);
      const filename = scope === 'menu' ? 'accounting-menu-import-template.xlsx' : 'accounting-inventory-menu-import-template.xlsx';
      saveBlob(blob, filename);
      setNotice(`${scope === 'menu' ? 'Menu' : 'Full setup'} template downloaded.`);
    } catch (err) {
      setError(err.message || 'Failed to download template.');
    }
  }

  async function submit(event) {
    event.preventDefault();
    setError(''); setNotice(''); setResult(null);
    if (!canUpload) return setError('Your account has download-only access. Ask a manager to validate and import the completed workbook.');
    if (!file) return setError('Choose an .xlsx file first.');
    setLoading(true);
    try {
      const data = await importSetupWorkbook({ file, dryRun, replaceRecipeLines });
      setResult(data);
      setNotice(data.rolled_back ? `Import found errors and was not saved: ${countLabel(data)}.` : dryRun ? `Validation finished: ${countLabel(data)}.` : `Import finished: ${countLabel(data)}.`);
    } catch (err) {
      setError(err.message || 'Failed to import workbook.');
    } finally {
      setLoading(false);
    }
  }

  const visibleRows = (result?.rows || []).slice(0, 300);
  const validationPassed = !!result?.dry_run && !!result?.ok;

  return (
    <div className="stack">
      <section className="section">
        <div className="toolbar">
          <div>
            <h1>Excel Setup Import</h1>
            <p className="muted">Download a template, fill in the workbook, validate it, and import clean rows without duplicating existing setup data.</p>
          </div>
          <div className="row wrap">
            <button type="button" className="secondary" onClick={() => downloadTemplate('menu')}>Download Menu Template</button>
            <button type="button" className="secondary" onClick={() => downloadTemplate('all')}>Download Full Setup Template</button>
          </div>
        </div>
        {!!notice && <p className="success-text" style={{ marginTop: 8 }}>{notice}</p>}
        {!!error && <p className="error-text" style={{ marginTop: 8 }}>{error}</p>}
      </section>

      <section className="section">
        <h2>{canUpload ? 'Upload Workbook' : 'Download-only Access'}</h2>
        {!canUpload && <p className="muted">You can download and complete either template. A manager with menu, inventory, recipe, or master-data permissions must upload the workbook.</p>}
        {canUpload && <form className="stack" onSubmit={submit}>
          <label
            className={`file-drop ${dragActive ? 'active' : ''}`}
            onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => { event.preventDefault(); setDragActive(false); chooseFile(event.dataTransfer.files?.[0]); }}
          >
            <strong>{file ? file.name : 'Drop an Excel workbook here or choose a file'}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : '.xlsx only, maximum 10 MB'}</span>
            <input type="file" accept=".xlsx" onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
          </label>
          <div className="form-grid">
            <label>Mode<select value={String(dryRun)} onChange={(event) => setDryRun(event.target.value === 'true')}>
              <option value="true">1. Validate only - recommended first</option>
              <option value="false">2. Import validated workbook</option>
            </select></label>
            <label>Recipe Handling<select value={String(replaceRecipeLines)} onChange={(event) => setReplaceRecipeLines(event.target.value === 'true')}>
              <option value="true">Replace recipe lines for items in file</option>
              <option value="false">Update/add matching recipe lines only</option>
            </select></label>
          </div>
          <div className="row wrap">
            <button type="submit" disabled={loading}>{loading ? 'Processing...' : dryRun ? 'Validate Workbook' : 'Import Workbook'}</button>
            <span className="muted small">Ingredient and component units remain controlled by Accounting setup.</span>
          </div>
        </form>}
      </section>

      {result && (
        <section className="section">
          <div className="toolbar">
            <div>
              <h2>Workbook Result</h2>
              <p className="muted">{countLabel(result)}</p>
              {result.rolled_back && <p className="error-text">Nothing was saved. Fix the rows marked errors, then validate again.</p>}
            </div>
            <div className="row wrap">
              <span className={`badge ${result.ok ? 'success' : 'warn'}`}>{result.rolled_back ? 'not saved' : result.dry_run ? 'preview' : 'imported'}</span>
              {!!result.rows?.length && <button type="button" className="secondary" onClick={() => downloadResultCsv(result.rows)}>Download Row Results</button>}
              {validationPassed && <button type="button" onClick={() => { setDryRun(false); setNotice('Validation passed. Review the results, then click Import Workbook to save the data.'); }}>Continue to Import</button>}
            </div>
          </div>
          <table className="table" style={{ marginTop: 10 }}>
            <thead><tr><th>Sheet</th><th>Row</th><th>Action</th><th>Message</th></tr></thead>
            <tbody>
              {visibleRows.map((row, idx) => (
                <tr key={`${row.sheet}-${row.row}-${idx}`}>
                  <td>{row.sheet}</td>
                  <td>{row.row}</td>
                  <td><span className={`badge ${row.action === 'errors' ? 'warn' : row.action === 'warning' ? 'info' : 'success'}`}>{row.action}</span></td>
                  <td>{row.message}</td>
                </tr>
              ))}
              {!visibleRows.length && <tr><td colSpan="4" className="muted">No workbook rows were processed.</td></tr>}
            </tbody>
          </table>
          {(result?.rows || []).length > visibleRows.length && <p className="muted small">Showing the first {visibleRows.length} rows. Download the row results for the full list.</p>}
        </section>
      )}
    </div>
  );
}
