Visual QA focus for `/events/calendar`:

1. Empty month should render as a white/light calendar grid, never a solid green tile matrix.
2. Today should be the only date with a filled green circle in an otherwise neutral day cell.
3. Selected day should use a light green tint and thin inset outline, not a dark fill.
4. Event rows should appear as compact light strips with a narrow status-colored edge.
5. KPI strip and toolbar should remain visually secondary to the month grid.
6. Inspector should not dominate the page when the selected day has no events.
