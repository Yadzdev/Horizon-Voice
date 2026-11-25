import { http, HttpRequest, HttpRequestMethod, HttpHeader } from "@minecraft/server-net";

export const API_BASE = "https://voice-horizon.online/api/v1";
const SERVER_SECRET_KEY = "horizonvoice:server_secret";

export function getServerSecret(world) {
  const value = world.getDynamicProperty(SERVER_SECRET_KEY);
  return typeof value === "string" && value.length > 24 ? value : null;
}

export function saveServerSecret(world, secret) {
  world.setDynamicProperty(SERVER_SECRET_KEY, secret);
}

export async function apiRequest(path, { method = HttpRequestMethod.Post, body, serverSecret } = {}) {
  const request = new HttpRequest(`${API_BASE}${path}`);
  request.method = method;
  request.timeout = 8;
  const headers = [new HttpHeader("Accept", "application/json")];
  if (body !== undefined) {
    request.body = JSON.stringify(body);
    headers.push(new HttpHeader("Content-Type", "application/json"));
  }
  if (serverSecret) headers.push(new HttpHeader("X-Server-Key", serverSecret));
  request.headers = headers;

  const response = await http.request(request);
  let data = {};
  try { data = JSON.parse(response.body || "{}"); } catch { /* API error body will be handled below. */ }
  if (response.status < 200 || response.status >= 300) {
    const message = typeof data.detail === "string" ? data.detail : `API respondeu HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}
