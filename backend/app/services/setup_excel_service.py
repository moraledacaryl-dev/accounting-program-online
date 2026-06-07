from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from app.models.entities import (
    InventoryItem,
    MasterValue,
    MenuItem,
    MenuSKU,
    MenuSKURecipeItem,
    PrepComponent,
    PrepComponentItem,
    RecipeLine,
)

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

DATA_SHEETS = [
    'Units',
    'Inventory Categories',
    'Inventory Items',
    'Menu Categories',
    'Menu Items',
    'Menu Item Recipes',
    'Prep Components',
    'Component Lines',
    'Menu SKUs',
    'SKU Recipe Lines',
]


def _norm(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip())


def _key(value: Any) -> str:
    return _norm(value).casefold()


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == '':
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '')
    if not text:
        return default
    return float(text)


def _to_int(value: Any, default: int = 0) -> int:
    return int(round(_to_float(value, default)))


def _to_bool(value: Any, default: bool = True) -> bool:
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {'1', 'true', 'yes', 'y', 'active', 'enabled'}:
        return True
    if text in {'0', 'false', 'no', 'n', 'inactive', 'disabled'}:
        return False
    return default


def _cell_ref(row_idx: int, col_idx: int) -> str:
    letters = ''
    n = col_idx
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f'{letters}{row_idx}'


def _sheet_xml(rows: list[list[Any]]) -> str:
    max_columns = max((len(row) for row in rows), default=1)
    last_column = ''.join(ch for ch in _cell_ref(1, max_columns) if ch.isalpha())
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    out.append('<cols>')
    for idx in range(1, max_columns + 1):
        width = min(max(max((len(str(row[idx - 1])) for row in rows if idx <= len(row)), default=10) + 2, 12), 42)
        out.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')
    out.append('</cols>')
    out.append('<sheetData>')
    for r_idx, row in enumerate(rows, start=1):
        out.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row, start=1):
            if value is None:
                continue
            ref = _cell_ref(r_idx, c_idx)
            style = ' s="1"' if r_idx == 1 else ''
            if isinstance(value, bool):
                value = 'TRUE' if value else 'FALSE'
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
            else:
                out.append(f'<c r="{ref}"{style} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        out.append('</row>')
    out.append('</sheetData>')
    if rows:
        out.append(f'<autoFilter ref="A1:{last_column}{max(len(rows), 1)}"/>')
    out.append('</worksheet>')
    return ''.join(out)


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = ''.join(
        f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheets}</sheets></workbook>'
    )


def _workbook_rels(sheet_names: list[str]) -> str:
    rels = ''.join(
        '<Relationship '
        f'Id="rId{idx}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{idx}.xml"/>'
        for idx, _ in enumerate(sheet_names, start=1)
    )
    rels += (
        '<Relationship Id="rIdStyles" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rels}</Relationships>'
    )


def _content_types(sheet_names: list[str]) -> str:
    overrides = ''.join(
        '<Override '
        f'PartName="/xl/worksheets/sheet{idx}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx, _ in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f'{overrides}</Types>'
    )


def _minimal_styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F6A47"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>'
        '</styleSheet>'
    )


def _build_xlsx(sheets: dict[str, list[list[Any]]]) -> bytes:
    buf = io.BytesIO()
    sheet_names = list(sheets.keys())
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', _content_types(sheet_names))
        zf.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'
        ))
        zf.writestr('docProps/core.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:creator>Hidden Oasis Accounting</dc:creator>'
            '<dc:title>Accounting setup import template</dc:title>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
            '</cp:coreProperties>'
        ))
        zf.writestr('docProps/app.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Hidden Oasis Accounting</Application></Properties>'
        ))
        zf.writestr('xl/workbook.xml', _workbook_xml(sheet_names))
        zf.writestr('xl/_rels/workbook.xml.rels', _workbook_rels(sheet_names))
        zf.writestr('xl/styles.xml', _minimal_styles_xml())
        for idx, (_, rows) in enumerate(sheets.items(), start=1):
            zf.writestr(f'xl/worksheets/sheet{idx}.xml', _sheet_xml(rows))
    return buf.getvalue()


