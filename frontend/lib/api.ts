export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export type EventRecord = {
  id: number;
  organizer_id: number;
  venue_id: number;
  title: string;
  description: string | null;
  category: string;
  starts_at: string;
  ends_at: string;
  price: string | number;
  capacity: number;
  status: string;
};

export type VenueRecord = {
  id: number;
  name: string;
  address: string;
  city: string;
  country: string;
  capacity: number;
};

export type TicketCategoryRecord = {
  id: number;
  event_id: number;
  name: string;
  description: string | null;
  price: string | number;
  total_quantity: number;
  sold_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  min_per_order: number;
  max_per_order: number;
  sales_open: boolean;
  status: string;
};

export type ReservationRecord = {
  id: number;
  user_id: number;
  ticket_category_id: number;
  quantity: number;
  unit_price: string | number;
  total_price: string | number;
  status: "pending" | "confirmed" | "cancelled" | "expired";
  expires_at: string;
};

export type AuthTokens = { access_token: string; refresh_token: string; token_type: string };

export async function apiRequest<T>(path: string, options: RequestInit = {}, accessToken?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      const detail = body?.detail;
      message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).join(", ") : message;
    } catch { /* response body was not JSON */ }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
