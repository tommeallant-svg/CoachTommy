self.addEventListener('push', (event) => {
  let payload;
  try {
    payload = event.data && event.data.json();
  } catch {
    return;
  }
  if (!payload || !Number.isSafeInteger(payload.workout_id) || payload.workout_id <= 0) return;
  const messages = {
    morning_reminder: 'Une séance est prévue aujourd’hui.',
    evening_reminder: 'Pensez à valider votre séance.',
    workout_validated: 'Une séance a été validée.',
  };
  if (!Object.prototype.hasOwnProperty.call(messages, payload.kind)) return;
  event.waitUntil(self.registration.showNotification('Coach Tommy', {
    body: messages[payload.kind],
    data: { workoutId: payload.workout_id },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const id = event.notification.data && event.notification.data.workoutId;
  if (!Number.isSafeInteger(id) || id <= 0) return;
  const url = new URL(`/workouts/${id}`, self.location.origin).href;
  event.waitUntil(self.clients.openWindow(url));
});