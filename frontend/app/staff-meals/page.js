'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createStaffMeal,
  fetchInventoryItems,
  fetchMenuItems,
  fetchMenuSkus,
  fetchStaffMeals,
} from '../../lib/api';

const PAYMENT_METHODS = ['inventory', 'cash', 'gcash', 'card', 'bank_transfer', 'on_account'];
const SERVED_TO_OPTIONS = ['Kitchen Staff', 'Service Staff', 'Office Staff', 'Other'];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function StaffMealsPage() {
  const [logs, setLogs] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [skus, setSkus] = useState([]);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [form, setForm] = useState({
    meal_no: '',
    meal_date: todayISO(),
    dish_name: '',
    menu_item_id: '',
    sku_id: '',
    quantity: '1',
    served_to: 'Kitchen Staff',
    strict_inventory: true,
    payment_method: 'inventory',
    auto_post_accounting: false,
    notes: '',
  });

  const [ingredientDraft, setIngredientDraft] = useState({
    inventory_item_id: '',
    quantity: '',
    unit: '',
    notes: '',
  });
  const [ingredients, setIngredients] = useState([]);

  const inventoryById = useMemo(() => Object.fromEntries(inventoryItems.map((x) => [x.id, x])), [inventoryItems]);

  const skuOptions = useMemo(() => {
    const menuItemId = Number(form.menu_item_id || 0);
    if (!menuItemId) return [];
    return skus.filter((x) => Number(x.menu_item_id) === menuItemId);
  }, [form.menu_item_id, skus]);

  async function load() {
    const [logRows, menuRows, skuRows, inventoryRows] = await Promise.all([
      fetchStaffMeals(),
      fetchMenuItems(),
      fetchMenuSkus(),
      fetchInventoryItems(),
    ]);
    setLogs(Array.isArray(logRows) ? logRows : []);
    setMenuItems(Array.isArray(menuRows) ? menuRows : []);
    setSkus(Array.isArray(skuRows) ? skuRows : []);
    setInventoryItems(Array.isArray(inventoryRows) ? inventoryRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load staff meal data.'));
  }, []);

  function addIngredientLine() {
    const inventoryItemId = Number(ingredientDraft.inventory_item_id || 0);
    const quantity = asNumber(ingredientDraft.quantity, 0);
    if (!inventoryItemId) {
      setError('Choose an inventory item for this ingredient line.');
      return;
    }
    if (quantity <= 0) {
      setError('Ingredient quantity must be greater than zero.');
      return;
    }

    setIngredients((prev) => [
      ...prev,
      {
        inventory_item_id: inventoryItemId,
        quantity,
        unit: inventoryById[inventoryItemId]?.unit || ingredientDraft.unit || '',
        notes: ingredientDraft.notes || null,
      },
    ]);

    setIngredientDraft({
      inventory_item_id: '',
      quantity: '',
      unit: '',
      notes: '',
    });
    setError('');
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...form,
        menu_item_id: form.menu_item_id ? Number(form.menu_item_id) : null,
        sku_id: form.sku_id ? Number(form.sku_id) : null,
        quantity: asNumber(form.quantity, 0),
        strict_inventory: !!form.strict_inventory,
        auto_post_accounting: !!form.auto_post_accounting,
        ingredients,
      };

      if (!payload.dish_name) {
        setError('Dish name is required.');
        return;
      }
      if (payload.quantity <= 0) {
        setError('Meal quantity must be greater than zero.');
        return;
      }
      if (!payload.menu_item_id && !ingredients.length && payload.strict_inventory) {
        setError('Add a menu item or ingredient lines for strict inventory mode.');
        return;
      }

      await createStaffMeal(payload);
      setNotice(payload.auto_post_accounting ? 'Staff meal posted with inventory deduction and accounting linkage.' : 'Staff meal posted with inventory deduction.');
      setForm({
        meal_no: '',
        meal_date: todayISO(),
        dish_name: '',
        menu_item_id: '',
        sku_id: '',
        quantity: '1',
        served_to: 'Kitchen Staff',
        strict_inventory: true,
        payment_method: 'inventory',
        auto_post_accounting: false,
        notes: '',
      });
      setIngredients([]);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to post staff meal.');
    }
  }

  return (
    <div>
      <section className="section">
        <h1>Staff Meals</h1>
        <p className="muted">Encode dish name, quantity, and ingredients. Inventory is deducted immediately; accounting posting is optional.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>New Staff Meal Log</h2>
          <form onSubmit={submit} className="stack">
            <div className="form-grid">
              <label>Reference (optional)<input value={form.meal_no} onChange={e => setForm(f => ({ ...f, meal_no: e.target.value }))} placeholder="Auto if blank" /></label>
              <label>Meal Date<input type="date" value={form.meal_date} onChange={e => setForm(f => ({ ...f, meal_date: e.target.value }))} /></label>
              <label>Dish Name<input required value={form.dish_name} onChange={e => setForm(f => ({ ...f, dish_name: e.target.value }))} /></label>
              <label>Menu Item (optional)
                <select value={form.menu_item_id} onChange={e => setForm(f => ({ ...f, menu_item_id: e.target.value, sku_id: '' }))}>
                  <option value="">None</option>
                  {menuItems.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              {skuOptions.length > 0 ? (
                <label>Variant (optional)
                  <select value={form.sku_id} onChange={e => setForm(f => ({ ...f, sku_id: e.target.value }))}>
                    <option value="">Use menu recipe</option>
                    {skuOptions.map(sku => <option key={sku.id} value={sku.id}>{sku.variant_name || sku.sku_code || `Variant ${sku.id}`}</option>)}
                  </select>
                </label>
              ) : form.menu_item_id ? (
                <p className="muted small">This menu item has no variants. The menu recipe will be used if available.</p>
              ) : null}
              <label>Quantity<input type="number" min="0.01" step="0.01" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} /></label>
              <label>Served To
                <select value={form.served_to} onChange={e => setForm(f => ({ ...f, served_to: e.target.value }))}>
                  {SERVED_TO_OPTIONS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Strict Inventory
                <select value={String(form.strict_inventory)} onChange={e => setForm(f => ({ ...f, strict_inventory: e.target.value === 'true' }))}>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </label>
              <label>Accounting Payment Source
                <select value={form.payment_method} onChange={e => setForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(row => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>Auto Post Accounting
                <select value={String(form.auto_post_accounting)} onChange={e => setForm(f => ({ ...f, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>

            <label>Notes<textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></label>

            <div className="ops-line-builder">
              <div className="row wrap" style={{ justifyContent: 'space-between' }}>
                <h3>Ingredient Lines</h3>
                <span className="small muted">{ingredients.length} lines</span>
              </div>
              <div className="form-grid">
                <label>Inventory Item
                  <select value={ingredientDraft.inventory_item_id} onChange={e => {
                    const item = inventoryById[Number(e.target.value)];
                    setIngredientDraft(f => ({ ...f, inventory_item_id: e.target.value, unit: item?.unit || '' }));
                  }}>
                    <option value="">Select</option>
                    {inventoryItems.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Quantity<input type="number" min="0.0001" step="0.01" value={ingredientDraft.quantity} onChange={e => setIngredientDraft(f => ({ ...f, quantity: e.target.value }))} /></label>
                <label>Unit<input value={ingredientDraft.unit} readOnly placeholder="Choose ingredient first" /></label>
                <label>Notes<input value={ingredientDraft.notes} onChange={e => setIngredientDraft(f => ({ ...f, notes: e.target.value }))} /></label>
                <div className="align-end"><button type="button" onClick={addIngredientLine}>Add Ingredient</button></div>
              </div>

              <table className="table dense-table">
                <thead><tr><th>Ingredient</th><th>Qty</th><th>Unit</th><th></th></tr></thead>
                <tbody>
                  {ingredients.map((line, idx) => (
                    <tr key={`${line.inventory_item_id}-${idx}`}>
                      <td>{inventoryById[line.inventory_item_id]?.name || `#${line.inventory_item_id}`}</td>
                      <td>{line.quantity}</td>
                      <td>{line.unit || '-'}</td>
                      <td><button className="secondary" type="button" onClick={() => setIngredients(prev => prev.filter((_, i) => i !== idx))}>Remove</button></td>
                    </tr>
                  ))}
                  {!ingredients.length && <tr><td colSpan="4" className="muted">No ingredients added.</td></tr>}
                </tbody>
              </table>
            </div>

            <button type="submit">Post Staff Meal</button>
          </form>
        </section>

        <section className="section">
          <h2>Recent Staff Meal Logs</h2>
          <table className="table">
            <thead><tr><th>Ref</th><th>Date</th><th>Dish</th><th>Served To</th><th>COGS</th><th>Record</th><th>Ingredients</th></tr></thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id}>
                  <td>{log.meal_no}</td>
                  <td>{log.meal_date}</td>
                  <td>{log.dish_name}</td>
                  <td>{log.served_to || '-'}</td>
                  <td>{currency(log.cogs_amount)}</td>
                  <td>{log.expense_record_id || '-'}</td>
                  <td>{(log.lines || []).length}</td>
                </tr>
              ))}
              {!logs.length && <tr><td colSpan="7" className="muted">No staff meal logs yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
