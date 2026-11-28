/** Resolve real source controls semantically; never create substitute practice editors. */
function labelText(node) {
  const copy=node.cloneNode(true);
  copy.querySelectorAll('input,select,textarea,button,option').forEach(child=>child.remove());
  return copy.textContent.replace(/\s+/g,' ').trim();
}

export function trainingTargets(selector) {
  if (!selector || typeof document==='undefined') return [];
  let scopes=[document];
  for (const segment of selector.split('>>')) {
    const part=segment.trim();
    const match=part.match(/^(form|label|button|summary|row|toggle):(.+)$/);
    if (!match) {
      scopes=scopes.flatMap(scope=>part==='dialog'?Array.from(scope.querySelectorAll('dialog[open],[role="dialog"]')):Array.from(scope.querySelectorAll(part)));
      continue;
    }
    const [,kind,content]=match;
    scopes=scopes.flatMap(scope=>{
      if(kind==='form') return Array.from(scope.querySelectorAll('form')).filter(form=>Array.from(form.querySelectorAll('button')).some(button=>button.textContent.trim()===content));
      if(kind==='row') return Array.from(scope.querySelectorAll('tr')).filter(row=>row.textContent.includes(content));
      if(kind==='toggle') return Array.from(scope.querySelectorAll('.toggle-field')).filter(row=>row.querySelector('.toggle-label')?.textContent.trim()===content).map(row=>row.querySelector('button'));
      if(kind==='label') return Array.from(scope.querySelectorAll('label')).filter(label=>labelText(label)===content).map(label=>label.querySelector('input,select,textarea'));
      return Array.from(scope.querySelectorAll(kind)).filter(node=>node.textContent.trim()===content||node.getAttribute('aria-label')===content);
    }).filter(Boolean);
  }
  return scopes;
}
