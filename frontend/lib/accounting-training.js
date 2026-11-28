export function mastery(history, lesson, role) {
    const modes = new Set(history.filter(row => row.lesson_id === lesson.id && row.role === role && row.status === "passed" && row.curriculum_version === lesson.curriculum_version).map(row => row.mode));
    return { guided: modes.has("guided"), assisted: modes.has("assisted"), independent: modes.has("independent") };
}
export const trainingEnabled = process.env.NEXT_PUBLIC_ACCOUNTING_TRAINING === "1";
export function trainingOutcomeMatches(expected, actual) {
    actual = actual.split("?")[0];
    if (!expected.includes("*"))
        return expected === actual;
    const parts = expected.split("*");
    if (parts.length !== 2 || !actual.startsWith(parts[0]) || !actual.endsWith(parts[1]))
        return false;
    const id = actual.slice(parts[0].length, actual.length - parts[1].length);
    return /^[a-f0-9-]{36}$/.test(id);
}
export function trainingInspectionMatches(lesson, path) {
    if (!lesson?.inspection_api_path)
        return false;
    const [pathname, query = ""] = path.split("?");
    if (pathname !== lesson.inspection_api_path)
        return false;
    const params = new URLSearchParams(query);
    return Object.entries(lesson.inspection_query || {}).every(([key, value]) => params.get(key) === value);
}
