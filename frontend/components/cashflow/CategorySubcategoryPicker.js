import { useMemo } from 'react';

export default function CategorySubcategoryPicker({
  taxonomy = {},
  category = '',
  subcategory = '',
  level3Item = '',
  onCategoryChange,
  onSubcategoryChange,
  onLevel3ItemChange,
}) {
  const categories = useMemo(() => Object.keys(taxonomy || {}), [taxonomy]);
  const subcategories = useMemo(() => Object.keys((taxonomy || {})[category] || {}), [taxonomy, category]);
  const level3 = useMemo(() => ((taxonomy || {})[category]?.[subcategory] || []), [taxonomy, category, subcategory]);

  return (
    <>
      <label>
        Category
        <select value={category} onChange={(e) => onCategoryChange?.(e.target.value)}>
          <option value="">Select</option>
          {categories.map((row) => <option key={row} value={row}>{row}</option>)}
        </select>
      </label>
      <label>
        Subcategory
        <select value={subcategory} onChange={(e) => onSubcategoryChange?.(e.target.value)} disabled={!category}>
          <option value="">Select</option>
          {subcategories.map((row) => <option key={row} value={row}>{row}</option>)}
        </select>
      </label>
      <label>
        Detail
        <select value={level3Item} onChange={(e) => onLevel3ItemChange?.(e.target.value)} disabled={!subcategory}>
          <option value="">Select</option>
          {level3.map((row) => <option key={row} value={row}>{row}</option>)}
        </select>
      </label>
    </>
  );
}
