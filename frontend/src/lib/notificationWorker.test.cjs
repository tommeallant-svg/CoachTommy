const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function worker() {
  const handlers = {};
  const shown = [];
  const opened = [];
  const self = {
    location: { origin: 'https://example.com' },
    addEventListener: (name, handler) => { handlers[name] = handler; },
    registration: { showNotification: (...args) => { shown.push(args); return Promise.resolve(); } },
    clients: { openWindow: url => { opened.push(url); return Promise.resolve(); } },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../public/notification-sw.js'), 'utf8'), { self, URL });
  return { handlers, shown, opened };
}

test('push accepts only known events and safe workout identifiers', () => {
  const { handlers, shown } = worker();
  const send = payload => handlers.push({ data: { json: () => payload }, waitUntil: () => {} });
  send({ kind: 'morning_reminder', workout_id: 42, url: 'https://evil.example' });
  assert.equal(shown.length, 1);
  assert.equal(shown[0][1].data.workoutId, 42);
  send({ kind: 'constructor', workout_id: 1 });
  send({ kind: 'workout_validated', workout_id: '../login' });
  send({ kind: 'workout_validated', workout_id: -1 });
  handlers.push({ data: { json: () => { throw new Error(); } }, waitUntil: () => {} });
  assert.equal(shown.length, 1);
});

test('click opens only a same-origin workout path', () => {
  const { handlers, opened } = worker();
  const click = workoutId => handlers.notificationclick({ notification: { data: { workoutId }, close: () => {} }, waitUntil: () => {} });
  click(12);
  click('//evil.example');
  assert.deepEqual(opened, ['https://example.com/workouts/12']);
});