def build_setup_import_template(scope: str = 'all') -> bytes:
    sheets = {
        'Instructions': [
            ['Accounting Inventory/Menu Setup Import'],
            ['Use the data tabs to create or update setup data. Leave unused tabs blank.'],
            ['Import is idempotent by names/codes: existing inventory items, menu items, components, and SKUs are updated instead of duplicated.'],
            ['Recipe units are controlled by setup: inventory recipe lines use the inventory item unit; component recipe lines use the component yield unit. If workbook unit differs, Accounting uses the controlled unit and reports a warning.'],
            ['For a full recipe refresh, keep "Replace recipe lines for items included in file" enabled on upload. That prevents duplicate ingredients when re-importing.'],
            ['Do not delete or rename these sheet names.'],
        ],
        'Examples': [
            ['Sheet', 'Example fields', 'Example value'],
            ['Units', 'unit', 'kg'],
            ['Inventory Categories', 'type/category/subcategory/code', 'category / Raw Materials / blank / INV_RAW'],
            ['Inventory Items', 'name/category/subcategory/unit/reorder_level', 'Chicken Breast / Raw Materials / Protein / kg / 5'],
            ['Menu Categories', 'module_slug/category/code', 'cafe / Coffee / CAFE_COFFEE'],
            ['Menu Items', 'name/module_slug/category/price', 'Iced Latte / cafe / Coffee / 150'],
            ['Menu Item Recipes', 'menu_item_name/ingredient_name/quantity', 'Iced Latte / Milk / 0.2'],
            ['Prep Components', 'name/yield_quantity/yield_unit', 'House Syrup / 1 / L'],
            ['Component Lines', 'component_name/ingredient_name/quantity', 'House Syrup / Sugar / 1'],
            ['Menu SKUs', 'menu_item_name/sku_code/variant_name/price', 'Iced Latte / LATTE-16OZ / 16 oz / 150'],
            ['SKU Recipe Lines', 'sku_code/line_type/ingredient_name/component_name/quantity', 'LATTE-16OZ / inventory / Milk / blank / 0.2'],
        ],
        'Units': [['unit', 'code', 'is_active', 'notes']],
        'Inventory Categories': [['type', 'category', 'subcategory', 'code', 'is_active', 'notes']],
        'Inventory Items': [['name', 'module_name', 'category_name', 'subcategory_name', 'unit', 'quantity_on_hand', 'reorder_level', 'average_cost', 'notes']],
        'Menu Categories': [['module_slug', 'category', 'code', 'is_active', 'notes']],
        'Menu Items': [['name', 'module_slug', 'category', 'price', 'is_active', 'notes']],
        'Menu Item Recipes': [['menu_item_name', 'ingredient_name', 'quantity', 'unit', 'notes']],
        'Prep Components': [['name', 'category_name', 'yield_quantity', 'yield_unit', 'is_active', 'notes']],
        'Component Lines': [['component_name', 'ingredient_name', 'quantity', 'unit', 'wastage_percent', 'sort_order', 'notes']],
        'Menu SKUs': [['menu_item_name', 'sku_code', 'variant_name', 'size_label', 'price', 'packaging_cost', 'labor_cost', 'overhead_cost', 'is_active', 'notes']],
        'SKU Recipe Lines': [['sku_code', 'menu_item_name', 'variant_name', 'line_type', 'ingredient_name', 'component_name', 'quantity', 'unit', 'wastage_percent', 'sort_order', 'notes']],
    }
    if scope == 'menu':
        menu_sheets = {'Instructions', 'Examples', 'Menu Categories', 'Menu Items', 'Menu Item Recipes', 'Prep Components', 'Component Lines', 'Menu SKUs', 'SKU Recipe Lines'}
        sheets = {name: rows for name, rows in sheets.items() if name in menu_sheets}
    return _build_xlsx(sheets)


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        raw = zf.read('xl/sharedStrings.xml')
    except KeyError:
        return []
    root = ET.fromstring(raw)
    ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    values: list[str] = []
    for si in root.findall('x:si', ns):
        parts = [node.text or '' for node in si.findall('.//x:t', ns)]
        values.append(''.join(parts))
    return values


