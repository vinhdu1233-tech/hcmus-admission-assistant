import test from 'node:test';
import assert from 'node:assert/strict';
import {groupCalendarEvents} from '../ui/calendar-grouping.mjs';
const event=(method,extra={})=>({id:'official-2026-'+method+'-result',user_id:null,year:2026,method,title:'Kết quả',starts:1,ends:2,source_url:'https://example.test',note:'common',...extra});
test('common milestones display once with separate method records',()=>{
 const rows=groupCalendarEvents(['1a','1b','2'].map(m=>event(m)));
 assert.equal(rows.length,1);assert.deepEqual(rows[0].variants.map(v=>v.method),['1a','1b','2']);
});
test('single filter and differing dates stay distinct',()=>{
 assert.equal(groupCalendarEvents([event('1a')])[0].variants,undefined);
 assert.equal(groupCalendarEvents([event('1a'),event('2',{ends:3})]).length,2);
});
test('personal and unrelated official events are not merged',()=>{
 const a=event('1a',{id:'custom-a',user_id:10}),b=event('1b',{id:'custom-b',user_id:10});
 assert.equal(groupCalendarEvents([a,b,event('2',{id:'official-new'})]).length,3);
});
