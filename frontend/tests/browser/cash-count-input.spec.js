const {test,expect}=require('@playwright/test');

test('cash close retains observed values and previews the selected account',async({page})=>{
 let saved;
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());let body=[];
  if(url.pathname==='/api/auth/me')body={id:1,username:'counter',role:'owner',permissions:['*']};
  if(url.pathname==='/api/auth/csrf')body={csrf_token:'fictional-test-csrf'};
  if(url.pathname.replace(/\/$/,'')==='/api/financial-accounts')body=[
   {id:101,name:'Practice Cash',code:'CASH',account_type:'cash_drawer',current_balance:5000,is_active:true,requires_physical_count:true},
   {id:102,name:'Practice Bank',code:'BANK',account_type:'bank',current_balance:10000,is_active:true}];
  if(url.pathname==='/api/cashflow/summary')body={summary_cards:{},accounts_requiring_reconciliation:[]};
  if(url.pathname.startsWith('/api/taxonomy'))body={};
  if(url.pathname.replace(/\/$/,'')==='/api/reconciliations'&&route.request().method()==='POST'){
   saved=route.request().postDataJSON();body={id:1,...saved};
  }
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/cashflow?tab=close');
 await page.getByRole('row').filter({hasText:'Practice Cash'}).getByRole('button',{name:'Count / reconcile',exact:true}).click();
 const drawer=page.locator('.workspace-drawer');
 await drawer.getByLabel('Counted Amount',{exact:true}).fill('4980');
 await drawer.getByLabel('Notes',{exact:true}).fill('Observed amount from the physical count.');
 await expect(drawer.getByText('Short -20.00',{exact:true})).toBeVisible();
 await drawer.getByRole('combobox',{name:/^Account\b/}).selectOption('102');
 await expect(drawer.getByRole('heading',{name:'Practice Bank Close',exact:true})).toBeVisible();
 await expect(drawer.getByText('Short -5020.00',{exact:true})).toBeVisible();
 await drawer.getByRole('button',{name:'Save Count',exact:true}).click();
 await expect.poll(()=>saved).toMatchObject({financial_account_id:102,actual_counted:4980,notes:'Observed amount from the physical count.'});
});
