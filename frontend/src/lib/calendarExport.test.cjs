const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  module._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, filename);
};
const { createCalendarEvent, createGoogleCalendarUrl, createIcsCalendar } = require('./calendarExport.ts');

const workout = {
  name: 'Séance, vélo; \\ test',
  date: '2026-03-28T23:30:00',
  duration_minutes: 120,
  description: 'Échauffement\r\nPuis, effort; retour\\fin',
  scheme: 'NE PAS EXPORTER',
};

test('Google et ICS exportent les mêmes dates UTC et seulement les champs prévus', () => {
  const url = new URL(createGoogleCalendarUrl(workout));
  assert.equal(url.origin + url.pathname, 'https://calendar.google.com/calendar/render');
  assert.equal(url.searchParams.get('action'), 'TEMPLATE');
  assert.equal(url.searchParams.get('text'), workout.name);
  assert.equal(url.searchParams.get('details'), workout.description);
  assert.equal(url.searchParams.get('dates'), '20260328T223000Z/20260329T003000Z');
  const ics = createIcsCalendar(workout);
  assert.match(ics, /DTSTART:20260328T223000Z\r\nDTEND:20260329T003000Z/);
  assert.ok(ics.includes('SUMMARY:Séance\\, vélo\\; \\\\ test\r\n'));
  assert.ok(ics.includes('DESCRIPTION:Échauffement\\nPuis\\, effort\\; retour\\\\fin\r\n'));
  assert.ok(!ics.includes(workout.scheme));
  assert.ok(!url.href.includes('NE+PAS+EXPORTER'));
});

test('franchissement de minuit et changements d’heure calculés en durée réelle', () => {
  for (const [date, minutes, start, end] of [
    ['2026-01-01T23:30:00', 90, '2026-01-01T22:30:00.000Z', '2026-01-02T00:00:00.000Z'],
    ['2026-03-29T01:30:00', 120, '2026-03-29T00:30:00.000Z', '2026-03-29T02:30:00.000Z'],
    ['2026-10-25T01:30:00', 120, '2026-10-24T23:30:00.000Z', '2026-10-25T01:30:00.000Z'],
    ['2026-01-01T10:00:00+05:30', 60, '2026-01-01T04:30:00.000Z', '2026-01-01T05:30:00.000Z'],
    ['2026-01-01', 60, '2025-12-31T23:00:00.000Z', '2026-01-01T00:00:00.000Z'],
  ]) {
    const event = createCalendarEvent({ ...workout, date, duration_minutes: minutes });
    assert.equal(event.start.toISOString(), start);
    assert.equal(event.end.toISOString(), end);
  }
});

test('dates et durées invalides sont refusées', () => {
  for (const date of ['2026-02-29T10:00', '2026-04-31', '2026-13-01', '2026-01-01T24:00', '2026-01-01T10:60', '2026-01-01T10:00+25:00', '2026-03-29T02:30', 'nonsense', '']) {
    assert.throws(() => createCalendarEvent({ ...workout, date }), /Date/);
  }
  for (const duration_minutes of [0, -1, 1.5, NaN, Infinity, null, '30', Number.MAX_SAFE_INTEGER]) {
    assert.throws(() => createCalendarEvent({ ...workout, duration_minutes }));
  }
});

test('ICS replie à 75 octets UTF-8 maximum sans couper les caractères', () => {
  const name = 'é😀'.repeat(60);
  const ics = createIcsCalendar({ ...workout, name, description: null });
  assert.ok(!/(?<!\r)\n|\r(?!\n)/.test(ics));
  for (const line of ics.split('\r\n')) assert.ok(Buffer.byteLength(line, 'utf8') <= 75);
  const unfolded = ics.replace(/\r\n[ \t]/g, '');
  assert.ok(unfolded.includes(`SUMMARY:${name}\r\n`));
  assert.ok(unfolded.includes('DESCRIPTION:\r\n'));
  assert.ok(!ics.includes('�'));
});