---
name: external-service-hailing-web-push-vapid
type: reference
source: https://pqvst.com/2023/11/21/web-push-notifications/
source_sha: 6073f550eafac442
fetched_at: 2026-07-28T10:49:36Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-web-push-vapid
---

## reference · service-hailing-web-push-vapid

- **VAPID requirement**  
  - Chrome & Safari **require** VAPID keys.  
  - Firefox does **not** require VAPID keys.  
  - Safari error: `Subscribing for push requires an applicationServerKey`.  
  - Chrome error: `DOMException: Registration failed - missing applicationServerKey, and gcm_sender_id not found in manifest`.

- **Generate VAPID keys**  
  - Use https://vapidkeys.com/ to obtain a public/private key pair.  
  - Keep the private key secret; only expose the public key to the client.

- **Subscription JSON structure**  
  ```json
  {
    "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/…",
    "expirationTime": null,
    "keys": { "auth": "...", "p256dh": "…" }
  }
  ```
  - Firefox endpoint: `https://updates.push.services.mozilla.com/...`  
  - Safari endpoint: `https://web.push.apple.com/...`  
  - Chrome endpoint: `https://fcm.googleapis.com/fcm/send/...`

- **Server‑side (Node.js)**  
  - Install `web-push` (`npm i web-push`).  
  - Configure VAPID:  
    ```js
    import webPush from 'web-push';
    const vapid = { publicKey: '…', privateKey: '…' };
    webPush.setVapidDetails('mailto:<email-address>', vapid.publicKey, vapid.privateKey);
    ```
  - Persist subscriptions (DB or JSON file).  
  - Broadcast notification:  
    ```js
    async function pushNotification(payload) {
      await Promise.all(subscriptions.map(async sub => {
        try { await webPush.sendNotification(sub, payload); }
        catch (err) { console.log(sub.endpoint, '->', err.message); /* delete sub */ }
      }));
    }
    pushNotification('This is a test notification!');
    ```

- **Client‑side**  
  1. **Request permission**  
     ```js
     Notification.requestPermission().then(permission => {
       if (permission === 'granted') init();
     });
     ```
  2. **Register service worker & subscribe**  
     ```js
     const vapidPublicKey = '…';
     async function initServiceWorker() {
       const sw = await navigator.serviceWorker.register('sw.js');
       let sub = await sw.pushManager.getSubscription();
       if (!sub) sub = await sw.pushManager.subscribe({
         userVisibleOnly: true,
         applicationServerKey: vapidPublicKey
       });
       fetch('/subscribe', {method:'post', body:JSON.stringify(sub),
         headers:{'content-type':'application/json'}});
     }
     window.addEventListener('load', initServiceWorker);
     ```
  3. **Service worker (`sw.js`)**  
     ```js
     self.addEventListener('push', event => {
       const opts = { body: event.data.text(), icon:'/apple-touch-icon.png',
                      badge:'/badge.png' };
       event.waitUntil(self.registration.showNotification('My App', opts));
     });
     self.addEventListener('notificationclick', event => {
       event.notification.close();
       const targetUrl = '…';
       event.waitUntil(
         clients.matchAll({type:'window'}).then(wc => {
           for (const c of wc) if (c.url===targetUrl && c.focus) return c.focus();
           return clients.openWindow(targetUrl);
         })
       );
     });
     ```
  4. **Reloading service worker** – manually reload in dev tools or enable auto‑reload on page refresh.

-
