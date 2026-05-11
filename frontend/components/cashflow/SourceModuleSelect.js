const MODULES = [
  'rooms',
  'restaurant',
  'breakfast',
  'cafe',
  'bar',
  'events',
  'inventory',
  'procurement',
  'internal',
  'channel_ota',
  'reconciliation',
  'payroll',
  'assets',
  'utilities',
  'finance',
  'other_income',
];

const MODULE_LABELS = {
  rooms: 'Rooms',
  restaurant: 'Restaurant',
  breakfast: 'Breakfast',
  cafe: 'Cafe',
  bar: 'Bar',
  events: 'Events',
  inventory: 'Inventory',
  procurement: 'Purchasing',
  internal: 'Internal',
  channel_ota: 'OTA / channel',
  reconciliation: 'Periodic check',
  payroll: 'Payroll',
  assets: 'Assets',
  utilities: 'Utilities',
  finance: 'Finance',
  other_income: 'Other income',
};

export default function SourceModuleSelect({ value = 'finance', onChange, label = 'Area' }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange?.(e.target.value)}>
        {MODULES.map((moduleSlug) => (
          <option key={moduleSlug} value={moduleSlug}>{MODULE_LABELS[moduleSlug] || moduleSlug}</option>
        ))}
      </select>
    </label>
  );
}
