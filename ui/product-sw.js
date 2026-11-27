/* No offline cache of private data. Only push reception and safe navigation. */
self.addEventListener('push',event=>{
  let payload={};
  try{payload=event.data?.json()||{};}catch{}
  event.waitUntil(self.registration.showNotification(payload.title||'HCMUS Guide',{
    body:payload.body||'Bạn có một mốc lịch cần chú ý.',
    icon:'/assets/h-icon.svg',data:{url:payload.url||'/portal.html#calendar'}
  }));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    const u=new URL(event.notification.data?.url||'/portal.html#calendar',self.location.origin);
    const target=u.origin===self.location.origin&&u.pathname==='/portal.html'?u.href:new URL('/portal.html#calendar',self.location.origin).href;
    const windows=await clients.matchAll({type:'window',includeUncontrolled:true});
    const w=windows.find(x=>new URL(x.url).origin===self.location.origin);
    if(w){await w.navigate(target);return w.focus();}
    return clients.openWindow(target);
  })());
});
