const assert = require('node:assert/strict');
const fs = require('node:fs');
global.window = global;
require('./boards.js');
require('./sets-core.js');
const rules = JSON.parse(fs.readFileSync('set_catalog.json'));
const ids = Object.keys(graviaBoards);
const expected = {1:790,2:1090,3:1786,4:1290,5:1976,6:2261,7:2890,8:1490,9:2166,10:2451,11:3033,12:2641,13:3213,14:3483,15:4190};
function permutations(values) { return values.length ? values.flatMap((v,i) => permutations(values.filter((_,j) => i!==j)).map(rest => [v,...rest])) : [[]]; }
for (let mask=1;mask<16;mask++) {
  const selected=ids.filter((_,i)=>mask & (1<<i));
  const result=GraviaSetsCore.quote(selected,graviaBoards,rules);
  assert.equal(result.total,expected[mask]);
  assert.equal(result.preset,mask===7 || mask===15);
  for(const order of permutations(selected)) assert.deepEqual(GraviaSetsCore.quote(order,graviaBoards,rules),result);
}
assert.equal(GraviaSetsCore.quote([],graviaBoards,rules),null);
assert.throws(()=>GraviaSetsCore.quote([ids[0],ids[0]],graviaBoards,rules));
assert.throws(()=>GraviaSetsCore.quote(['unknown'],graviaBoards,rules));
console.log('Set pricing: all 15 combinations and all selection orders passed.');
