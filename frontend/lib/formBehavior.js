export function shouldPreventEnterSubmit(event, isSubmittable) {
  if (!event || event.defaultPrevented) return false;
  if (event.key !== 'Enter') return false;

  const target = event.target;
  if (!target || typeof target !== 'object') return false;

  const tagName = String(target.tagName || '').toLowerCase();
  const inputType = String(target.getAttribute?.('type') || '').toLowerCase();
  const role = String(target.getAttribute?.('role') || '').toLowerCase();
  const className = String(target.className || '').toLowerCase();
  const name = String(target.getAttribute?.('name') || '').toLowerCase();
  const dataPrevent = String(target.getAttribute?.('data-prevent-enter-submit') || '').toLowerCase();
  const inSearchContainer = !!target.closest?.('[data-enter-context="search"]');
  const inLineItemContainer = !!target.closest?.('[data-enter-context="line-item"]');

  const isTextarea = tagName === 'textarea';
  const isSearchLike = inputType === 'search'
    || role === 'combobox'
    || className.includes('search')
    || name.includes('search')
    || name.includes('query')
    || inSearchContainer;
  const isNonSubmitField = tagName === 'select'
    || isTextarea
    || isSearchLike
    || inLineItemContainer
    || dataPrevent === 'true';

  if (isNonSubmitField) {
    event.preventDefault();
    return true;
  }

  if (typeof isSubmittable === 'function' && !isSubmittable()) {
    event.preventDefault();
    return true;
  }
  return false;
}
