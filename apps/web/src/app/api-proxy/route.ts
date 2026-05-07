import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const hopByHopHeaders = new Set([
  "accept-encoding",
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

const PROXY_TIMEOUT_MS = 30_000;

function backendBaseUrl() {
  const value =
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.BACKEND_API_BASE_URL ||
    process.env.BACKEND_URL ||
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "";
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    if (!url.pathname || url.pathname === "/") {
      url.pathname = "/api";
      return url.toString().replace(/\/+$/, "");
    }
  } catch {
    return trimmed;
  }
  return trimmed;
}

function targetPath(request: NextRequest) {
  const value = request.nextUrl.searchParams.get("target") || "";
  return value.startsWith("/") ? value : `/${value}`;
}

function proxyUrl(request: NextRequest) {
  const base = backendBaseUrl();
  const target = targetPath(request);
  if (target === "/__connection") return "__connection";
  const fallbackBase = `${request.nextUrl.origin}/api`;
  return `${base || fallbackBase}${target}`;
}

function forwardHeaders(request: NextRequest) {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (!hopByHopHeaders.has(lower)) {
      headers.set(key, value);
    }
  });
  return headers;
}

async function proxy(request: NextRequest) {
  const target = proxyUrl(request);
  if (target === "__connection") {
    return Response.json({
      configured: Boolean(backendBaseUrl()),
      base_url: backendBaseUrl() || null,
      message: backendBaseUrl()
        ? "前台已設定後端 API 連線位址。"
        : "前台尚未設定 API_BASE_URL，暫時會嘗試使用同網域 /api；建議在 Web 服務環境變數填入後端 API 網址，例如 https://your-api.zeabur.app/api。",
    });
  }

  const method = request.method.toUpperCase();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);
  const init: RequestInit = {
    method,
    headers: forwardHeaders(request),
    cache: "no-store",
    redirect: "manual",
    signal: controller.signal,
  };
  if (method !== "GET" && method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(target, init);
    const headers = new Headers();
    upstream.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!hopByHopHeaders.has(lower)) {
        headers.set(key, value);
      }
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  } catch (error) {
    const message = error instanceof DOMException && error.name === "AbortError"
      ? "前台代理連線後端 API 逾時，請確認 API_BASE_URL 指向正確的後端 /api 網址。"
      : `前台代理無法連到後端 API：${error instanceof Error ? error.message : String(error)}`;
    return Response.json({ detail: message }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(request: NextRequest) {
  return proxy(request);
}

export async function POST(request: NextRequest) {
  return proxy(request);
}

export async function PATCH(request: NextRequest) {
  return proxy(request);
}

export async function DELETE(request: NextRequest) {
  return proxy(request);
}
