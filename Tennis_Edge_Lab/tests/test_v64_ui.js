const assert=require('node:assert/strict');
const test=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'..','research_v64.js'),'utf8');
const {renderTopIds}=require('../research_v64.js');
test('v64 top modes are based on selected IDs, not new calculations',()=>{
 const data={candidates:[{id:'one'},{id:'two'}],tops:{top10:['two','one']}};
 assert.deepEqual(renderTopIds(data,'top10'),['two','one']);
 assert.deepEqual(renderTopIds(data,'all'),['one','two']);
});
test('v64 UI labels historical as not prospective',()=>{
 assert.match(code,/historique/i);
 assert.match(code,/pas une validation prospective/);
 assert.match(code,/clv_mean_pct/);
 assert.match(code,/roi_pct/);
});
