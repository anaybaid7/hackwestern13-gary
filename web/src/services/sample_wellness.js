// A made-up week for the wellness view, so the page can show what it looks
// like before there is any real history. It is always shown with a
// "demo data" label. Nothing here came from a person.
export const SAMPLE_WELLNESS = {
  private: true,
  demo: true,
  checkins: [],
  pairs: [
    { day: '2026-11-16', before: 2, after: 3, change: 1, minutes: 25 },
    { day: '2026-11-17', before: 3, after: 3, change: 0, minutes: 15 },
    { day: '2026-11-19', before: 3, after: 4, change: 1, minutes: 40 },
    { day: '2026-11-21', before: 3, after: 4, change: 1, minutes: 55 },
  ],
  summary: 'You reported feeling better after 3 of 4 outings.',
  outdoor: [
    { day: '2026-11-16', minutes: 20 },
    { day: '2026-11-17', minutes: 10 },
    { day: '2026-11-19', minutes: 40 },
    { day: '2026-11-21', minutes: 50 },
  ],
  outdoor_minutes: 120,
  outdoor_note: "An estimate from Gary's sniffs: each 10-minute block with an outdoor find counts as 10 minutes outdoors.",
  finds: 14,
  shared: 5,
  solo: 9,
}
