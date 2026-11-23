export interface CalendarWorkout {
  name: string;
  date: string;
  duration_minutes: number;
  description?: string | null;
}

export interface CalendarEvent {
  name: string;
  start: Date;
  end: Date;
  description: string;
}

function parseDate(value: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})?)?$/.exec(value);
  if (!match) throw new Error('Date de séance invalide');

  const [, y, mo, d, h = '0', mi = '0', s = '0', fraction = '', zone] = match;
  const year = Number(y), month = Number(mo), day = Number(d);
  const hour = Number(h), minute = Number(mi), second = Number(s);
  const milliseconds = Number((fraction + '000').slice(0, 3));
  if (year < 1 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) {
    throw new Error('Date de séance invalide');
  }

  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  calendar.setUTCHours(hour, minute, second, milliseconds);
  if (calendar.getUTCFullYear() !== year || calendar.getUTCMonth() !== month - 1 || calendar.getUTCDate() !== day) {
    throw new Error('Date de séance invalide');
  }

  if (zone) {
    if (zone !== 'Z') {
      const offsetHours = Number(zone.slice(1, 3)), offsetMinutes = Number(zone.slice(4, 6));
      if (offsetHours > 23 || offsetMinutes > 59) throw new Error('Date de séance invalide');
      const offset = (offsetHours * 60 + offsetMinutes) * (zone[0] === '+' ? 1 : -1);
      calendar.setTime(calendar.getTime() - offset * 60000);
    }
    return calendar;
  }

  const local = new Date(0);
  local.setFullYear(year, month - 1, day);
  local.setHours(hour, minute, second, milliseconds);
  if (local.getFullYear() !== year || local.getMonth() !== month - 1 || local.getDate() !== day ||
      local.getHours() !== hour || local.getMinutes() !== minute || local.getSeconds() !== second) {
    throw new Error('Date de séance invalide');
  }
  return local;
}

function utcDate(date: Date): string {
  if (!Number.isFinite(date.getTime()) || date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) {
    throw new Error('Date de séance invalide');
  }
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
}

export function createCalendarEvent(workout: CalendarWorkout): CalendarEvent {
  if (typeof workout.date !== 'string') throw new Error('Date de séance invalide');
  if (typeof workout.duration_minutes !== 'number' || !Number.isFinite(workout.duration_minutes) ||
      !Number.isInteger(workout.duration_minutes) || workout.duration_minutes <= 0) {
    throw new Error('Durée de séance invalide');
  }
  const start = parseDate(workout.date);
  const end = new Date(start.getTime() + workout.duration_minutes * 60000);
  utcDate(start);
  utcDate(end);
  return { name: workout.name, start, end, description: workout.description || '' };
}

export function createGoogleCalendarUrl(workout: CalendarWorkout): string {
  const event = createCalendarEvent(workout);
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.name,
    dates: `${utcDate(event.start)}/${utcDate(event.end)}`,
    details: event.description,
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function escapeText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\r\n|\r|\n/g, '\\n').replace(/;/g, '\\;').replace(/,/g, '\\,');
}

function foldLine(line: string): string {
  const encoder = new TextEncoder();
  const lines: string[] = [];
  let current = '';
  let bytes = 0;
  for (const character of line) {
    const length = encoder.encode(character).length;
    if (bytes + length > 75) {
      lines.push(current);
      current = ' ';
      bytes = 1;
    }
    current += character;
    bytes += length;
  }
  lines.push(current);
  return lines.join('\r\n');
}

export function createIcsCalendar(workout: CalendarWorkout): string {
  const event = createCalendarEvent(workout);
  const uid = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//CoachTommy//Calendar Export//FR',
    'BEGIN:VEVENT',
    `UID:${uid}@coachtommy`,
    `DTSTAMP:${utcDate(new Date())}`,
    `DTSTART:${utcDate(event.start)}`,
    `DTEND:${utcDate(event.end)}`,
    `SUMMARY:${escapeText(event.name)}`,
    `DESCRIPTION:${escapeText(event.description)}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ].map(foldLine).join('\r\n') + '\r\n';
}