def _column_index(cell_ref: str) -> int:
    letters = ''.join(ch for ch in cell_ref if ch.isalpha()).upper()
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - 64)
    return max(value, 1)


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    cell_type = cell.attrib.get('t')
    if cell_type == 'inlineStr':
        return ''.join(node.text or '' for node in cell.findall('.//x:t', ns))
    value = cell.find('x:v', ns)
    text = value.text if value is not None and value.text is not None else ''
    if cell_type == 's':
        try:
            return shared_strings[int(text)]
        except Exception:
            return ''
    if cell_type == 'b':
        return 'TRUE' if text == '1' else 'FALSE'
    return text


def _read_xlsx_sheets(content: bytes) -> dict[str, list[dict[str, str]]]:
    rows_by_sheet: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
        shared_strings = _read_shared_strings(zf)
        wb = ET.fromstring(zf.read('xl/workbook.xml'))
        rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
        wb_ns = {
            'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        }
        rel_ns = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        rel_targets = {
            rel.attrib.get('Id'): rel.attrib.get('Target', '')
            for rel in rels.findall('rel:Relationship', rel_ns)
        }
        for sheet in wb.findall('x:sheets/x:sheet', wb_ns):
            name = sheet.attrib.get('name') or ''
            rel_id = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = rel_targets.get(rel_id or '')
            if not name or not target:
                continue
            path = f'xl/{target}' if not target.startswith('/') else target.lstrip('/')
            root = ET.fromstring(zf.read(path))
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            matrix: list[list[str]] = []
            for row in root.findall('x:sheetData/x:row', ns):
                values: list[str] = []
                for cell in row.findall('x:c', ns):
                    idx = _column_index(cell.attrib.get('r', 'A1'))
                    while len(values) < idx:
                        values.append('')
                    values[idx - 1] = _cell_text(cell, shared_strings)
                matrix.append(values)
            if not matrix:
                rows_by_sheet[name] = []
                continue
            headers = [_key(value).replace(' ', '_') for value in matrix[0]]
            data_rows: list[dict[str, str]] = []
            for raw in matrix[1:]:
                row = {headers[idx]: _norm(raw[idx]) if idx < len(raw) else '' for idx in range(len(headers)) if headers[idx]}
                if any(value for value in row.values()):
                    data_rows.append(row)
            rows_by_sheet[name] = data_rows
    return rows_by_sheet


@dataclass
class ImportResult:
    dry_run: bool
    counts: dict[str, int] = field(default_factory=lambda: {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'warnings': 0,
        'errors': 0,
    })
    rows: list[dict[str, Any]] = field(default_factory=list)

    def add(self, sheet: str, row_number: int, action: str, message: str, detail: dict[str, Any] | None = None):
        self.rows.append({'sheet': sheet, 'row': row_number, 'action': action, 'message': message, 'detail': detail or {}})
        if action in self.counts:
            self.counts[action] += 1
        elif action == 'warning':
            self.counts['warnings'] += 1

    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.counts['errors'] == 0, 'dry_run': self.dry_run, 'counts': self.counts, 'rows': self.rows}


