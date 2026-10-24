import { API_URL } from "@/lib/api";

// 個股健檢：轉發到 Python 後端，並帶上訪客 IP (後端用來計算每人使用次數)
export async function POST(request: Request) {
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const res = await fetch(`${API_URL}/api/stock-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-client-ip": ip },
    body: await request.text(),
  });
  return Response.json(await res.json(), { status: res.status });
}
