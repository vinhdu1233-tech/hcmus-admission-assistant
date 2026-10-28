import assert from 'node:assert/strict';
import { ADMISSION_METHODS, commonTasks } from '../ui/admission-methods.js';

assert.deepEqual(ADMISSION_METHODS['2026'].map(m=>m.id), ['1a','1b','2']);
assert.deepEqual(ADMISSION_METHODS['2025'].map(m=>m.id), ['1a','1b','1c','1d','2','3']);
assert.equal(ADMISSION_METHODS['2027'], undefined);
const method2=ADMISSION_METHODS['2026'].find(m=>m.id==='2');
assert.deepEqual(method2.paths.map(p=>p.id), ['thpt','dgnl']);
const thpt=method2.paths.find(p=>p.id==='thpt');
const dgnl=method2.paths.find(p=>p.id==='dgnl');
assert.ok(thpt.tasks.some(t=>t.title.includes('THPT')));
assert.ok(dgnl.tasks.some(t=>t.title.includes('ĐGNL')));
assert.ok(!dgnl.tasks.some(t=>t.title.includes('kết quả thi tốt nghiệp THPT')));
assert.ok(method2.source.includes('hcmus.edu.vn'));
assert.ok(commonTasks(2026).length>=3);
console.log('Admission-method configuration: PASS');
