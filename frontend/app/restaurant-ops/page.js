'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createMenuItem,
  createMenuPromotion,
  createMenuSku,
  createPrepComponent,
  createSaleOrder,
  createStockMovement,
  deleteMenuItem,
  deleteMenuPromotion,
  deleteMenuSku,
  deletePrepComponent,
  fetchInventoryItems,
  fetchMenuItems,
  fetchMenuPromotions,
  fetchMenuSkus,
  fetchPrepComponents,
  fetchSaleOrders,
  fetchStockMovements,
  getMenuSkuCosting,
  getPrepComponentCosting,
  updateMenuItem,
  updateMenuPromotion,
  updateMenuSku,
  updatePrepComponent,
  voidSaleOrder,
} from '../../lib/api';

const MODULE_OPTIONS = ['restaurant', 'breakfast', 'cafe', 'bar'];
const PROMO_TYPES = ['percent_off', 'fixed_discount', 'set_price'];
const PAYMENT_METHODS = ['cash', 'gcash', 'card', 'bank_transfer', 'on_account'];
const EXPENSE_MODULES = ['procurement', 'inventory', 'finance'];
const BUILDER_TABS = ['menu', 'components', 'skus', 'promos'];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function nullableNum(value) {
  if (value === '' || value === null || typeof value === 'undefined') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function currency(value) {
  return `P${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function shortDate(value) {
  if (!value) return '-';
  return value;
}

export default function RestaurantOpsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [menuItems, setMenuItems] = useState([]);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [components, setComponents] = useState([]);
  const [skus, setSkus] = useState([]);
  const [promotions, setPromotions] = useState([]);
  const [sales, setSales] = useState([]);
  const [movements, setMovements] = useState([]);

  const [builderTab, setBuilderTab] = useState('menu');

  const [componentCosting, setComponentCosting] = useState({});
  const [skuCosting, setSkuCosting] = useState({});

  const [menuEditId, setMenuEditId] = useState(null);
  const [menuForm, setMenuForm] = useState({
    name: '',
    module_slug: 'restaurant',
    category: '',
    price: '',
    is_active: true,
    notes: '',
  });

  const [componentEditId, setComponentEditId] = useState(null);
  const [componentForm, setComponentForm] = useState({
    name: '',
    category_name: '',
    yield_quantity: '1',
    yield_unit: '',
    is_active: true,
    notes: '',
  });
  const [componentItemDraft, setComponentItemDraft] = useState({
    inventory_item_id: '',
    quantity: '',
    unit: '',
    wastage_percent: '0',
    sort_order: '0',
    notes: '',
  });
  const [componentItems, setComponentItems] = useState([]);

  const [skuEditId, setSkuEditId] = useState(null);
  const [skuForm, setSkuForm] = useState({
    menu_item_id: '',
    sku_code: '',
    variant_name: '',
    size_label: '',
    price: '',
    packaging_cost: '0',
    labor_cost: '0',
    overhead_cost: '0',
    is_active: true,
    notes: '',
  });
  const [skuRecipeDraft, setSkuRecipeDraft] = useState({
    line_type: 'inventory',
    inventory_item_id: '',
    component_id: '',
    quantity: '',
    unit: '',
    wastage_percent: '0',
    sort_order: '0',
    notes: '',
  });
  const [skuRecipeItems, setSkuRecipeItems] = useState([]);

  const [promoEditId, setPromoEditId] = useState(null);
  const [promoForm, setPromoForm] = useState({
    name: '',
    applies_to: 'sku',
    sku_id: '',
    menu_item_id: '',
    promo_type: 'percent_off',
    promo_value: '',
    min_qty: '',
    start_date: '',
    end_date: '',
    is_active: true,
    notes: '',
  });

  const [saleForm, setSaleForm] = useState({
    order_no: '',
    order_date: todayISO(),
    payment_method: 'cash',
    channel: '',
    counterparty: '',
    notes: '',
    strict_inventory: true,
    auto_post_accounting: false,
  });
  const [saleLineDraft, setSaleLineDraft] = useState({
    menu_item_id: '',
    sku_id: '',
    quantity: '1',
    unit_price: '',
    discount_amount: '0',
  });
  const [saleLines, setSaleLines] = useState([]);

  const [restockForm, setRestockForm] = useState({
    item_id: '',
    movement_type: 'in',
    quantity: '',
    total_item_cost: '',
    delivery_cost: '',
    other_cost: '',
    reason: 'Purchase',
    module_slug: 'inventory',
    reference_no: '',
    movement_date: todayISO(),
    supplier: '',
    notes: '',
    log_expense: false,
    expense_module_slug: 'procurement',
    expense_payment_method: 'cash',
    expense_counterparty: '',
    expense_notes: '',
  });

  const menuById = useMemo(() => Object.fromEntries(menuItems.map((row) => [row.id, row])), [menuItems]);
  const inventoryById = useMemo(() => Object.fromEntries(inventoryItems.map((row) => [row.id, row])), [inventoryItems]);

  const selectedMenuSkus = useMemo(() => {
    const menuItemId = Number(saleLineDraft.menu_item_id || 0);
    if (!menuItemId) return [];
    return skus.filter((row) => Number(row.menu_item_id) === menuItemId);
  }, [saleLineDraft.menu_item_id, skus]);

  const skuFilteredForPromo = useMemo(() => {
    if (!promoForm.menu_item_id) return skus;
    return skus.filter((row) => Number(row.menu_item_id) === Number(promoForm.menu_item_id));
  }, [promoForm.menu_item_id, skus]);

  const lowStockItems = useMemo(() => {
    return inventoryItems
      .filter((row) => Number(row.quantity_on_hand || 0) <= Number(row.reorder_level || 0))
      .sort((a, b) => Number(a.quantity_on_hand || 0) - Number(b.quantity_on_hand || 0));
  }, [inventoryItems]);

  const saleDraftTotals = useMemo(() => {
    let gross = 0;
    let discount = 0;
    for (const line of saleLines) {
      const qty = num(line.quantity, 0);
      const unitPrice = num(line.unit_price, 0);
      const lineDiscount = num(line.discount_amount, 0);
      gross += qty * unitPrice;
      discount += lineDiscount;
    }
    return { gross, discount, net: Math.max(gross - discount, 0) };
  }, [saleLines]);

  async function loadAll({ silent = false } = {}) {
    if (!silent) {
      setLoading(true);
      setError('');
    }
    try {
      const [
        menuRows,
        inventoryRows,
        componentRows,
        skuRows,
        promoRows,
        saleRows,
        movementRows,
      ] = await Promise.all([
        fetchMenuItems(),
        fetchInventoryItems(),
        fetchPrepComponents(),
        fetchMenuSkus(),
        fetchMenuPromotions(),
        fetchSaleOrders(120),
        fetchStockMovements(),
      ]);
      setMenuItems(Array.isArray(menuRows) ? menuRows : []);
      setInventoryItems(Array.isArray(inventoryRows) ? inventoryRows : []);
      setComponents(Array.isArray(componentRows) ? componentRows : []);
      setSkus(Array.isArray(skuRows) ? skuRows : []);
      setPromotions(Array.isArray(promoRows) ? promoRows : []);
      setSales(Array.isArray(saleRows) ? saleRows : []);
      setMovements(Array.isArray(movementRows) ? movementRows : []);
    } catch (e) {
      setError(e.message || 'Failed to load restaurant operations data.');
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    loadAll().catch(console.error);
  }, []);

  function setSuccess(message) {
    setNotice(message);
    setError('');
  }

  function resetMenuForm() {
    setMenuEditId(null);
    setMenuForm({
      name: '',
      module_slug: 'restaurant',
      category: '',
      price: '',
      is_active: true,
      notes: '',
    });
  }

  function resetComponentForm() {
    setComponentEditId(null);
    setComponentForm({
      name: '',
      category_name: '',
      yield_quantity: '1',
      yield_unit: '',
      is_active: true,
      notes: '',
    });
    setComponentItems([]);
    setComponentItemDraft({
      inventory_item_id: '',
      quantity: '',
      unit: '',
      wastage_percent: '0',
      sort_order: '0',
      notes: '',
    });
  }

  function resetSkuForm() {
    setSkuEditId(null);
    setSkuForm({
      menu_item_id: '',
      sku_code: '',
      variant_name: '',
      size_label: '',
      price: '',
      packaging_cost: '0',
      labor_cost: '0',
      overhead_cost: '0',
      is_active: true,
      notes: '',
    });
    setSkuRecipeItems([]);
    setSkuRecipeDraft({
      line_type: 'inventory',
      inventory_item_id: '',
      component_id: '',
      quantity: '',
      unit: '',
      wastage_percent: '0',
      sort_order: '0',
      notes: '',
    });
  }

  function resetPromoForm() {
    setPromoEditId(null);
    setPromoForm({
      name: '',
      applies_to: 'sku',
      sku_id: '',
      menu_item_id: '',
      promo_type: 'percent_off',
      promo_value: '',
      min_qty: '',
      start_date: '',
      end_date: '',
      is_active: true,
      notes: '',
    });
  }

  async function submitMenu(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...menuForm,
        price: num(menuForm.price, 0),
        is_active: !!menuForm.is_active,
      };
      if (menuEditId) await updateMenuItem(menuEditId, payload);
      else await createMenuItem(payload);
      resetMenuForm();
      await loadAll({ silent: true });
      setSuccess('Menu item saved.');
    } catch (err) {
      setError(err.message || 'Unable to save menu item.');
    }
  }

  async function removeMenuItem(id) {
    if (!confirm('Delete this menu item?')) return;
    setError('');
    try {
      await deleteMenuItem(id);
      await loadAll({ silent: true });
      if (menuEditId === id) resetMenuForm();
      setSuccess('Menu item deleted.');
    } catch (err) {
      setError(err.message || 'Unable to delete menu item.');
    }
  }

  function addComponentDraftItem() {
    const inventoryItemId = Number(componentItemDraft.inventory_item_id || 0);
    if (!inventoryItemId) {
      setError('Choose an inventory item for this component line.');
      return;
    }
    if (num(componentItemDraft.quantity, 0) <= 0) {
      setError('Component line quantity must be greater than zero.');
      return;
    }

    setComponentItems((prev) => [
      ...prev,
      {
        inventory_item_id: inventoryItemId,
        quantity: num(componentItemDraft.quantity, 0),
        unit: componentItemDraft.unit || '',
        wastage_percent: num(componentItemDraft.wastage_percent, 0),
        sort_order: componentItemDraft.sort_order === '' ? prev.length : num(componentItemDraft.sort_order, prev.length),
        notes: componentItemDraft.notes || '',
      },
    ]);
    setComponentItemDraft({
      inventory_item_id: '',
      quantity: '',
      unit: '',
      wastage_percent: '0',
      sort_order: String(componentItems.length + 1),
      notes: '',
    });
    setError('');
  }

  async function submitComponent(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...componentForm,
        yield_quantity: num(componentForm.yield_quantity, 1),
        is_active: !!componentForm.is_active,
        items: componentItems.map((row, index) => ({
          inventory_item_id: Number(row.inventory_item_id),
          quantity: num(row.quantity, 0),
          unit: row.unit || '',
          wastage_percent: num(row.wastage_percent, 0),
          sort_order: num(row.sort_order, index),
          notes: row.notes || null,
        })),
      };
      if (componentEditId) await updatePrepComponent(componentEditId, payload);
      else await createPrepComponent(payload);
      resetComponentForm();
      await loadAll({ silent: true });
      setSuccess('Component saved.');
    } catch (err) {
      setError(err.message || 'Unable to save component.');
    }
  }

  async function removeComponent(id) {
    if (!confirm('Delete this prep component?')) return;
    setError('');
    try {
      await deletePrepComponent(id);
      await loadAll({ silent: true });
      if (componentEditId === id) resetComponentForm();
      setSuccess('Component deleted.');
    } catch (err) {
      setError(err.message || 'Unable to delete component.');
    }
  }

  async function showComponentCosting(id) {
    setError('');
    try {
      const data = await getPrepComponentCosting(id);
      setComponentCosting((prev) => ({ ...prev, [id]: data }));
      setSuccess('Component costing computed.');
    } catch (err) {
      setError(err.message || 'Unable to compute component costing.');
    }
  }

  function addSkuRecipeLine() {
    const lineType = skuRecipeDraft.line_type;
    if (num(skuRecipeDraft.quantity, 0) <= 0) {
      setError('SKU recipe quantity must be greater than zero.');
      return;
    }
    if (lineType === 'component' && !Number(skuRecipeDraft.component_id || 0)) {
      setError('Select a component for this recipe line.');
      return;
    }
    if (lineType !== 'component' && !Number(skuRecipeDraft.inventory_item_id || 0)) {
      setError('Select an inventory item for this recipe line.');
      return;
    }

    setSkuRecipeItems((prev) => [
      ...prev,
      {
        line_type: lineType,
        inventory_item_id: lineType === 'component' ? null : Number(skuRecipeDraft.inventory_item_id),
        component_id: lineType === 'component' ? Number(skuRecipeDraft.component_id) : null,
        quantity: num(skuRecipeDraft.quantity, 0),
        unit: skuRecipeDraft.unit || '',
        wastage_percent: num(skuRecipeDraft.wastage_percent, 0),
        sort_order: skuRecipeDraft.sort_order === '' ? prev.length : num(skuRecipeDraft.sort_order, prev.length),
        notes: skuRecipeDraft.notes || '',
      },
    ]);

    setSkuRecipeDraft({
      line_type: 'inventory',
      inventory_item_id: '',
      component_id: '',
      quantity: '',
      unit: '',
      wastage_percent: '0',
      sort_order: String(skuRecipeItems.length + 1),
      notes: '',
    });
    setError('');
  }

  async function submitSku(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...skuForm,
        menu_item_id: Number(skuForm.menu_item_id),
        price: num(skuForm.price, 0),
        packaging_cost: num(skuForm.packaging_cost, 0),
        labor_cost: num(skuForm.labor_cost, 0),
        overhead_cost: num(skuForm.overhead_cost, 0),
        is_active: !!skuForm.is_active,
        recipe_items: skuRecipeItems.map((row, index) => ({
          line_type: row.line_type,
          inventory_item_id: row.line_type === 'component' ? null : Number(row.inventory_item_id),
          component_id: row.line_type === 'component' ? Number(row.component_id) : null,
          quantity: num(row.quantity, 0),
          unit: row.unit || '',
          wastage_percent: num(row.wastage_percent, 0),
          sort_order: num(row.sort_order, index),
          notes: row.notes || null,
        })),
      };

      if (!payload.menu_item_id) {
        setError('Select a menu item for this SKU.');
        return;
      }

      if (skuEditId) await updateMenuSku(skuEditId, payload);
      else await createMenuSku(payload);

      resetSkuForm();
      await loadAll({ silent: true });
      setSuccess('SKU saved.');
    } catch (err) {
      setError(err.message || 'Unable to save SKU.');
    }
  }

  async function removeSku(id) {
    if (!confirm('Delete this SKU?')) return;
    setError('');
    try {
      await deleteMenuSku(id);
      await loadAll({ silent: true });
      if (skuEditId === id) resetSkuForm();
      setSuccess('SKU deleted.');
    } catch (err) {
      setError(err.message || 'Unable to delete SKU.');
    }
  }

  async function showSkuCosting(id) {
    setError('');
    try {
      const data = await getMenuSkuCosting(id);
      setSkuCosting((prev) => ({ ...prev, [id]: data }));
      setSuccess('SKU costing computed.');
    } catch (err) {
      setError(err.message || 'Unable to compute SKU costing.');
    }
  }

  async function submitPromotion(e) {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        name: promoForm.name,
        applies_to: promoForm.applies_to,
        sku_id: promoForm.applies_to === 'sku' ? nullableNum(promoForm.sku_id) : null,
        menu_item_id: promoForm.applies_to === 'menu_item' ? nullableNum(promoForm.menu_item_id) : null,
        promo_type: promoForm.promo_type,
        promo_value: num(promoForm.promo_value, 0),
        min_qty: nullableNum(promoForm.min_qty),
        start_date: promoForm.start_date || null,
        end_date: promoForm.end_date || null,
        is_active: !!promoForm.is_active,
        notes: promoForm.notes || null,
      };

      if (payload.applies_to === 'sku' && !payload.sku_id) {
        setError('Select a SKU for this promotion.');
        return;
      }
      if (payload.applies_to === 'menu_item' && !payload.menu_item_id) {
        setError('Select a menu item for this promotion.');
        return;
      }

      if (promoEditId) await updateMenuPromotion(promoEditId, payload);
      else await createMenuPromotion(payload);

      resetPromoForm();
      await loadAll({ silent: true });
      setSuccess('Promotion saved.');
    } catch (err) {
      setError(err.message || 'Unable to save promotion.');
    }
  }

  async function removePromotion(id) {
    if (!confirm('Delete this promotion?')) return;
    setError('');
    try {
      await deleteMenuPromotion(id);
      await loadAll({ silent: true });
      if (promoEditId === id) resetPromoForm();
      setSuccess('Promotion deleted.');
    } catch (err) {
      setError(err.message || 'Unable to delete promotion.');
    }
  }

  function addSaleLine() {
    const menuItemId = Number(saleLineDraft.menu_item_id || 0);
    if (!menuItemId) {
      setError('Select a menu item before adding a sale line.');
      return;
    }
    const qty = num(saleLineDraft.quantity, 0);
    if (qty <= 0) {
      setError('Sale quantity must be greater than zero.');
      return;
    }

    const skuId = saleLineDraft.sku_id ? Number(saleLineDraft.sku_id) : null;
    const selectedSku = skuId ? skus.find((row) => Number(row.id) === skuId) : null;
    const selectedMenu = menuById[menuItemId];
    const fallbackPrice = selectedSku ? num(selectedSku.price, 0) : num(selectedMenu?.price, 0);

    const unitPrice = saleLineDraft.unit_price === '' ? fallbackPrice : num(saleLineDraft.unit_price, fallbackPrice);

    setSaleLines((prev) => [
      ...prev,
      {
        key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        menu_item_id: menuItemId,
        sku_id: skuId,
        quantity: qty,
        unit_price: unitPrice,
        discount_amount: num(saleLineDraft.discount_amount, 0),
      },
    ]);

    setSaleLineDraft((prev) => ({
      ...prev,
      quantity: '1',
      unit_price: '',
      discount_amount: '0',
    }));
    setError('');
  }

  async function submitSale(e) {
    e.preventDefault();
    setError('');
    if (!saleLines.length) {
      setError('Add at least one line before posting a sale.');
      return;
    }

    try {
      const payload = {
        order_no: saleForm.order_no || null,
        order_date: saleForm.order_date || null,
        payment_method: saleForm.payment_method || null,
        channel: saleForm.channel || null,
        counterparty: saleForm.counterparty || null,
        notes: saleForm.notes || null,
        strict_inventory: !!saleForm.strict_inventory,
        auto_post_accounting: !!saleForm.auto_post_accounting,
        lines: saleLines.map((line) => ({
          menu_item_id: Number(line.menu_item_id),
          sku_id: line.sku_id ? Number(line.sku_id) : null,
          quantity: num(line.quantity, 0),
          unit_price: nullableNum(line.unit_price),
          discount_amount: num(line.discount_amount, 0),
        })),
      };

      const posted = await createSaleOrder(payload);
      setSaleLines([]);
      setSaleForm((prev) => ({ ...prev, order_no: '', notes: '', counterparty: '' }));
      await loadAll({ silent: true });
      setSuccess(`Sale posted: ${posted.order_no}`);
    } catch (err) {
      setError(err.message || 'Unable to post sale.');
    }
  }

  async function handleVoidSale(row) {
    const reason = window.prompt(`Void sale ${row.order_no}\nEnter reason:`, 'Customer cancellation');
    if (!reason || !reason.trim()) return;
    const reverseInventory = window.confirm('Reverse inventory deductions for this sale?');
    const autoPostAccounting = window.confirm('Create accounting reversal records now?');

    setError('');
    try {
      await voidSaleOrder(row.id, {
        reason: reason.trim(),
        void_date: todayISO(),
        reverse_inventory: !!reverseInventory,
        auto_post_accounting: !!autoPostAccounting,
      });
      await loadAll({ silent: true });
      setSuccess(`Sale voided: ${row.order_no}`);
    } catch (err) {
      setError(err.message || 'Unable to void sale.');
    }
  }

  async function submitRestock(e) {
    e.preventDefault();
    setError('');
    try {
      const totalItemCost = num(restockForm.total_item_cost, 0);
      const deliveryCost = num(restockForm.delivery_cost, 0);
      const otherCost = num(restockForm.other_cost, 0);
      const landedTotal = totalItemCost + deliveryCost + otherCost;
      const payload = {
        ...restockForm,
        item_id: Number(restockForm.item_id),
        quantity: num(restockForm.quantity, 0),
        unit_cost: restockForm.movement_type === 'in' ? (num(restockForm.quantity, 0) > 0 ? landedTotal / num(restockForm.quantity, 0) : 0) : 0,
        total_item_cost: restockForm.movement_type === 'in' ? totalItemCost : undefined,
        delivery_cost: restockForm.movement_type === 'in' ? deliveryCost : undefined,
        other_cost: restockForm.movement_type === 'in' ? otherCost : undefined,
        log_expense: !!restockForm.log_expense,
      };
      if (!payload.item_id) {
        setError('Choose an inventory item to restock.');
        return;
      }
      if (payload.quantity <= 0) {
        setError('Restock quantity must be greater than zero.');
        return;
      }

      await createStockMovement(payload);
      setRestockForm((prev) => ({
        ...prev,
        quantity: '',
        total_item_cost: '',
        delivery_cost: '',
        other_cost: '',
        reference_no: '',
        supplier: '',
        notes: '',
        expense_counterparty: '',
        expense_notes: '',
      }));
      await loadAll({ silent: true });
      setSuccess(`Restock posted.${payload.log_expense ? ' Linked accounting expense was created.' : ''}`);
    } catch (err) {
      setError(err.message || 'Unable to post restock.');
    }
  }

  function startEditMenu(row) {
    setBuilderTab('menu');
    setMenuEditId(row.id);
    setMenuForm({
      name: row.name || '',
      module_slug: row.module_slug || 'restaurant',
      category: row.category || '',
      price: String(row.price ?? ''),
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  function startEditComponent(row) {
    setBuilderTab('components');
    setComponentEditId(row.id);
    setComponentForm({
      name: row.name || '',
      category_name: row.category_name || '',
      yield_quantity: String(row.yield_quantity ?? '1'),
      yield_unit: row.yield_unit || '',
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
    setComponentItems(Array.isArray(row.items) ? row.items.map((item) => ({
      inventory_item_id: item.inventory_item_id,
      quantity: item.quantity,
      unit: item.unit || '',
      wastage_percent: item.wastage_percent ?? 0,
      sort_order: item.sort_order ?? 0,
      notes: item.notes || '',
    })) : []);
  }

  function startEditSku(row) {
    setBuilderTab('skus');
    setSkuEditId(row.id);
    setSkuForm({
      menu_item_id: String(row.menu_item_id || ''),
      sku_code: row.sku_code || '',
      variant_name: row.variant_name || '',
      size_label: row.size_label || '',
      price: String(row.price ?? ''),
      packaging_cost: String(row.packaging_cost ?? '0'),
      labor_cost: String(row.labor_cost ?? '0'),
      overhead_cost: String(row.overhead_cost ?? '0'),
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
    setSkuRecipeItems(Array.isArray(row.recipe_items) ? row.recipe_items.map((item) => ({
      line_type: item.line_type || 'inventory',
      inventory_item_id: item.inventory_item_id,
      component_id: item.component_id,
      quantity: item.quantity,
      unit: item.unit || '',
      wastage_percent: item.wastage_percent ?? 0,
      sort_order: item.sort_order ?? 0,
      notes: item.notes || '',
    })) : []);
  }

  function startEditPromo(row) {
    setBuilderTab('promos');
    setPromoEditId(row.id);
    setPromoForm({
      name: row.name || '',
      applies_to: row.applies_to || 'sku',
      sku_id: row.sku_id ? String(row.sku_id) : '',
      menu_item_id: row.menu_item_id ? String(row.menu_item_id) : '',
      promo_type: row.promo_type || 'percent_off',
      promo_value: String(row.promo_value ?? ''),
      min_qty: row.min_qty === null || typeof row.min_qty === 'undefined' ? '' : String(row.min_qty),
      start_date: row.start_date || '',
      end_date: row.end_date || '',
      is_active: !!row.is_active,
      notes: row.notes || '',
    });
  }

  const recentInbound = useMemo(() => {
    return movements.filter((row) => row.movement_type === 'in').slice(0, 8);
  }, [movements]);

  const recentSales = sales.slice(0, 8);

  if (loading) {
    return (
      <section className="section">
        <h1>Restaurant Operations</h1>
        <p className="muted">Loading operations workspace...</p>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="section ops-hero">
        <div className="row wrap" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Restaurant Operations</h1>
            <p className="muted">One screen for sales posting, automatic inventory deduction, restocking with accounting, and menu builders.</p>
          </div>
          <div className="row wrap">
            <span className="badge">Inventory-Linked Sales</span>
            <span className="badge">Accounting-Linked Restock</span>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="card-grid">
        <article className="card stat-card">
          <div className="muted small">Menu Items</div>
          <div className="kpi">{menuItems.length}</div>
          <div className="small muted">Across restaurant, breakfast, cafe, and bar</div>
        </article>
        <article className="card stat-card">
          <div className="muted small">SKUs</div>
          <div className="kpi">{skus.length}</div>
          <div className="small muted">Variant pricing and recipe definitions</div>
        </article>
        <article className="card stat-card">
          <div className="muted small">Active Promotions</div>
          <div className="kpi">{promotions.filter((row) => row.is_active).length}</div>
          <div className="small muted">Applied automatically on sale posting</div>
        </article>
        <article className="card stat-card">
          <div className="muted small">Low Stock Alerts</div>
          <div className="kpi">{lowStockItems.length}</div>
          <div className="small muted">Items at or below reorder level</div>
        </article>
      </section>

      <div className="grid">
        <section className="section">
          <h2>Quick Sale</h2>
          <p className="muted small">Post sale and deduct inventory FIFO. Optional accounting posting is available when needed.</p>

          <form onSubmit={submitSale} className="stack">
            <div className="form-grid">
              <label>
                Order No
                <input value={saleForm.order_no} onChange={(e) => setSaleForm((prev) => ({ ...prev, order_no: e.target.value }))} placeholder="Auto if blank" />
              </label>
              <label>
                Order Date
                <input type="date" value={saleForm.order_date} onChange={(e) => setSaleForm((prev) => ({ ...prev, order_date: e.target.value }))} />
              </label>
              <label>
                Payment Method
                <select value={saleForm.payment_method} onChange={(e) => setSaleForm((prev) => ({ ...prev, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map((row) => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>
                Channel
                <input value={saleForm.channel} onChange={(e) => setSaleForm((prev) => ({ ...prev, channel: e.target.value }))} placeholder="Dine-in, Grab, etc." />
              </label>
              <label>
                Counterparty
                <input value={saleForm.counterparty} onChange={(e) => setSaleForm((prev) => ({ ...prev, counterparty: e.target.value }))} placeholder="Optional customer name" />
              </label>
              <label>
                Strict Inventory
                <select value={String(saleForm.strict_inventory)} onChange={(e) => setSaleForm((prev) => ({ ...prev, strict_inventory: e.target.value === 'true' }))}>
                  <option value="true">true (recommended)</option>
                  <option value="false">false</option>
                </select>
              </label>
              <label>
                Auto Post Accounting
                <select value={String(saleForm.auto_post_accounting)} onChange={(e) => setSaleForm((prev) => ({ ...prev, auto_post_accounting: e.target.value === 'true' }))}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </label>
            </div>

            <label>
              Notes
              <textarea value={saleForm.notes} onChange={(e) => setSaleForm((prev) => ({ ...prev, notes: e.target.value }))} />
            </label>

            <div className="ops-line-builder">
              <div className="row wrap" style={{ justifyContent: 'space-between' }}>
                <h3>Sale Lines</h3>
                <span className="small muted">Net {currency(saleDraftTotals.net)}</span>
              </div>
              <div className="form-grid">
                <label>
                  Menu Item
                  <select value={saleLineDraft.menu_item_id} onChange={(e) => setSaleLineDraft((prev) => ({ ...prev, menu_item_id: e.target.value, sku_id: '' }))}>
                    <option value="">Select</option>
                    {menuItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  Variant (optional)
                  <select value={saleLineDraft.sku_id} disabled={!selectedMenuSkus.length} onChange={(e) => setSaleLineDraft((prev) => ({ ...prev, sku_id: e.target.value }))}>
                    <option value="">{selectedMenuSkus.length ? 'Use base menu recipe' : 'Choose a menu item first'}</option>
                    {selectedMenuSkus.map((row) => <option key={row.id} value={row.id}>{row.variant_name || row.sku_code || `Variant ${row.id}`}</option>)}
                  </select>
                </label>
                <label>
                  Quantity
                  <input type="number" step="0.01" min="0.01" value={saleLineDraft.quantity} onChange={(e) => setSaleLineDraft((prev) => ({ ...prev, quantity: e.target.value }))} />
                </label>
                <label>
                  Unit Price
                  <input type="number" step="0.01" min="0" value={saleLineDraft.unit_price} onChange={(e) => setSaleLineDraft((prev) => ({ ...prev, unit_price: e.target.value }))} placeholder="Auto from menu/SKU if blank" />
                </label>
                <label>
                  Discount Amount
                  <input type="number" step="0.01" min="0" value={saleLineDraft.discount_amount} onChange={(e) => setSaleLineDraft((prev) => ({ ...prev, discount_amount: e.target.value }))} />
                </label>
                <div className="align-end">
                  <button type="button" onClick={addSaleLine}>Add Line</button>
                </div>
              </div>

              <table className="table dense-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Variant</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Discount</th>
                    <th>Net</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {saleLines.map((line) => {
                    const menuItem = menuById[line.menu_item_id];
                    const sku = line.sku_id ? skus.find((row) => Number(row.id) === Number(line.sku_id)) : null;
                    const net = Math.max(num(line.quantity, 0) * num(line.unit_price, 0) - num(line.discount_amount, 0), 0);
                    return (
                      <tr key={line.key}>
                        <td>{menuItem?.name || `#${line.menu_item_id}`}</td>
                        <td>{sku ? (sku.variant_name || sku.sku_code || sku.id) : '-'}</td>
                        <td>{line.quantity}</td>
                        <td>{currency(line.unit_price)}</td>
                        <td>{currency(line.discount_amount)}</td>
                        <td>{currency(net)}</td>
                        <td>
                          <button
                            className="secondary"
                            type="button"
                            onClick={() => setSaleLines((prev) => prev.filter((row) => row.key !== line.key))}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {!saleLines.length && (
                    <tr>
                      <td colSpan="7" className="muted">No lines yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <button type="submit">Post Sale</button>
          </form>
        </section>

        <section className="section">
          <h2>Quick Restock</h2>
          <p className="muted small">Receive stock and optionally auto-log accounting expense in one post.</p>
          <form onSubmit={submitRestock} className="stack">
            <div className="form-grid">
              <label>
                Inventory Item
                <select value={restockForm.item_id} onChange={(e) => setRestockForm((prev) => ({ ...prev, item_id: e.target.value }))}>
                  <option value="">Select</option>
                  {inventoryItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                </select>
              </label>
              <label>
                Quantity
                <input type="number" step="0.01" min="0.01" value={restockForm.quantity} onChange={(e) => setRestockForm((prev) => ({ ...prev, quantity: e.target.value }))} />
              </label>
              <label>
                Total Item Cost
                <input type="number" step="0.01" min="0" value={restockForm.total_item_cost} onChange={(e) => setRestockForm((prev) => ({ ...prev, total_item_cost: e.target.value }))} />
              </label>
              <label>
                Delivery Cost
                <input type="number" step="0.01" min="0" value={restockForm.delivery_cost} onChange={(e) => setRestockForm((prev) => ({ ...prev, delivery_cost: e.target.value }))} />
              </label>
              <label>
                Other Cost
                <input type="number" step="0.01" min="0" value={restockForm.other_cost} onChange={(e) => setRestockForm((prev) => ({ ...prev, other_cost: e.target.value }))} />
              </label>
              <label>
                Derived Unit Cost
                <input type="number" step="0.01" min="0" value={restockForm.quantity ? ((num(restockForm.total_item_cost,0) + num(restockForm.delivery_cost,0) + num(restockForm.other_cost,0)) / num(restockForm.quantity,1)).toFixed(2) : '0.00'} readOnly />
              </label>
              <label>
                Reason
                <input value={restockForm.reason} onChange={(e) => setRestockForm((prev) => ({ ...prev, reason: e.target.value }))} />
              </label>
              <label>
                Reference
                <input value={restockForm.reference_no} onChange={(e) => setRestockForm((prev) => ({ ...prev, reference_no: e.target.value }))} />
              </label>
              <label>
                Date
                <input type="date" value={restockForm.movement_date} onChange={(e) => setRestockForm((prev) => ({ ...prev, movement_date: e.target.value }))} />
              </label>
              <label>
                Supplier
                <input value={restockForm.supplier} onChange={(e) => setRestockForm((prev) => ({ ...prev, supplier: e.target.value }))} />
              </label>
              <label>
                Expense Module
                <select value={restockForm.expense_module_slug} onChange={(e) => setRestockForm((prev) => ({ ...prev, expense_module_slug: e.target.value }))}>
                  {EXPENSE_MODULES.map((row) => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>
                Expense Payment
                <select value={restockForm.expense_payment_method} onChange={(e) => setRestockForm((prev) => ({ ...prev, expense_payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map((row) => <option key={row} value={row}>{row}</option>)}
                </select>
              </label>
              <label>
                Auto Log Expense
                <select value={String(restockForm.log_expense)} onChange={(e) => setRestockForm((prev) => ({ ...prev, log_expense: e.target.value === 'true' }))}>
                  <option value="false">false (manual-first)</option>
                  <option value="true">true</option>
                </select>
              </label>
              <label>
                Expense Counterparty
                <input value={restockForm.expense_counterparty} onChange={(e) => setRestockForm((prev) => ({ ...prev, expense_counterparty: e.target.value }))} placeholder="Defaults to supplier if blank" />
              </label>
            </div>

            <label>
              Restock Notes
              <textarea value={restockForm.notes} onChange={(e) => setRestockForm((prev) => ({ ...prev, notes: e.target.value }))} />
            </label>
            <label>
              Expense Notes
              <textarea value={restockForm.expense_notes} onChange={(e) => setRestockForm((prev) => ({ ...prev, expense_notes: e.target.value }))} />
            </label>

            <button type="submit">Post Restock</button>
          </form>

          {lowStockItems.length > 0 && (
            <div className="ops-alert-list">
              <h3>Low Stock</h3>
              <ul>
                {lowStockItems.slice(0, 6).map((row) => (
                  <li key={row.id}>
                    <span>{row.name}</span>
                    <span>{num(row.quantity_on_hand, 0)} {row.unit || ''} (reorder {num(row.reorder_level, 0)})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2>Catalog Builder</h2>
            <p className="muted small">Manage menu, prep components, SKUs, and promotions in one place.</p>
          </div>
          <div className="segmented">
            {BUILDER_TABS.map((tab) => (
              <button
                key={tab}
                className={builderTab === tab ? 'tab active' : 'tab'}
                type="button"
                onClick={() => setBuilderTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {builderTab === 'menu' && (
          <div className="stack">
            <form onSubmit={submitMenu}>
              <div className="form-grid">
                <label>
                  Name
                  <input required value={menuForm.name} onChange={(e) => setMenuForm((prev) => ({ ...prev, name: e.target.value }))} />
                </label>
                <label>
                  Module
                  <select value={menuForm.module_slug} onChange={(e) => setMenuForm((prev) => ({ ...prev, module_slug: e.target.value }))}>
                    {MODULE_OPTIONS.map((row) => <option key={row} value={row}>{row}</option>)}
                  </select>
                </label>
                <label>
                  Category
                  <input value={menuForm.category} onChange={(e) => setMenuForm((prev) => ({ ...prev, category: e.target.value }))} />
                </label>
                <label>
                  Base Price
                  <input type="number" step="0.01" min="0" value={menuForm.price} onChange={(e) => setMenuForm((prev) => ({ ...prev, price: e.target.value }))} />
                </label>
                <label>
                  Active
                  <select value={String(menuForm.is_active)} onChange={(e) => setMenuForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <label>
                Notes
                <textarea value={menuForm.notes} onChange={(e) => setMenuForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              <div className="row wrap">
                <button type="submit">{menuEditId ? 'Update Menu Item' : 'Create Menu Item'}</button>
                {menuEditId && <button className="secondary" type="button" onClick={resetMenuForm}>Cancel</button>}
              </div>
            </form>

            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Module</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>Active</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {menuItems.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.module_slug}</td>
                    <td>{row.category || '-'}</td>
                    <td>{currency(row.price)}</td>
                    <td>{String(!!row.is_active)}</td>
                    <td className="row wrap">
                      <button className="secondary" type="button" onClick={() => startEditMenu(row)}>Edit</button>
                      <button className="secondary" type="button" onClick={() => removeMenuItem(row.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
                {!menuItems.length && <tr><td colSpan="6" className="muted">No menu items yet.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        {builderTab === 'components' && (
          <div className="stack">
            <form onSubmit={submitComponent} className="stack">
              <div className="form-grid">
                <label>
                  Component Name
                  <input required value={componentForm.name} onChange={(e) => setComponentForm((prev) => ({ ...prev, name: e.target.value }))} />
                </label>
                <label>
                  Category
                  <input value={componentForm.category_name} onChange={(e) => setComponentForm((prev) => ({ ...prev, category_name: e.target.value }))} />
                </label>
                <label>
                  Yield Quantity
                  <input type="number" step="0.01" min="0.01" value={componentForm.yield_quantity} onChange={(e) => setComponentForm((prev) => ({ ...prev, yield_quantity: e.target.value }))} />
                </label>
                <label>
                  Yield Unit
                  <input value={componentForm.yield_unit} onChange={(e) => setComponentForm((prev) => ({ ...prev, yield_unit: e.target.value }))} />
                </label>
                <label>
                  Active
                  <select value={String(componentForm.is_active)} onChange={(e) => setComponentForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>

              <label>
                Notes
                <textarea value={componentForm.notes} onChange={(e) => setComponentForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>

              <div className="ops-line-builder">
                <div className="row wrap" style={{ justifyContent: 'space-between' }}>
                  <h3>Component Recipe Lines</h3>
                  <span className="small muted">{componentItems.length} lines</span>
                </div>
                <div className="form-grid">
                  <label>
                    Inventory Item
                    <select value={componentItemDraft.inventory_item_id} onChange={(e) => setComponentItemDraft((prev) => ({ ...prev, inventory_item_id: e.target.value }))}>
                      <option value="">Select</option>
                      {inventoryItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                    </select>
                  </label>
                  <label>
                    Quantity
                    <input type="number" step="0.01" min="0.0001" value={componentItemDraft.quantity} onChange={(e) => setComponentItemDraft((prev) => ({ ...prev, quantity: e.target.value }))} />
                  </label>
                  <label>
                    Unit
                    <input value={componentItemDraft.unit} onChange={(e) => setComponentItemDraft((prev) => ({ ...prev, unit: e.target.value }))} />
                  </label>
                  <label>
                    Wastage %
                    <input type="number" step="0.01" min="0" value={componentItemDraft.wastage_percent} onChange={(e) => setComponentItemDraft((prev) => ({ ...prev, wastage_percent: e.target.value }))} />
                  </label>
                  <label>
                    Sort Order
                    <input type="number" step="1" min="0" value={componentItemDraft.sort_order} onChange={(e) => setComponentItemDraft((prev) => ({ ...prev, sort_order: e.target.value }))} />
                  </label>
                  <div className="align-end">
                    <button type="button" onClick={addComponentDraftItem}>Add Line</button>
                  </div>
                </div>

                <table className="table dense-table">
                  <thead>
                    <tr>
                      <th>Inventory</th>
                      <th>Qty</th>
                      <th>Unit</th>
                      <th>Waste %</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {componentItems.map((line, index) => (
                      <tr key={`${line.inventory_item_id}-${index}`}>
                        <td>{inventoryById[line.inventory_item_id]?.name || `#${line.inventory_item_id}`}</td>
                        <td>{line.quantity}</td>
                        <td>{line.unit || '-'}</td>
                        <td>{line.wastage_percent}</td>
                        <td>
                          <button className="secondary" type="button" onClick={() => setComponentItems((prev) => prev.filter((_, rowIndex) => rowIndex !== index))}>Remove</button>
                        </td>
                      </tr>
                    ))}
                    {!componentItems.length && <tr><td colSpan="5" className="muted">No component lines yet.</td></tr>}
                  </tbody>
                </table>
              </div>

              <div className="row wrap">
                <button type="submit">{componentEditId ? 'Update Component' : 'Create Component'}</button>
                {componentEditId && <button className="secondary" type="button" onClick={resetComponentForm}>Cancel</button>}
              </div>
            </form>

            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Yield</th>
                  <th>Lines</th>
                  <th>Unit Cost</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {components.map((row) => {
                  const costing = componentCosting[row.id];
                  return (
                    <tr key={row.id}>
                      <td>{row.name}</td>
                      <td>{row.yield_quantity} {row.yield_unit || ''}</td>
                      <td>{Array.isArray(row.items) ? row.items.length : 0}</td>
                      <td>{costing ? currency(costing.unit_cost) : '-'}</td>
                      <td className="row wrap">
                        <button className="secondary" type="button" onClick={() => showComponentCosting(row.id)}>Costing</button>
                        <button className="secondary" type="button" onClick={() => startEditComponent(row)}>Edit</button>
                        <button className="secondary" type="button" onClick={() => removeComponent(row.id)}>Delete</button>
                      </td>
                    </tr>
                  );
                })}
                {!components.length && <tr><td colSpan="5" className="muted">No components yet.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        {builderTab === 'skus' && (
          <div className="stack">
            <form onSubmit={submitSku} className="stack">
              <div className="form-grid">
                <label>
                  Menu Item
                  <select required value={skuForm.menu_item_id} onChange={(e) => setSkuForm((prev) => ({ ...prev, menu_item_id: e.target.value }))}>
                    <option value="">Select</option>
                    {menuItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  SKU Code
                  <input value={skuForm.sku_code} onChange={(e) => setSkuForm((prev) => ({ ...prev, sku_code: e.target.value }))} />
                </label>
                <label>
                  Variant Name
                  <input required value={skuForm.variant_name} onChange={(e) => setSkuForm((prev) => ({ ...prev, variant_name: e.target.value }))} />
                </label>
                <label>
                  Size Label
                  <input value={skuForm.size_label} onChange={(e) => setSkuForm((prev) => ({ ...prev, size_label: e.target.value }))} />
                </label>
                <label>
                  Price
                  <input type="number" step="0.01" min="0" value={skuForm.price} onChange={(e) => setSkuForm((prev) => ({ ...prev, price: e.target.value }))} />
                </label>
                <label>
                  Packaging Cost
                  <input type="number" step="0.01" min="0" value={skuForm.packaging_cost} onChange={(e) => setSkuForm((prev) => ({ ...prev, packaging_cost: e.target.value }))} />
                </label>
                <label>
                  Labor Cost
                  <input type="number" step="0.01" min="0" value={skuForm.labor_cost} onChange={(e) => setSkuForm((prev) => ({ ...prev, labor_cost: e.target.value }))} />
                </label>
                <label>
                  Overhead Cost
                  <input type="number" step="0.01" min="0" value={skuForm.overhead_cost} onChange={(e) => setSkuForm((prev) => ({ ...prev, overhead_cost: e.target.value }))} />
                </label>
                <label>
                  Active
                  <select value={String(skuForm.is_active)} onChange={(e) => setSkuForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>

              <label>
                Notes
                <textarea value={skuForm.notes} onChange={(e) => setSkuForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>

              <div className="ops-line-builder">
                <div className="row wrap" style={{ justifyContent: 'space-between' }}>
                  <h3>SKU Recipe Lines</h3>
                  <span className="small muted">{skuRecipeItems.length} lines</span>
                </div>
                <div className="form-grid">
                  <label>
                    Line Type
                    <select value={skuRecipeDraft.line_type} onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, line_type: e.target.value }))}>
                      <option value="inventory">inventory</option>
                      <option value="component">component</option>
                    </select>
                  </label>
                  <label>
                    Inventory Item
                    <select
                      value={skuRecipeDraft.inventory_item_id}
                      onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, inventory_item_id: e.target.value }))}
                      disabled={skuRecipeDraft.line_type === 'component'}
                    >
                      <option value="">Select</option>
                      {inventoryItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                    </select>
                  </label>
                  <label>
                    Component
                    <select
                      value={skuRecipeDraft.component_id}
                      onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, component_id: e.target.value }))}
                      disabled={skuRecipeDraft.line_type !== 'component'}
                    >
                      <option value="">Select</option>
                      {components.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                    </select>
                  </label>
                  <label>
                    Quantity
                    <input type="number" step="0.01" min="0.0001" value={skuRecipeDraft.quantity} onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, quantity: e.target.value }))} />
                  </label>
                  <label>
                    Unit
                    <input value={skuRecipeDraft.unit} onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, unit: e.target.value }))} />
                  </label>
                  <label>
                    Waste %
                    <input type="number" step="0.01" min="0" value={skuRecipeDraft.wastage_percent} onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, wastage_percent: e.target.value }))} />
                  </label>
                  <label>
                    Sort Order
                    <input type="number" step="1" min="0" value={skuRecipeDraft.sort_order} onChange={(e) => setSkuRecipeDraft((prev) => ({ ...prev, sort_order: e.target.value }))} />
                  </label>
                  <div className="align-end">
                    <button type="button" onClick={addSkuRecipeLine}>Add Line</button>
                  </div>
                </div>

                <table className="table dense-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Reference</th>
                      <th>Qty</th>
                      <th>Unit</th>
                      <th>Waste %</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {skuRecipeItems.map((line, index) => (
                      <tr key={`${line.line_type}-${index}`}>
                        <td>{line.line_type}</td>
                        <td>
                          {line.line_type === 'component'
                            ? (components.find((row) => Number(row.id) === Number(line.component_id))?.name || `#${line.component_id}`)
                            : (inventoryById[line.inventory_item_id]?.name || `#${line.inventory_item_id}`)}
                        </td>
                        <td>{line.quantity}</td>
                        <td>{line.unit || '-'}</td>
                        <td>{line.wastage_percent}</td>
                        <td>
                          <button className="secondary" type="button" onClick={() => setSkuRecipeItems((prev) => prev.filter((_, rowIndex) => rowIndex !== index))}>Remove</button>
                        </td>
                      </tr>
                    ))}
                    {!skuRecipeItems.length && <tr><td colSpan="6" className="muted">No SKU recipe lines yet.</td></tr>}
                  </tbody>
                </table>
              </div>

              <div className="row wrap">
                <button type="submit">{skuEditId ? 'Update SKU' : 'Create SKU'}</button>
                {skuEditId && <button className="secondary" type="button" onClick={resetSkuForm}>Cancel</button>}
              </div>
            </form>

            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Menu Item</th>
                  <th>Variant</th>
                  <th>Price</th>
                  <th>Recipe Lines</th>
                  <th>Total Cost</th>
                  <th>Margin %</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {skus.map((row) => {
                  const costing = skuCosting[row.id];
                  return (
                    <tr key={row.id}>
                      <td>{menuById[row.menu_item_id]?.name || `#${row.menu_item_id}`}</td>
                      <td>{row.variant_name || row.sku_code || row.id}</td>
                      <td>{currency(row.price)}</td>
                      <td>{Array.isArray(row.recipe_items) ? row.recipe_items.length : 0}</td>
                      <td>{costing ? currency(costing.total_cost) : '-'}</td>
                      <td>{costing?.margin_percent ?? '-'}</td>
                      <td className="row wrap">
                        <button className="secondary" type="button" onClick={() => showSkuCosting(row.id)}>Costing</button>
                        <button className="secondary" type="button" onClick={() => startEditSku(row)}>Edit</button>
                        <button className="secondary" type="button" onClick={() => removeSku(row.id)}>Delete</button>
                      </td>
                    </tr>
                  );
                })}
                {!skus.length && <tr><td colSpan="7" className="muted">No SKUs yet.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        {builderTab === 'promos' && (
          <div className="stack">
            <form onSubmit={submitPromotion}>
              <div className="form-grid">
                <label>
                  Name
                  <input required value={promoForm.name} onChange={(e) => setPromoForm((prev) => ({ ...prev, name: e.target.value }))} />
                </label>
                <label>
                  Applies To
                  <select value={promoForm.applies_to} onChange={(e) => setPromoForm((prev) => ({ ...prev, applies_to: e.target.value }))}>
                    <option value="sku">sku</option>
                    <option value="menu_item">menu_item</option>
                  </select>
                </label>
                <label>
                  Menu Item
                  <select value={promoForm.menu_item_id} onChange={(e) => setPromoForm((prev) => ({ ...prev, menu_item_id: e.target.value }))}>
                    <option value="">Optional</option>
                    {menuItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  SKU
                  <select value={promoForm.sku_id} onChange={(e) => setPromoForm((prev) => ({ ...prev, sku_id: e.target.value }))} disabled={promoForm.applies_to !== 'sku'}>
                    <option value="">Select SKU</option>
                    {skuFilteredForPromo.map((row) => <option key={row.id} value={row.id}>{row.variant_name || row.sku_code || row.id}</option>)}
                  </select>
                </label>
                <label>
                  Promo Type
                  <select value={promoForm.promo_type} onChange={(e) => setPromoForm((prev) => ({ ...prev, promo_type: e.target.value }))}>
                    {PROMO_TYPES.map((row) => <option key={row} value={row}>{row}</option>)}
                  </select>
                </label>
                <label>
                  Promo Value
                  <input type="number" step="0.01" min="0" value={promoForm.promo_value} onChange={(e) => setPromoForm((prev) => ({ ...prev, promo_value: e.target.value }))} />
                </label>
                <label>
                  Min Qty
                  <input type="number" step="0.01" min="0" value={promoForm.min_qty} onChange={(e) => setPromoForm((prev) => ({ ...prev, min_qty: e.target.value }))} />
                </label>
                <label>
                  Start Date
                  <input type="date" value={promoForm.start_date} onChange={(e) => setPromoForm((prev) => ({ ...prev, start_date: e.target.value }))} />
                </label>
                <label>
                  End Date
                  <input type="date" value={promoForm.end_date} onChange={(e) => setPromoForm((prev) => ({ ...prev, end_date: e.target.value }))} />
                </label>
                <label>
                  Active
                  <select value={String(promoForm.is_active)} onChange={(e) => setPromoForm((prev) => ({ ...prev, is_active: e.target.value === 'true' }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <label>
                Notes
                <textarea value={promoForm.notes} onChange={(e) => setPromoForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              <div className="row wrap">
                <button type="submit">{promoEditId ? 'Update Promotion' : 'Create Promotion'}</button>
                {promoEditId && <button className="secondary" type="button" onClick={resetPromoForm}>Cancel</button>}
              </div>
            </form>

            <table className="table dense-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Target</th>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Date Range</th>
                  <th>Active</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {promotions.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>
                      {row.applies_to === 'sku'
                        ? (skus.find((skuRow) => Number(skuRow.id) === Number(row.sku_id))?.variant_name || `SKU ${row.sku_id}`)
                        : (menuById[row.menu_item_id]?.name || `Menu ${row.menu_item_id}`)}
                    </td>
                    <td>{row.promo_type}</td>
                    <td>{row.promo_value}</td>
                    <td>{shortDate(row.start_date)} to {shortDate(row.end_date)}</td>
                    <td>{String(!!row.is_active)}</td>
                    <td className="row wrap">
                      <button className="secondary" type="button" onClick={() => startEditPromo(row)}>Edit</button>
                      <button className="secondary" type="button" onClick={() => removePromotion(row.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
                {!promotions.length && <tr><td colSpan="7" className="muted">No promotions yet.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="grid">
        <div className="section">
          <h2>Recent Sales</h2>
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Date</th>
                <th>Status</th>
                <th>Lines</th>
                <th>Net</th>
                <th>COGS</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {recentSales.map((row) => (
                <tr key={row.id}>
                  <td>{row.order_no}</td>
                  <td>{shortDate(row.order_date)}</td>
                  <td>{row.status}</td>
                  <td>{row.line_count}</td>
                  <td>{currency(row.net_amount)}</td>
                  <td>{currency(row.cogs_amount)}</td>
                  <td>
                    {String(row.status || '').toLowerCase() !== 'voided' ? (
                      <button className="secondary" type="button" onClick={() => handleVoidSale(row)}>Void</button>
                    ) : (
                      <span className="small muted">Voided</span>
                    )}
                  </td>
                </tr>
              ))}
              {!recentSales.length && <tr><td colSpan="7" className="muted">No sales posted yet.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="section">
          <h2>Recent Restocks</h2>
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Ref</th>
                <th>Item</th>
                <th>Qty</th>
                <th>Total Cost</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {recentInbound.map((row) => (
                <tr key={row.id}>
                  <td>{row.reference_no || row.id}</td>
                  <td>{inventoryById[row.item_id]?.name || `#${row.item_id}`}</td>
                  <td>{row.quantity}</td>
                  <td>{currency(row.total_cost)}</td>
                  <td>{shortDate(row.movement_date)}</td>
                </tr>
              ))}
              {!recentInbound.length && <tr><td colSpan="5" className="muted">No restock movements yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
