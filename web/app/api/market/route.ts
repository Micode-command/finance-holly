import { API_URL } from "@/lib/api";

// 開休市狀態與開盤預估：依「現在時間」計算，不能快取
export async function GET() {
  const res = await fetch(`${API_URL}/api/market`);
  return Response.json(await res.json(), { status: res.status });
}
