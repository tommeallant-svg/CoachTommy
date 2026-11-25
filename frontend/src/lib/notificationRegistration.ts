export function waitForActiveWorker(registration: ServiceWorkerRegistration, timeoutMs = 15000): Promise<void> {
  return new Promise((resolve, reject) => {
    let worker: ServiceWorker | null = null;
    const message = 'Le service worker de notifications n’a pas pu être activé. Rechargez la page et réessayez.';
    const cleanup = () => {
      clearTimeout(timer);
      worker?.removeEventListener('statechange', check);
      registration.removeEventListener?.('updatefound', check);
    };
    const check = () => {
      if (registration.active?.state === 'activated') {
        cleanup();
        resolve();
        return;
      }
      const current = registration.installing || registration.waiting || registration.active;
      if (current !== worker) {
        worker?.removeEventListener('statechange', check);
        worker = current;
        worker?.addEventListener('statechange', check);
      }
      if (worker?.state === 'redundant') {
        cleanup();
        reject(new Error(message));
      }
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(message));
    }, timeoutMs);
    registration.addEventListener?.('updatefound', check);
    check();
  });
}