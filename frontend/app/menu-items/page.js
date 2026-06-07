'use client';
import { useEffect, useMemo, useState } from 'react';
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import { createMenuItem, createRecipeLine, deleteMenuItem, deleteRecipeLine, fetchInventoryItems, fetchMasterValues, fetchMenuItems, fetchRecipe, updateMenuItem } from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const MODULE_OPTIONS = [
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'cafe', label: 'Cafe' },
  { value: 'bar', label: 'Bar' },
];

export default function MenuItemsPage() {
  const confirmAction = useConfirmAction();
  const [items, setItems] = useState([]);
  const [inv, setInv] = useState([]);
  const [masterRows, setMasterRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [recipe, setRecipe] = useState([]);
  const [form, setForm] = useState({ name: '', module_slug: 'restaurant', category: '', price: '', notes: '' });
  const [recipeForm, setRecipeForm] = useState({ inventory_item_id: '', quantity: '', unit: '' });
  const [editingId, setEditingId] = useState(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function load() {
    const [menuItems, inventoryItems, masterValues] = await Promise.all([
      fetchMenuItems(),
      fetchInventoryItems(),
      fetchMasterValues('', true),
    ]);
    setItems(menuItems);
    setInv(inventoryItems);
    setMasterRows(masterValues);
    if (selected) setRecipe(await fetchRecipe(selected));
  }

  useEffect(() => { load().catch(console.error); }, [selected]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!form.name.trim()) {
      setError('Item name is required.');
      return;
    }
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        category: form.category || undefined,
        price: Number(form.price || 0),
        notes: form.notes.trim(),
      };
      if (editingId) {
        await updateMenuItem(editingId, payload);
        setNotice('Menu item updated.');
      } else {
        await createMenuItem(payload);
        setNotice('Menu item added.');
      }
      setEditingId(null);
      setForm({ name: '', module_slug: 'restaurant', category: '', price: '', notes: '' });
      await load();
    } catch (err) {
      setError(err.message || 'Unable to save menu item.');
    }
  }

  async function addRecipe(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!selected || Number(recipeForm.inventory_item_id || 0) <= 0 || Number(recipeForm.quantity || 0) <= 0) {
      setError('Please choose an ingredient and quantity.');
      return;
    }
    try {
      const selectedInventoryItem = invById[Number(recipeForm.inventory_item_id)];
      await createRecipeLine(selected, {
        ...recipeForm,
        inventory_item_id: Number(recipeForm.inventory_item_id),
        quantity: Number(recipeForm.quantity || 0),
        unit: selectedInventoryItem?.unit || recipeForm.unit || undefined,
      });
      setNotice('Recipe line added.');
      setRecipeForm({ inventory_item_id: '', quantity: '', unit: '' });
      setRecipe(await fetchRecipe(selected));
    } catch (err) {
      setError(err.message || 'Unable to save recipe line.');
    }
  }

  const categoryMap = useMemo(() => masterRows.reduce((acc, row) => {
    if (!acc[row.group_name]) acc[row.group_name] = [];
    acc[row.group_name].push(row);
    return acc;
  }, {}), [masterRows]);

  const currentCategoryOptions = categoryMap[`${form.module_slug}_categories`] || [];
  const invById = useMemo(() => Object.fromEntries(inv.map((row) => [row.id, row])), [inv]);
  const selectedItem = selected ? items.find((item) => item.id === selected) : null;

  function isMenuSubmittable() {
    return !!form.name.trim();
  }

  function isRecipeSubmittable() {
    return !!(selected && Number(recipeForm.inventory_item_id || 0) > 0 && Number(recipeForm.quantity || 0) > 0);
  }

  return (
    <div>
      <section className="section">
        <h1>Menu & Recipes</h1>
        <p className="muted">Create sellable menu items first, then build ingredient recipes for costing and inventory. Variants are handled later in Restaurant Ops only when they are actually required.</p>
      </section>

      {!!notice && <p className="success-text">{notice}</p>}
      {!!error && <p className="error-text">{error}</p>}

      <div className="grid">
        <section className="section">
          <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isMenuSubmittable)}>
            <div className="form-grid">
              <label>Item name<input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></label>
              <label>Service area<select value={form.module_slug} onChange={e => {
                const nextModule = e.target.value;
                const nextOptions = categoryMap[`${nextModule}_categories`] || [];
                const hasSelected = nextOptions.some((row) => row.value === form.category);
                setForm(f => ({ ...f, module_slug: nextModule, category: hasSelected ? f.category : '' }));
              }}>
                {MODULE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select></label>
              <label>Category<select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                <option value="">Select category...</option>
                {currentCategoryOptions.length ? currentCategoryOptions.map((opt) => <option key={opt.id} value={opt.value}>{opt.value}</option>) : <option value="">Add categories in Menu Categories</option>}
              </select></label>
              <label>Sale price<input type="number" step="0.01" inputMode="decimal" min="0" value={form.price} onChange={e => setForm(f => ({ ...f, price: e.target.value }))} /></label>
            </div>
            <p className="small muted">Price shown here is the menu sale price used for POS and billing.</p>
            <label>Item notes<textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></label>
            <button type="submit">{editingId ? 'Update item' : 'Save item'}</button>
          </form>
        </section>

        <section className="section">
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Category</th><th>Service</th><th>Price</th><th></th></tr>
            </thead>
            <tbody>
              {items.map(i => (
                <tr key={i.id}>
                  <td>{i.name}</td>
                  <td>{i.category || '-'}</td>
                  <td>{i.module_slug}</td>
                  <td>{Number(i.price || 0).toLocaleString()}</td>
                  <td className="row wrap">
                    <button className="secondary" onClick={() => setSelected(i.id)}>Recipe</button>
                    <button className="secondary" onClick={() => { setEditingId(i.id); setForm({ name: i.name, module_slug: i.module_slug, category: i.category || '', price: i.price || '', notes: i.notes || '' }); }}>
                      Edit
                    </button>
                    <button className="secondary" onClick={async () => { if (await confirmAction({ title: `Delete menu item ${i.name}?`, description: 'Items already used by POS sales should be made unavailable instead of removed.' })) { await deleteMenuItem(i.id); if (selected === i.id) setSelected(null); await load(); } }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!items.length && (
                <tr><td colSpan="5" className="muted">No menu items yet. Add an item to start.</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>

      {selected && (
        <section className="section">
          <h2>Recipe for {selectedItem?.name || `Item #${selected}`}</h2>
          <p className="muted">Choose inventory ingredients and quantities for costing and inventory deductions. Unit defaults come from the selected inventory item.</p>
          <form onSubmit={addRecipe} onKeyDown={(event) => shouldPreventEnterSubmit(event, isRecipeSubmittable)}>
            <div className="form-grid">
              <label>Ingredient<select required value={recipeForm.inventory_item_id} onChange={e => {
                const itemId = e.target.value;
                const item = invById[Number(itemId)];
                setRecipeForm((prev) => ({
                  ...prev,
                  inventory_item_id: itemId,
                  unit: item?.unit || prev.unit,
                }));
              }}>
                <option value="">Select ingredient</option>
                {inv.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select></label>
              <label>Quantity<input required type="number" step="0.01" min="0.01" inputMode="decimal" value={recipeForm.quantity} onChange={e => setRecipeForm(f => ({ ...f, quantity: e.target.value }))} /></label>
              <label>Unit<input required readOnly value={recipeForm.unit || ''} placeholder="Choose ingredient first" /></label>
            </div>
            <button type="submit">Add ingredient</button>
          </form>

          <table className="table">
            <thead><tr><th>Ingredient</th><th>Qty</th><th>Unit</th><th></th></tr></thead>
            <tbody>
              {recipe.length ? recipe.map((r) => (
                <tr key={r.id}>
                  <td>{invById[r.inventory_item_id]?.name || `Item #${r.inventory_item_id}`}</td>
                  <td>{r.quantity}</td>
                  <td>{r.unit || '-'}</td>
                  <td>
                    <button className="secondary" onClick={async () => { if (await confirmAction({ title: 'Delete this recipe ingredient?', description: 'Removing it changes costing and future inventory deductions for this menu item.' })) { await deleteRecipeLine(r.id); setRecipe(await fetchRecipe(selected)); } }}>
                      Delete
                    </button>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan="4" className="muted">No recipe lines yet for this item.</td></tr>
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
