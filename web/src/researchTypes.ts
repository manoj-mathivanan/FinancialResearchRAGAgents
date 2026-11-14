// The fields consumed by React from the JSON returned by POST /api/ask.
export type FilingInput = {
  period_end: string;
  value: string;
  unit?: string;
  source: { url: string; row?: string; section?: string };
};
export type Citation =
  | { type: "filing_calculation"; inputs: { prior: FilingInput; current: FilingInput } }
  | { type: "reported_fact"; input: FilingInput }
  | { type?: undefined; source_url: string; pdf_page: number; transcript_page: number; period_end: string };

type SearchStep = { query: string; pdf_pages: number[] };
export type Answer = {
  status: "answered" | "partial" | "insufficient_evidence";
  claims: { text: string; source_ids: string[] }[];
  sources: Record<string, Citation>;
  gaps: string[];
  route?: { period_end?: string | null; metric?: string | null; transcript_query?: string | null };
  assignment?: { period_end?: string | null; financial_task?: string | null; management_task?: string | null };
  financial_tools?: { tool: string; metric: string; gap?: string }[];
  transcript_searches?: SearchStep[];
};

export function formatQuarter(date: string) {
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(date + "T00:00:00Z"));
}

export function answerQuarter(answer: Answer) {
  return answer.assignment?.period_end ?? answer.route?.period_end ?? null;
}
