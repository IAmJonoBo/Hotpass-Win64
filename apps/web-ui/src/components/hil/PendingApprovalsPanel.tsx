import { useMemo } from "react";
import { formatDistanceToNow } from "date-fns";
import { Link } from "react-router-dom";
import { AlertCircle, Clock, MessageSquare, UserCheck } from "lucide-react";
import type { HILApproval, PrefectFlowRun } from "@/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface PendingApprovalsPanelProps {
  approvals: Record<string, HILApproval>;
  runs: PrefectFlowRun[];
  isLoading?: boolean;
  onOpenAssistant?: (message?: string) => void;
  className?: string;
}

type PendingApprovalEntry = {
  approval: HILApproval;
  run?: PrefectFlowRun;
};

const MAX_DISPLAY = 6;

export function PendingApprovalsPanel({
  approvals,
  runs,
  isLoading = false,
  onOpenAssistant,
  className,
}: PendingApprovalsPanelProps) {
  const waitingEntries = useMemo<PendingApprovalEntry[]>(() => {
    const entries = Object.values(approvals).filter(
      (entry) => entry.status === "waiting",
    );
    entries.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
    return entries.slice(0, MAX_DISPLAY).map((entry) => ({
      approval: entry,
      run: runs.find((run) => run.id === entry.runId),
    }));
  }, [approvals, runs]);

  const totalWaiting = useMemo(
    () =>
      Object.values(approvals).filter((entry) => entry.status === "waiting")
        .length,
    [approvals],
  );
  const totalApproved = useMemo(
    () =>
      Object.values(approvals).filter((entry) => entry.status === "approved")
        .length,
    [approvals],
  );
  const totalRejected = useMemo(
    () =>
      Object.values(approvals).filter((entry) => entry.status === "rejected")
        .length,
    [approvals],
  );

  return (
    <Card
      className={cn(
        "h-full rounded-3xl border border-border/80 bg-card/90 shadow-sm",
        className,
      )}
    >
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <UserCheck className="h-4 w-4 text-primary" aria-hidden="true" />
          Pending approvals
        </CardTitle>
        <CardDescription>
          Manual reviews waiting on an operator decision. Open Run Details to
          see full QA context.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-xl border border-border/60 bg-background/80 px-3 py-2">
            <p className="font-semibold text-foreground">{totalWaiting}</p>
            <p className="text-muted-foreground">Waiting</p>
          </div>
          <div className="rounded-xl border border-border/60 bg-background/80 px-3 py-2">
            <p className="font-semibold text-foreground">{totalApproved}</p>
            <p className="text-muted-foreground">Approved (24h)</p>
          </div>
          <div className="rounded-xl border border-border/60 bg-background/80 px-3 py-2">
            <p className="font-semibold text-foreground">{totalRejected}</p>
            <p className="text-muted-foreground">Rejected (24h)</p>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-16 rounded-2xl" />
            ))}
          </div>
        ) : waitingEntries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/30 p-4 text-xs text-muted-foreground">
            No approvals waiting on you right now. Completed decisions will
            appear here for 24 hours.
          </div>
        ) : (
          <ul className="space-y-3">
            {waitingEntries.map(({ approval, run }) => {
              const runName = run?.name ?? approval.runId;
              const profile =
                typeof run?.parameters?.profile === "string"
                  ? run.parameters.profile
                  : null;
              const comment =
                approval.comment ||
                run?.parameters?.notes ||
                run?.parameters?.comment;
              const timestamp = Date.parse(approval.timestamp);
              return (
                <li
                  key={approval.id}
                  className="rounded-2xl border border-border/60 bg-background/90 p-4 text-xs shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p
                        className="truncate text-sm font-semibold text-foreground"
                        title={runName}
                      >
                        {runName}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3 w-3" aria-hidden="true" />
                          {Number.isNaN(timestamp)
                            ? "timestamp unknown"
                            : formatDistanceToNow(
                                new Date(approval.timestamp),
                                { addSuffix: true },
                              )}
                        </span>
                        {profile && (
                          <Badge
                            variant="secondary"
                            className="rounded-full px-2 py-0.5 text-[10px] uppercase"
                          >
                            {profile}
                          </Badge>
                        )}
                        {approval.operator && (
                          <span className="inline-flex items-center gap-1">
                            <UserCheck className="h-3 w-3" aria-hidden="true" />
                            {approval.operator}
                          </span>
                        )}
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className="border-yellow-500/40 text-yellow-700 dark:text-yellow-400"
                    >
                      Waiting
                    </Badge>
                  </div>
                  {typeof comment === "string" && comment && (
                    <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">
                      “{comment}”
                    </p>
                  )}
                  {comment && typeof comment !== "string" && (
                    <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">
                      “{JSON.stringify(comment)}”
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Link to={`/runs/${approval.runId}?hil=1`}>
                      <Button variant="default" size="sm">
                        Open Run
                      </Button>
                    </Link>
                    {onOpenAssistant && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          onOpenAssistant(
                            `Help me prepare approval notes for run ${approval.runId}. Current comment: ${comment ?? "None provided"}.`,
                          )
                        }
                      >
                        <MessageSquare className="mr-1 h-3 w-3" />
                        Ask assistant
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {waitingEntries.length > 0 && waitingEntries.length === MAX_DISPLAY && (
          <div className="rounded-xl border border-border/60 bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
            Showing the {MAX_DISPLAY} most recent requests. Older approvals
            remain available in Run Details.
          </div>
        )}

        <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-[11px] text-muted-foreground">
          <AlertCircle className="h-3 w-3 text-primary" aria-hidden="true" />
          Decisions sync back to Prefect automatically. Use Run Details for full
          QA breakdowns before approving.
        </div>
      </CardContent>
    </Card>
  );
}
