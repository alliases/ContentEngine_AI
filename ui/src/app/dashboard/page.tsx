// ui/src/app/dashboard/page.tsx

"use client";

import { useEffect, useState } from "react";
// Added EventSourceMessage for strict typing
import { fetchEventSource, EventSourceMessage } from "@microsoft/fetch-event-source";
import { API_BASE_URL, getAuthHeaders } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Enterprise Standard: Strict interface for the payload
interface TaskState {
  task_id: string;
  status: string;
  error?: string | null;
  result?: string | null;
}

export default function DashboardPage() {
  const [tasks, setTasks] = useState<Record<string, TaskState>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();

    const connectSSE = async () => {
      try {
        await fetchEventSource(`${API_BASE_URL}/tasks/stream`, {
          method: "GET",
          headers: getAuthHeaders() as Record<string, string>,
          signal: ctrl.signal,
          // Explicitly typing the standard fetch Response
          async onopen(response: Response) {
            if (response.ok && response.status === 200) {
              setError(null); // Clear previous errors on successful connection
              return;
            } else if (response.status >= 400 && response.status < 500 && response.status !== 429) {
              throw new Error(`Fatal Client Error: ${response.status}`);
            }
            throw new Error(`Server Error: ${response.status}`);
          },
          // Using library's specific EventSourceMessage type instead of implicitly 'any'
          onmessage(ev: EventSourceMessage) {
            if (ev.data) {
              const parsed = JSON.parse(ev.data);
              if (parsed.type === "initial") {
                const initialMap: Record<string, TaskState> = {};
                parsed.tasks.forEach((t: TaskState) => {
                  initialMap[t.task_id] = t;
                });
                setTasks(initialMap);
              } else {
                // Strict typing for the previous state updater
                setTasks((prev: Record<string, TaskState>) => ({
                  ...prev,
                  [parsed.task_id]: { ...prev[parsed.task_id], ...parsed },
                }));
              }
            }
          },
          // Strict error typing using 'unknown' standard
          onerror(err: unknown) {
            console.error("SSE Error:", err);
            if (err instanceof Error && err.message.includes("Fatal Client Error")) {
              setError("Authentication failed. Please log in again.");
              throw err;
            }
            setError("Connection lost. Reconnecting...");
          },
          onclose() {
            console.log("SSE Connection closed.");
          }
        });
      } catch (err: unknown) {
        console.error("Fetch Event Source setup failed", err);
      }
    };

    // Explicitly invoking the async function and voiding it to satisfy ESLint
    void connectSSE();

    return () => {
      ctrl.abort();
    };
  }, []);

  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <CardTitle>Content Generation Queue</CardTitle>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.values(tasks).map((task) => (
                <TableRow key={task.task_id}>
                  <TableCell className="font-medium text-xs">{task.task_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={task.status} />
                  </TableCell>
                  <TableCell className="text-red-500 text-xs">
                    {task.error || "-"}
                  </TableCell>
                </TableRow>
              ))}
              {Object.keys(tasks).length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-gray-500 py-4">
                    No active tasks.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
