import { API_URL } from "@/lib/api";

// 轉發到 Python 後端；Gemini 回應可能要 20-40 秒
export async function POST() {
  const res = await fetch(`${API_URL}/api/ai`, { method: "POST" });
  return Response.json(await res.json(), { status: res.status });
}
