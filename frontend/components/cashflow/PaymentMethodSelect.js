const OPTIONS = [
  ['cash', 'Cash'],
  ['bank_transfer', 'Bank Transfer'],
  ['e_wallet', 'E-Wallet (GCash)'],
  ['card', 'Card'],
  ['check', 'Check'],
  ['online_gateway', 'Online Gateway'],
  ['other', 'Other'],
];

export default function PaymentMethodSelect({
  label = 'Payment Method',
  value,
  onChange,
  required = false,
}) {
  return (
    <label>
      {label}
      <select required={required} value={value || ''} onChange={(e) => onChange(e.target.value)}>
        {OPTIONS.map(([code, name]) => (
          <option key={code} value={code}>{name}</option>
        ))}
      </select>
    </label>
  );
}
