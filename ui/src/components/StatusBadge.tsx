// ui/src/components/StatusBadge.tsx

import { Badge } from "@/components/ui/badge";

export function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    PENDING: "bg-gray-500",
    PROCESSING: "bg-blue-500",
    WRITING: "bg-indigo-500",
    REVIEWING: "bg-purple-500",
    APPROVED_BY_AI: "bg-green-500 text-white",
    RENDERING: "bg-yellow-500",
    NEEDS_REVISION: "bg-orange-500 text-white",
    FALLBACK: "bg-red-500 text-white",
  };

  const className = colorMap[status] || "bg-gray-500";
  return <Badge className={className}>{status}</Badge>;
}
