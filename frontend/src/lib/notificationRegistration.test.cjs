const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  module._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, filename);
};
const { waitForActiveWorker } = require('./notificationRegistration.ts');

test('attend que le worker enregistré soit activé', async () => {
  const worker = new EventTarget();
  worker.state = 'installing';
  const registration = { active: null, installing: worker, waiting: null };
  let finished = false;
  const pending = waitForActiveWorker(registration, 1000).then(() => { finished = true; });
  await Promise.resolve();
  assert.equal(finished, false);
  worker.state = 'activated';
  registration.active = worker;
  worker.dispatchEvent(new Event('statechange'));
  await pending;
  assert.equal(finished, true);
});

test('accepte un worker déjà actif', async () => {
  await waitForActiveWorker({ active: { state: 'activated' } }, 100);
});

test('signale un worker devenu redondant ou une attente trop longue', async () => {
  const worker = new EventTarget();
  worker.state = 'installing';
  const pending = waitForActiveWorker({ active: null, installing: worker, waiting: null }, 1000);
  worker.state = 'redundant';
  worker.dispatchEvent(new Event('statechange'));
  await assert.rejects(pending, /service worker/i);
  await assert.rejects(waitForActiveWorker({ active: null, installing: null, waiting: null }, 10), /service worker/i);
});