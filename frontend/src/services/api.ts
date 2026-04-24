const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * 백엔드 API 호출 래퍼
 * CRITICAL: 모든 외부 API 호출은 백엔드를 통해서만 수행
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * 헬스체크 API
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
  return apiFetch("/api/health");
}
