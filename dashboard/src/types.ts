export type Verdict = "correct" | "unsafe" | "over_escalation";

export interface TraceStep {
  state: string;
  note: string;
}

export interface CaseRow {
  id: string;
  complaint: string;
  expected_action: string;
  expected_category: string;
  action: string;
  category: string | null;
  confidence: number | null;
  escalation_reason: string | null;
  draft_attempts: number;
  verifier_rejections: number;
  draft: string | null;
  verdict: Verdict;
  trace: TraceStep[];
}

export interface Run {
  model: string;
  cases: number;
  action_accuracy: number;
  category_accuracy_on_auto: number | null;
  automation_rate: number;
  unsafe_auto_decisions: number;
  over_escalations: number;
  fabricated_notes_shipped: number;
  verifier_rejections: number;
  fabrications_injected?: number;
  rows: CaseRow[];
}

export interface Report {
  runs: Run[];
}
