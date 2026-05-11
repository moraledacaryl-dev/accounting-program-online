export default function TemplatePicker({ templates = [], value = '', onChange }) {
  return (
    <label>
      Template
      <select value={value} onChange={(e) => onChange?.(e.target.value)}>
        <option value="">Select</option>
        {templates.map((tpl) => (
          <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
        ))}
      </select>
    </label>
  );
}
