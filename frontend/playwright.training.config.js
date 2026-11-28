const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({testDir:'./tests/training',timeout:60000,workers:1,
  reporter:[['list'],['html',{outputFolder:'training-report',open:'never'}]],
  outputDir:'training-test-results',
  use:{baseURL:'http://127.0.0.1:3420',headless:true,viewport:{width:1440,height:1000},
    trace:'retain-on-failure',screenshot:'only-on-failure',
    launchOptions:process.env.TRAINING_CHROMIUM?{executablePath:process.env.TRAINING_CHROMIUM}:{}}});
