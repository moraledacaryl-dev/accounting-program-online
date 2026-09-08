const {test,expect}=require('@playwright/test');
const {default:AxeBuilder}=require('@axe-core/playwright');
async function fixture(page,{emptyAccounts=false}={}) {
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  const body=path==='/api/auth/me'?{id:1,username:'ui-review',full_name:'UI Review',role:'owner',permissions:['*']}:path.startsWith('/api/chart-of-accounts')&&!emptyAccounts?[{id:1,code:'1000',name:'Cash',account_type:'asset',is_active:true}]:path==='/api/dashboard/summary'?{cash_on_hand:100,bank_balance:200,command_center:{}}:[];
  return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
}
test('every group remains available when collapsed and the toggle stays legible',async({page})=>{
 await fixture(page);await page.goto('/dashboard');
 const nav=page.getByRole('complementary',{name:'Accounting navigation'});
 await nav.getByRole('button',{name:'Collapse sidebar',exact:true}).click();
 for(const name of ['Overview','Money','Sales & Receivables','Purchases & Payables','Accounting','Operations Integration','Administration']) await expect(nav.getByRole('button',{name,exact:true})).toBeVisible();
 const size=await page.locator('.sidebar-toggle.desktop-only svg').boundingBox();expect(size.width).toBeGreaterThanOrEqual(17);
 await nav.getByRole('button',{name:'Money',exact:true}).click();
 await expect(nav.getByRole('button',{name:'Collapse sidebar',exact:true})).toBeVisible();
 await expect(nav.getByRole('link',{name:'Money In',exact:true})).toBeVisible();
 const pos=await nav.getByRole('link',{name:'Money In',exact:true}).locator('.nav-text').boundingBox();expect(pos.x).toBeLessThan(65);
 await expect(page.locator('.brand-badge')).toHaveCSS('color','rgb(255, 255, 255)');
});
test('payables highlights only its destination and owning group',async({page})=>{
 await fixture(page);await page.goto('/cashflow/payables');
 const nav=page.getByRole('complementary',{name:'Accounting navigation'});
 await expect(nav.locator('a[aria-current="page"]')).toHaveCount(1);
 await expect(nav.getByRole('link',{name:'Payables',exact:true})).toHaveAttribute('aria-current','page');
 await expect(nav.getByRole('button',{name:'Purchases & Payables',exact:true})).toHaveAttribute('aria-expanded','true');
 await expect(page.getByRole('banner').getByText('Bills to Pay',{exact:true})).toBeVisible();
});
for(const width of [390,768]) test(`menu and report layout work at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:900});await page.goto('/reports');await page.waitForLoadState('networkidle');
 const title=await page.getByRole('heading',{name:'Reports & Reconciliation',exact:true}).boundingBox();
 const context=await page.locator('.context-nav-stack').boundingBox();expect(title.y).toBeGreaterThanOrEqual(context.y+context.height);
 const opener=page.getByRole('button',{name:'Open navigation',exact:true});await opener.click();
 const dialog=page.getByRole('dialog',{name:'Accounting navigation'});await expect(dialog).toBeVisible();
 for(let i=0;i<12;i++){await page.keyboard.press('Tab');expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);}
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await expect(opener).toBeFocused();
 const svg=await opener.locator('svg').boundingBox();expect(svg.width).toBeGreaterThanOrEqual(17);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 const exportButton=page.getByRole('button',{name:'Export CSV',exact:true});expect(await exportButton.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);
});
for(const [path,action,title] of [['/users','Create User','Create User'],['/account-mapping','New Mapping','New Mapping'],['/assets','Add Asset','Add Asset']]) test(`${path} opens its form in a keyboard-safe drawer`,async({page})=>{
 await fixture(page);await page.goto(path);await expect(page.getByRole('dialog')).toHaveCount(0);
 const open=page.getByRole('button',{name:action,exact:true});await open.click();
 const dialog=page.getByRole('dialog',{name:title,exact:true});await expect(dialog).toBeVisible();
 for(let i=0;i<20;i++){await page.keyboard.press('Tab');expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);}
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await expect(open).toBeFocused();
});
test('empty journal setup links to accounts and staff meal handoff identifies the available workflow',async({page})=>{
 await fixture(page,{emptyAccounts:true});await page.goto('/journals');await page.getByRole('button',{name:'Create Entry',exact:true}).click();
 await expect(page.getByRole('link',{name:'Set up chart of accounts'})).toHaveAttribute('href','/chart-of-accounts');
 await page.goto('/staff-meals');await expect(page.getByRole('link',{name:'Record ingredient usage in Inventory'})).toHaveAttribute('href','https://inventory.hiddenoasis.app/stock');
 await expect(page.getByText('a dedicated meal log is not yet available in Inventory.',{exact:false})).toBeVisible();
});
for(const width of [390,1440]) for(const path of ['/dashboard','/journals','/cashflow/payables','/reports']) test(`accessibility ${width} ${path}`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:900});await page.goto(path);await page.waitForLoadState('networkidle');
 if(path==='/journals')await page.getByRole('button',{name:'Create Entry',exact:true}).click();
 if(path==='/cashflow/payables')await page.getByRole('button',{name:'Add Bill',exact:true}).click();
 const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();expect(result.violations).toEqual([]);
});

test('cash action and close redirects select their actual navigation item',async({page})=>{
 await fixture(page);
 for(const [path,label] of [['/cashflow?tab=overview&action=money-in','Money In'],['/cashflow?tab=close','Daily Close & Reconciliation']]){
  await page.goto(path);
  const current=page.locator('.sidebar a[aria-current="page"]');await expect(current).toHaveCount(1);await expect(current).toHaveText(label);
 }
});
for(const [path,action,fields] of [
 ['/users','Create User',[['Username','ui-test'],['Password','only-a-browser-fixture']]],
 ['/account-mapping','New Mapping',[['Module Slug','restaurant']]],
 ['/assets','Add Asset',[['Name','Review fixture asset']]],
]) test(`${path} preserves form input after save failure and closes after retry`,async({page})=>{
 await fixture(page);let writes=0;
 await page.route('**/api/**',route=>{
  if(route.request().method()!=='POST'||new URL(route.request().url()).pathname==='/api/auth/csrf')return route.fallback();
  writes++;return route.fulfill({status:writes===1?503:200,contentType:'application/json',body:JSON.stringify(writes===1?{detail:'Temporary save failure'}:{id:1})});
 });
 await page.goto(path);await page.getByRole('button',{name:action,exact:true}).click();
 const dialog=page.getByRole('dialog');
 for(const [name,value] of fields)await dialog.getByLabel(name,{exact:true}).fill(value);
 await dialog.locator('button[type="submit"]').click();await expect(dialog.getByRole('alert')).toHaveText('Temporary save failure');
 for(const [name,value] of fields)await expect(dialog.getByLabel(name,{exact:true})).toHaveValue(value);
 await dialog.locator('button[type="submit"]').click();await expect(dialog).toHaveCount(0);expect(writes).toBe(2);
});
