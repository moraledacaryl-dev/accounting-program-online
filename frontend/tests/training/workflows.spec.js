const {test,expect}=require('@playwright/test');
const fs=require('fs'),path=require('path');
const fixtures=JSON.parse(fs.readFileSync(process.env.TRAINING_TEST_FIXTURES,'utf8'));
const targetCode=fs.readFileSync(path.join(__dirname,'../../lib/training-targets.js'),'utf8').replace('export function trainingTargets','function trainingTargets');

async function trainingApi(page,route,body){
 return page.evaluate(async({route,body})=>{
  const response=await fetch('/api/training/'+route,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Requested-With':'HiddenOasisAccountingTraining'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));return data;
 },{route,body});
}
async function start(page,lesson,mode='guided',exam_id){
 const result=await trainingApi(page,'start',{lesson_id:lesson.id,mode,exam_id});
 await page.evaluate(id=>{sessionStorage.setItem('accounting-training-attempt',id);localStorage.setItem('accounting-training-attempt',id);},result.attempt_id);
 await page.goto(result.lesson.route);
 await expect(page.getByRole('complementary',{name:'Your training task'})).toBeVisible();
 return result;
}
async function exercise(page,lesson,guided=true){
 if(!guided && lesson.steps.length)await page.getByRole('button',{name:'Hide guide',exact:true}).click();
 for(let index=0;index<lesson.steps.length;index++){
  const step=lesson.steps[index];
  if(guided)await expect(page.locator('.accounting-training-coach-label')).toContainText(`Action ${index+1} of`);
  await page.waitForFunction(({code,target})=>{
   const nodes=new Function(code+';return trainingTargets(arguments[0]);')(target);
   const found=nodes.find(node=>node.checkVisibility({checkVisibilityCSS:true})&&node.getBoundingClientRect().width>0);
   if(found){document.querySelectorAll('[data-test-training-target]').forEach(node=>node.removeAttribute('data-test-training-target'));found.setAttribute('data-test-training-target','1');return true;}return false;
  },{code:targetCode,target:step.target},{timeout:10000}).catch(async error=>{
   // Real source forms may be inside collapsed details. Open that actual section.
   const opened=await page.evaluate(({code,target})=>{const nodes=new Function(code+';return trainingTargets(arguments[0]);')(target);const detail=nodes[0]?.closest('details:not([open])');if(detail){detail.open=true;return true;}return false;},{code:targetCode,target:step.target});
   if(!opened)throw new Error(lesson.id+' step '+index+' '+step.target+': '+error.message);
  });
  await page.evaluate(({code,target})=>{const found=new Function(code+';return trainingTargets(arguments[0]);')(target).find(node=>node.checkVisibility({checkVisibilityCSS:true}));if(found)found.setAttribute('data-test-training-target','1');},{code:targetCode,target:step.target});
  const control=page.locator('[data-test-training-target="1"]').first();
  if(step.event==='input')await control.fill(String(step.value));
  else if(step.event==='change')await control.selectOption(String(step.value));
  else await control.click();
  if(guided && index+1<lesson.steps.length)await expect(page.locator('.accounting-training-coach-label')).toContainText(`Action ${index+2} of`,{timeout:10000});
 }
 if(!guided && lesson.steps.length)await page.getByRole('button',{name:'Show guide',exact:true}).click();
 const coach=page.getByRole('complementary',{name:'Your training task'});
 if(lesson.practical_question)await coach.getByLabel(lesson.practical_question,{exact:true}).fill(lesson.observation);
 await coach.getByLabel(lesson.question,{exact:true}).fill(lesson.answer);
 await coach.getByRole('button',{name:'Check my work',exact:true}).click();
 await expect(coach.getByRole('heading',{name:'Task passed',exact:true})).toBeVisible();
}

test('employee onboarding, responsive course and private trainer roster',async({page})=>{
 await page.goto('/training');await page.getByLabel('Your name',{exact:true}).fill('Browser training learner');
 await page.getByRole('button',{name:'Start training',exact:true}).click();
 await expect(page.getByRole('heading',{name:/Welcome back/})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.getByRole('button',{name:'Record money actually received',exact:true}).click();
 await page.getByRole('button',{name:'Start guided practice',exact:true}).click();
 await expect(page.getByRole('complementary',{name:'Your training task'})).toBeVisible();
 await exercise(page,fixtures.lessons.find(row=>row.id==='receipt'));
 await page.reload();await expect(page.getByRole('heading',{name:'Task passed',exact:true})).toBeVisible();
 await page.goto('/training/management');
 await expect(page.getByLabel('Trainer access code',{exact:true})).toBeVisible();
});

for(const lesson of fixtures.lessons)test('real saved work: '+lesson.id,async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/training');await trainingApi(page,'enrol',{name:'Fictional browser learner',role:lesson.roles[0]});
 await start(page,lesson);await exercise(page,lesson);
 expect(errors).toEqual([]);
});

test('full duty certification, saved final answers, trainer review and immutable retakes',async({page})=>{
 test.setTimeout(180000);
 await page.goto('/training');await trainingApi(page,'enrol',{name:'Fictional certified auditor',role:'auditor'});
 const lessons=fixtures.lessons.filter(row=>row.roles.includes('auditor'));
 for(const lesson of lessons)for(const mode of ['guided','assisted','independent']){
  await start(page,lesson,mode);await exercise(page,lesson.variants[mode],mode==='guided');
 }
 const catalogue=await trainingApi(page,'exams');let final;
 for(const row of catalogue.blueprints){
  const exam=await trainingApi(page,'exams/start',{module:row.module});
  for(const id of exam.blueprint.practical_lessons){const lesson=fixtures.lessons.find(row=>row.id===id);await start(page,lesson,'independent',exam.id);await exercise(page,lesson.variants.independent,false);}
  const answers=fixtures.exams['role-auditor'][row.module||'final'];
  if(row.module){const result=await trainingApi(page,'exams/'+exam.id+'/submit',{answers});expect(result.status).toBe('passed');}
  else final={exam,answers};
 }
 await page.goto('/training/assessments?exam='+final.exam.id);
 for(const [id,answer] of Object.entries(final.answers))await page.locator(`[data-training-question="${id}"]`).fill(String(answer));
 await expect(page.getByText('Answers saved',{exact:true})).toBeVisible();
 await page.reload();for(const [id,answer] of Object.entries(final.answers))await expect(page.locator(`[data-training-question="${id}"]`)).toHaveValue(String(answer));
 await page.getByRole('button',{name:'Submit final check',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Final check passed',exact:true})).toBeVisible();
 await expect(page.getByText('TRAINING-'+final.exam.id,{exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('heading',{name:'Final check passed',exact:true})).toBeVisible();
 if(process.env.TRAINING_MANAGER_KEY_PATH){await page.goto('/training/management');await page.getByLabel('Trainer access code',{exact:true}).fill(fs.readFileSync(process.env.TRAINING_MANAGER_KEY_PATH,'utf8').trim());await page.getByRole('button',{name:'Open training progress',exact:true}).click();await expect(page.getByText('Fictional certified auditor',{exact:true}).first()).toBeVisible();}
});
