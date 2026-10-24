import { API_URL } from "@/lib/api";

export async function POST() {
  const res = await fetch(`${API_URL}/api/refresh`, { method: "POST" });
  return Response.json(await res.json(), { status: res.status });
}
