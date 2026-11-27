// Group only known shared historical seed milestones with identical content.
export function groupCalendarEvents(events){
  const groups=new Map(),out=[];
  for(const e of events){
    const match=e.user_id===null&&/^official-2026-(1a|1b|2)-(result|appeal|confirm|enroll)$/.exec(e.id);
    if(!match){out.push(e);continue;}
    const key=JSON.stringify([match[2],e.year,e.title,e.starts,e.ends,e.source_url,e.note]);
    if(!groups.has(key)){const group={...e,variants:[e]};groups.set(key,group);out.push(group);}
    else groups.get(key).variants.push(e);
  }
  return out.map(e=>e.variants?.length===1?e.variants[0]:e);
}
