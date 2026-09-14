const fs = require('fs');
const path = require('path');

describe('event calendar visual contract', () => {
  const css = fs.readFileSync(path.join(__dirname, '..', 'app', 'events', 'calendar', 'event-calendar.css'), 'utf8');

  test('calendar days are a light surface, not solid brand tiles', () => {
    expect(css).toMatch(/\.event-calendar-day[^}]*background:#fff!important/);
    expect(css).not.toMatch(/\.event-calendar-day[^}]*background:var\(--brand\)/);
  });

  test('selected day uses a light accent and events use strips', () => {
    expect(css).toMatch(/\.event-calendar-day\.selected[^}]*background:#f5faf7!important/);
    expect(css).toMatch(/\.event-calendar-event[^}]*border-left:3px solid/);
  });

  test('calendar operational text stays readable', () => {
    expect(css).toMatch(/\.event-calendar-weekdays div[^}]*font-size:12px/);
    expect(css).toMatch(/\.event-calendar-event[^}]*font-size:12px/);
    expect(css).toMatch(/\.event-calendar-detail dd[^}]*font-size:13px/);
  });
});
