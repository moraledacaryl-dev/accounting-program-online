export default function AccountSelector({ accounts = [], value = '', onChange, label = 'Financial Account', required = false, types = [] }) {
  const filtered = types.length ? accounts.filter((a) => types.includes(a.account_type)) : accounts;
  return (
    <label>
      {label}
      <select required={required} value={value} onChange={(e) => onChange?.(e.target.value)}>
        <option value="">Select</option>
        {filtered.map((account) => (
          <option key={account.id} value={account.id}>
            {account.code} · {account.name}
          </option>
        ))}
      </select>
    </label>
  );
}
