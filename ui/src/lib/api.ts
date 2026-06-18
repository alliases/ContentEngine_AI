//ui/src/lib/api.ts

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://alliases.duckdns.org/ContentEngine/api/v1";
// export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8110/api/v1";

export function getAuthHeaders(): HeadersInit {
  // In a real app, retrieve this from localStorage or NextAuth session
  const token = typeof window !== 'undefined' ? localStorage.getItem("jwt_token") : null;
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}