class SetupWorkbookImporter:
    def __init__(self, db: Session, dry_run: bool = False, replace_recipe_lines: bool = True):
        self.db = db
        self.result = ImportResult(dry_run=dry_run)
        self.replace_recipe_lines = replace_recipe_lines
        self._cleared_menu_recipes: set[int] = set()
        self._cleared_component_lines: set[int] = set()
        self._cleared_sku_recipes: set[int] = set()

    def import_content(self, content: bytes) -> dict[str, Any]:
        sheets = _read_xlsx_sheets(content)
        self._import_units(sheets.get('Units', []))
        self._import_inventory_categories(sheets.get('Inventory Categories', []))
        self._import_inventory_items(sheets.get('Inventory Items', []))
        self._import_menu_categories(sheets.get('Menu Categories', []))
        self._import_menu_items(sheets.get('Menu Items', []))
        self._import_menu_item_recipes(sheets.get('Menu Item Recipes', []))
        self._import_components(sheets.get('Prep Components', []))
        self._import_component_lines(sheets.get('Component Lines', []))
        self._import_skus(sheets.get('Menu SKUs', []))
        self._import_sku_recipe_lines(sheets.get('SKU Recipe Lines', []))
        self.db.flush()
        return self.result.as_dict()

    def _row_error(self, sheet: str, row_idx: int, message: str):
        self.result.add(sheet, row_idx, 'errors', message)

    def _row_skip(self, sheet: str, row_idx: int, message: str):
        self.result.add(sheet, row_idx, 'skipped', message)

    def _get_master_value(self, group_name: str, value: str) -> MasterValue | None:
        target = _key(value)
        for row in self.db.query(MasterValue).filter(MasterValue.group_name == group_name).all():
            if _key(row.value) == target:
                return row
        return None

    def _upsert_master_value(self, group_name: str, value: str, code: str = '', is_active: bool = True) -> MasterValue | None:
        value = _norm(value)
        if not value:
            return None
        row = self._get_master_value(group_name, value)
        if row:
            row.code = _norm(code) or row.code
            row.is_active = is_active
            self.db.add(row)
            return row
        row = MasterValue(group_name=group_name, value=value, code=_norm(code) or None, is_active=is_active)
        self.db.add(row)
        self.db.flush()
        return row

    def _inventory_by_name(self, name: str) -> InventoryItem | None:
        target = _key(name)
        for row in self.db.query(InventoryItem).all():
            if _key(row.name) == target:
                return row
        return None

    def _menu_by_name(self, name: str) -> MenuItem | None:
        target = _key(name)
        for row in self.db.query(MenuItem).all():
            if _key(row.name) == target:
                return row
        return None

    def _component_by_name(self, name: str) -> PrepComponent | None:
        target = _key(name)
        for row in self.db.query(PrepComponent).all():
            if _key(row.name) == target:
                return row
        return None

    def _sku_by_row(self, row: dict[str, str]) -> MenuSKU | None:
        sku_code = _norm(row.get('sku_code'))
        if sku_code:
            target = _key(sku_code)
            for sku in self.db.query(MenuSKU).all():
                if _key(sku.sku_code) == target:
                    return sku
        menu = self._menu_by_name(row.get('menu_item_name') or '')
        if not menu:
            return None
        variant = _key(row.get('variant_name'))
        size = _key(row.get('size_label'))
        for sku in self.db.query(MenuSKU).filter(MenuSKU.menu_item_id == menu.id).all():
            if _key(sku.variant_name) == variant and _key(sku.size_label) == size:
                return sku
        return None

    def _import_units(self, rows: list[dict[str, str]]):
        sheet = 'Units'
        for idx, row in enumerate(rows, start=2):
            unit = _norm(row.get('unit'))
            if not unit:
                self._row_skip(sheet, idx, 'Unit is blank.')
                continue
            existing = self._get_master_value('units_of_measure', unit)
            self._upsert_master_value('units_of_measure', unit, row.get('code') or '', _to_bool(row.get('is_active'), True))
            self.result.add(sheet, idx, 'updated' if existing else 'created', f'Unit {unit} {"updated" if existing else "created"}.')

    def _import_inventory_categories(self, rows: list[dict[str, str]]):
        sheet = 'Inventory Categories'
        for idx, row in enumerate(rows, start=2):
            kind = _key(row.get('type') or 'category')
            is_active = _to_bool(row.get('is_active'), True)
            if kind.startswith('sub'):
                value = row.get('subcategory') or row.get('category')
                group = 'inventory_subcategories'
            else:
                value = row.get('category')
                group = 'inventory_categories'
            value = _norm(value)
            if not value:
                self._row_skip(sheet, idx, 'Category/subcategory is blank.')
                continue
            existing = self._get_master_value(group, value)
            self._upsert_master_value(group, value, row.get('code') or '', is_active)
            self.result.add(sheet, idx, 'updated' if existing else 'created', f'{value} {"updated" if existing else "created"}.')

    def _import_inventory_items(self, rows: list[dict[str, str]]):
        sheet = 'Inventory Items'
        for idx, row in enumerate(rows, start=2):
            name = _norm(row.get('name'))
            if not name:
                self._row_skip(sheet, idx, 'Inventory item name is blank.')
                continue
            unit = _norm(row.get('unit'))
            existing = self._inventory_by_name(name)
            if not existing and not unit:
                self._row_error(sheet, idx, f'Inventory item {name} needs a unit.')
                continue
            if unit:
                self._upsert_master_value('units_of_measure', unit)
            if row.get('category_name'):
                self._upsert_master_value('inventory_categories', row.get('category_name') or '')
            if row.get('subcategory_name'):
                self._upsert_master_value('inventory_subcategories', row.get('subcategory_name') or '')
            data = {
                'name': name,
                'module_name': _norm(row.get('module_name')) or 'Inventory',
                'category_name': _norm(row.get('category_name')),
                'subcategory_name': _norm(row.get('subcategory_name')),
                'unit': unit or (existing.unit if existing else ''),
                'reorder_level': _to_float(row.get('reorder_level'), existing.reorder_level if existing else 0),
                'notes': _norm(row.get('notes')) or None,
            }
            if row.get('quantity_on_hand') != '':
                data['quantity_on_hand'] = _to_float(row.get('quantity_on_hand'), existing.quantity_on_hand if existing else 0)
            if row.get('average_cost') != '':
                data['average_cost'] = _to_float(row.get('average_cost'), existing.average_cost if existing else 0)
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'Inventory item {name} updated.')
            else:
                self.db.add(InventoryItem(**data))
                self.result.add(sheet, idx, 'created', f'Inventory item {name} created.')
            self.db.flush()

    def _import_menu_categories(self, rows: list[dict[str, str]]):
        sheet = 'Menu Categories'
        for idx, row in enumerate(rows, start=2):
            module = _norm(row.get('module_slug')) or 'restaurant'
            category = _norm(row.get('category'))
            if not category:
                self._row_skip(sheet, idx, 'Menu category is blank.')
                continue
            group = f'{module}_categories'
            existing = self._get_master_value(group, category)
            self._upsert_master_value(group, category, row.get('code') or '', _to_bool(row.get('is_active'), True))
            self.result.add(sheet, idx, 'updated' if existing else 'created', f'{module} category {category} {"updated" if existing else "created"}.')

    def _import_menu_items(self, rows: list[dict[str, str]]):
        sheet = 'Menu Items'
        for idx, row in enumerate(rows, start=2):
            name = _norm(row.get('name'))
            if not name:
                self._row_skip(sheet, idx, 'Menu item name is blank.')
                continue
            module = _norm(row.get('module_slug')) or 'restaurant'
            category = _norm(row.get('category'))
            if category:
                self._upsert_master_value(f'{module}_categories', category)
            existing = self._menu_by_name(name)
            data = {
                'name': name,
                'module_slug': module,
                'category': category,
                'price': _to_float(row.get('price'), existing.price if existing else 0),
                'is_active': _to_bool(row.get('is_active'), existing.is_active if existing else True),
                'notes': _norm(row.get('notes')) or None,
            }
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'Menu item {name} updated.')
            else:
                self.db.add(MenuItem(**data))
                self.result.add(sheet, idx, 'created', f'Menu item {name} created.')
            self.db.flush()

    def _import_menu_item_recipes(self, rows: list[dict[str, str]]):
        sheet = 'Menu Item Recipes'
        for idx, row in enumerate(rows, start=2):
            menu = self._menu_by_name(row.get('menu_item_name') or '')
            inv = self._inventory_by_name(row.get('ingredient_name') or '')
            if not menu:
                self._row_error(sheet, idx, f"Menu item not found: {row.get('menu_item_name') or ''}")
                continue
            if not inv:
                self._row_error(sheet, idx, f"Inventory item not found: {row.get('ingredient_name') or ''}")
                continue
            qty = _to_float(row.get('quantity'), 0)
            if qty <= 0:
                self._row_error(sheet, idx, 'Recipe quantity must be greater than zero.')
                continue
            if self.replace_recipe_lines and menu.id not in self._cleared_menu_recipes:
                self.db.query(RecipeLine).filter(RecipeLine.menu_item_id == menu.id).delete(synchronize_session=False)
                self._cleared_menu_recipes.add(menu.id)
            unit = inv.unit or ''
            if _norm(row.get('unit')) and _key(row.get('unit')) != _key(unit):
                self.result.add(sheet, idx, 'warning', f'Unit overridden to inventory item unit: {unit or "blank"}.')
            existing = None if self.replace_recipe_lines else self.db.query(RecipeLine).filter(RecipeLine.menu_item_id == menu.id, RecipeLine.inventory_item_id == inv.id).first()
            if existing:
                existing.quantity = qty
                existing.unit = unit
                existing.notes = _norm(row.get('notes')) or None
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'Recipe line updated for {menu.name} / {inv.name}.')
            else:
                self.db.add(RecipeLine(menu_item_id=menu.id, inventory_item_id=inv.id, quantity=qty, unit=unit, notes=_norm(row.get('notes')) or None))
                self.result.add(sheet, idx, 'created', f'Recipe line created for {menu.name} / {inv.name}.')

    def _import_components(self, rows: list[dict[str, str]]):
        sheet = 'Prep Components'
        for idx, row in enumerate(rows, start=2):
            name = _norm(row.get('name'))
            if not name:
                self._row_skip(sheet, idx, 'Component name is blank.')
                continue
            yield_qty = _to_float(row.get('yield_quantity'), 1)
            if yield_qty <= 0:
                self._row_error(sheet, idx, f'Component {name} yield quantity must be greater than zero.')
                continue
            existing = self._component_by_name(name)
            data = {
                'name': name,
                'category_name': _norm(row.get('category_name')),
                'yield_quantity': yield_qty,
                'yield_unit': _norm(row.get('yield_unit')),
                'is_active': _to_bool(row.get('is_active'), existing.is_active if existing else True),
                'notes': _norm(row.get('notes')) or None,
            }
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'Component {name} updated.')
            else:
                self.db.add(PrepComponent(**data))
                self.result.add(sheet, idx, 'created', f'Component {name} created.')
            self.db.flush()

    def _import_component_lines(self, rows: list[dict[str, str]]):
        sheet = 'Component Lines'
        for idx, row in enumerate(rows, start=2):
            component = self._component_by_name(row.get('component_name') or '')
            inv = self._inventory_by_name(row.get('ingredient_name') or '')
            if not component:
                self._row_error(sheet, idx, f"Component not found: {row.get('component_name') or ''}")
                continue
            if not inv:
                self._row_error(sheet, idx, f"Inventory item not found: {row.get('ingredient_name') or ''}")
                continue
            qty = _to_float(row.get('quantity'), 0)
            if qty <= 0:
                self._row_error(sheet, idx, 'Component line quantity must be greater than zero.')
                continue
            if self.replace_recipe_lines and component.id not in self._cleared_component_lines:
                self.db.query(PrepComponentItem).filter(PrepComponentItem.component_id == component.id).delete(synchronize_session=False)
                self._cleared_component_lines.add(component.id)
            unit = inv.unit or ''
            if _norm(row.get('unit')) and _key(row.get('unit')) != _key(unit):
                self.result.add(sheet, idx, 'warning', f'Unit overridden to inventory item unit: {unit or "blank"}.')
            existing = None if self.replace_recipe_lines else self.db.query(PrepComponentItem).filter(PrepComponentItem.component_id == component.id, PrepComponentItem.inventory_item_id == inv.id).first()
            data = {
                'component_id': component.id,
                'inventory_item_id': inv.id,
                'quantity': qty,
                'unit': unit,
                'wastage_percent': _to_float(row.get('wastage_percent'), 0),
                'sort_order': _to_int(row.get('sort_order'), 0),
                'notes': _norm(row.get('notes')) or None,
            }
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'Component line updated for {component.name} / {inv.name}.')
            else:
                self.db.add(PrepComponentItem(**data))
                self.result.add(sheet, idx, 'created', f'Component line created for {component.name} / {inv.name}.')

    def _import_skus(self, rows: list[dict[str, str]]):
        sheet = 'Menu SKUs'
        for idx, row in enumerate(rows, start=2):
            menu = self._menu_by_name(row.get('menu_item_name') or '')
            if not menu:
                self._row_error(sheet, idx, f"Menu item not found: {row.get('menu_item_name') or ''}")
                continue
            existing = self._sku_by_row(row)
            data = {
                'menu_item_id': menu.id,
                'sku_code': _norm(row.get('sku_code')) or None,
                'variant_name': _norm(row.get('variant_name')),
                'size_label': _norm(row.get('size_label')) or None,
                'price': _to_float(row.get('price'), existing.price if existing else menu.price or 0),
                'packaging_cost': _to_float(row.get('packaging_cost'), existing.packaging_cost if existing else 0),
                'labor_cost': _to_float(row.get('labor_cost'), existing.labor_cost if existing else 0),
                'overhead_cost': _to_float(row.get('overhead_cost'), existing.overhead_cost if existing else 0),
                'is_active': _to_bool(row.get('is_active'), existing.is_active if existing else True),
                'notes': _norm(row.get('notes')) or None,
            }
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', f'SKU {data["sku_code"] or data["variant_name"] or existing.id} updated.')
            else:
                self.db.add(MenuSKU(**data))
                self.result.add(sheet, idx, 'created', f'SKU {data["sku_code"] or data["variant_name"] or menu.name} created.')
            self.db.flush()

    def _import_sku_recipe_lines(self, rows: list[dict[str, str]]):
        sheet = 'SKU Recipe Lines'
        for idx, row in enumerate(rows, start=2):
            sku = self._sku_by_row(row)
            if not sku:
                self._row_error(sheet, idx, 'SKU not found. Use sku_code, or menu_item_name + variant_name/size_label.')
                continue
            line_type = _key(row.get('line_type') or 'inventory')
            qty = _to_float(row.get('quantity'), 0)
            if qty <= 0:
                self._row_error(sheet, idx, 'SKU recipe quantity must be greater than zero.')
                continue
            if self.replace_recipe_lines and sku.id not in self._cleared_sku_recipes:
                self.db.query(MenuSKURecipeItem).filter(MenuSKURecipeItem.sku_id == sku.id).delete(synchronize_session=False)
                self._cleared_sku_recipes.add(sku.id)
            inv = None
            component = None
            if line_type == 'component':
                component = self._component_by_name(row.get('component_name') or '')
                if not component:
                    self._row_error(sheet, idx, f"Component not found: {row.get('component_name') or ''}")
                    continue
                unit = component.yield_unit or ''
            else:
                line_type = 'inventory'
                inv = self._inventory_by_name(row.get('ingredient_name') or '')
                if not inv:
                    self._row_error(sheet, idx, f"Inventory item not found: {row.get('ingredient_name') or ''}")
                    continue
                unit = inv.unit or ''
            if _norm(row.get('unit')) and _key(row.get('unit')) != _key(unit):
                self.result.add(sheet, idx, 'warning', f'Unit overridden to controlled unit: {unit or "blank"}.')
            existing = None
            if not self.replace_recipe_lines:
                q = self.db.query(MenuSKURecipeItem).filter(MenuSKURecipeItem.sku_id == sku.id, MenuSKURecipeItem.line_type == line_type)
                if line_type == 'component':
                    q = q.filter(MenuSKURecipeItem.component_id == component.id)
                else:
                    q = q.filter(MenuSKURecipeItem.inventory_item_id == inv.id)
                existing = q.first()
            data = {
                'sku_id': sku.id,
                'line_type': line_type,
                'inventory_item_id': inv.id if inv else None,
                'component_id': component.id if component else None,
                'quantity': qty,
                'unit': unit,
                'wastage_percent': _to_float(row.get('wastage_percent'), 0),
                'sort_order': _to_int(row.get('sort_order'), 0),
                'notes': _norm(row.get('notes')) or None,
            }
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                self.db.add(existing)
                self.result.add(sheet, idx, 'updated', 'SKU recipe line updated.')
            else:
                self.db.add(MenuSKURecipeItem(**data))
                self.result.add(sheet, idx, 'created', 'SKU recipe line created.')


def import_setup_workbook(db: Session, content: bytes, dry_run: bool = False, replace_recipe_lines: bool = True) -> dict[str, Any]:
    importer = SetupWorkbookImporter(db, dry_run=dry_run, replace_recipe_lines=replace_recipe_lines)
    return importer.import_content(content)
