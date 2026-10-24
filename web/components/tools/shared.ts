// 互動工具共用：存取密碼型別、樣式、送出請求

export interface Access {
  passcode: string;
  /** 呼叫成功後才記住密碼 (避免記住打錯的密碼) */
  remember: () => void;
}

export const inputCls = "glass min-w-0 rounded-lg px-3 py-2.5 text-sm outline-none placeholder:text-muted focus:border-accent";
export const buttonCls = "rounded-lg bg-gradient-to-r from-accent to-accent-2 px-5 py-2.5 text-sm font-semibold text-page disabled:opacity-60";

/** 送出到後端；回傳 [body, 錯誤訊息] */
export async function postTool<T>(url: string, payload: object): Promise<[T | null, string | null]> {
  try {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const body = await res.json();
    return res.ok ? [body as T, null] : [null, body.detail ?? `查詢失敗 (${res.status})`];
  } catch (e) {
    return [null, `無法連線：${e}`];
  }
}
