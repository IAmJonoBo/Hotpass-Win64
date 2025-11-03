export type HelpCategory =
  | "Getting Started"
  | "Import & Refinement"
  | "Monitoring & HIL"
  | "Troubleshooting"
  | "Governance & Compliance"
  | "Shortcuts & Productivity";

export interface HelpTopic {
  id: string;
  category: HelpCategory;
  title: string;
  summary: string;
  details: string;
  steps?: string[];
  docPath?: string;
  externalUrl?: string;
  keywords: string[];
  lastUpdated: string;
  relatedIds?: string[];
  highlight?: string;
}

export const helpTopics: HelpTopic[] = [
  {
    id: "getting-started-overview",
    category: "Getting Started",
    title: "Hotpass operator essentials",
    summary:
      "Understand the end-to-end workflow: refine, enrich, QA, and provenance checks before handoff.",
    details:
      "Operators begin every shift by running the guided wizard (`hotpass-operator wizard`) to refresh credentials, tunnels, and .env files, then step through refine → optional enrich → QA. Each stage emits telemetry to the timeline and lineage views so that provenance is always inspectable.",
    steps: [
      'Launch the operator wizard (`Assistant → "run operator wizard"` or CLI) to capture credentials, open tunnels, and write `.env.<target>`.',
      "Review the dashboard summary for failed or degraded runs.",
      "Open the Live Refinement panel for in-progress tasks and pending HIL reviews.",
      "Use the Help center search or the Assistant if a run requires deeper investigation.",
    ],
    docPath: "docs/how-to-guides/agentic-orchestration.md",
    keywords: [
      "overview",
      "workflow",
      "operator",
      "refine",
      "enrich",
      "qa",
      "provenance",
    ],
    lastUpdated: "2025-11-03",
    relatedIds: ["monitoring-hil-review", "import-bulk-datasets"],
    highlight: "Daily checklist",
  },
  {
    id: "import-bulk-datasets",
    category: "Import & Refinement",
    title: "Importing spreadsheets or zipped workbooks",
    summary:
      "Use the Import panel to drag-and-drop or browse for datasets, choose a profile, and monitor ingestion progress.",
    details:
      "Hotpass validates schema, profile assignment, and PII redaction on ingest. Operators can add contextual notes that flow into the activity log. Large uploads automatically resume if the connection drops.",
    steps: [
      "Drop files (.xlsx, .csv, .zip) or select them from your workstation.",
      "Select the matching profile (generic, aviation, compliance, etc.).",
      "Confirm metadata, then submit to trigger the refine pipeline.",
      "Monitor progress in the live timeline; HIL prompts appear when action is required.",
    ],
    docPath: "docs/how-to-guides/format-and-validate.md",
    keywords: [
      "import",
      "upload",
      "dataset",
      "drag and drop",
      "profile",
      "refine",
    ],
    lastUpdated: "2025-09-18",
    relatedIds: ["live-process-tracking", "import-accessibility"],
    highlight: "Supports drag & drop",
  },
  {
    id: "import-accessibility",
    category: "Import & Refinement",
    title: "Accessible import flow expectations",
    summary:
      "The import dialog follows WCAG guidance for keyboard shortcuts, focus order, and announcements for assistive tech.",
    details:
      "Screen reader instructions announce accepted file types, maximum size, and progress changes. Keyboard users can tab to the Browse button or hit Enter to open the file picker. Drag-and-drop is additive – dropping new files keeps any queued uploads.",
    keywords: [
      "accessibility",
      "wcag",
      "keyboard",
      "screen reader",
      "drag drop",
    ],
    docPath: "docs/docs/ai/AI_EVALUATION_PLAN.md",
    lastUpdated: "2025-07-29",
    relatedIds: ["import-bulk-datasets"],
  },
  {
    id: "live-process-tracking",
    category: "Monitoring & HIL",
    title: "Live process tracking and telemetry",
    summary:
      "Follow each run from ingest through QA with timestamps, statuses, and lineage badges.",
    details:
      "Runs stream into the Live Process feed as soon as Prefect registers them. Status chips reflect Prefect state, while the HIL column maps to operator approvals. Click a run to open full details or drill into lineage to see upstream/downstream impacts.",
    keywords: ["telemetry", "live", "status", "prefect", "timeline"],
    docPath: "docs/reference/cli.md",
    lastUpdated: "2025-09-22",
    relatedIds: ["monitoring-hil-review"],
    highlight: "Real-time updates",
  },
  {
    id: "monitoring-hil-review",
    category: "Monitoring & HIL",
    title: "Responding to HIL review requests",
    summary:
      "HIL requests surface in the dashboard, import timeline, and activity feed with context-rich reasoning.",
    details:
      "Every enrichment that flags a manual check routes to an approver. From the dashboard you can approve, request rework, or open provenance. Actions are logged to the audit trail and mirrored in the Prefect state.",
    docPath: "docs/compliance/remediation-backlog.md",
    externalUrl: undefined,
    steps: [
      "Locate the run with the Waiting badge in the Live Process section.",
      "Open provenance to inspect source assertions and timestamps.",
      "Approve or reject with a short comment; the workflow resumes automatically.",
    ],
    keywords: ["hil", "approval", "manual review", "audit"],
    lastUpdated: "2025-08-12",
  },
  {
    id: "gov-data-handling",
    category: "Governance & Compliance",
    title: "Data handling and retention guardrails",
    summary:
      "Hotpass enforces retention, access control, and PII scanning aligned with POPIA and SOC2.",
    details:
      "All uploads stay in encrypted object storage with lifecycle policies. Compliance dashboards surface outstanding remediation tasks and successful audits. Reference the remediation backlog for open items.",
    docPath: "docs/compliance/remediation-backlog.md",
    keywords: ["compliance", "pii", "retention", "popia", "soc2"],
    lastUpdated: "2025-10-10",
    relatedIds: ["import-bulk-datasets"],
  },
  {
    id: "troubleshooting-imports",
    category: "Troubleshooting",
    title: "Troubleshooting stalled imports",
    summary:
      "Common causes: schema mismatch, unsupported encoding, or upstream API throttling.",
    details:
      "Check the error banner for the failing file, then download the validation report. The Assistant can generate remediation steps based on the dataset schema. For API throttling, stagger retries or enable adaptive backoff.",
    steps: [
      "Review the validation report from the Live Process row.",
      "Fix the schema (column headers, types) or adjust the profile.",
      "Retry import; if the error persists escalate to the data engineering channel.",
    ],
    docPath: "docs/how-to-guides/dependency-profiles.md",
    keywords: ["error", "failed", "schema", "throttle", "retry"],
    lastUpdated: "2025-09-30",
    relatedIds: ["import-bulk-datasets", "monitoring-hil-review"],
    highlight: "Downloadable reports",
  },
  {
    id: "hotkeys-and-productivity",
    category: "Shortcuts & Productivity",
    title: "Keyboard shortcuts and assistant boosts",
    summary:
      "Speed up reviews with global search (`⌘K`), assistant handoff, operator wizard shortcuts, and batch provenance export.",
    details:
      "Use ⌘/Ctrl + Shift + F to focus the Help search, or press `.` on a run row to open actions. The assistant can now trigger the operator wizard (`run wizard`), open managed tunnels (`open tunnels host=…`), and generate `.env` files with cached credentials alongside traditional QA and lineage summaries.",
    keywords: ["shortcuts", "keyboard", "productivity", "assistant"],
    docPath: "docs/reference/cli.md",
    lastUpdated: "2025-11-03",
    relatedIds: ["help-shortcut"],
  },
] as const;

export const helpCategories: HelpCategory[] = [
  "Getting Started",
  "Import & Refinement",
  "Monitoring & HIL",
  "Governance & Compliance",
  "Troubleshooting",
  "Shortcuts & Productivity",
];
