// One column template for the list header AND every row (CSS grid), so the
// columns line up whatever the content: priority, from, subject, received.
// (Story 3.6 moved the priority dropdown into the reading pane: no "change" column.)
// From the `sm` breakpoint up; narrow screens use a wrapping two-line row instead.
// (A full class string, so Tailwind can find it when it scans the source.)
export const COLUMNS = 'sm:grid-cols-[10rem_11rem_minmax(0,1fr)_4.5rem]'
