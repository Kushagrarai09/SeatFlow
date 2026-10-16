"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CalendarDays, MapPin, Ticket, UserRound } from "lucide-react";
import { apiRequest, EventRecord, ReservationRecord, TicketCategoryRecord, VenueRecord } from "@/lib/api";

type SavedTokens = { access_token: string; refresh_token: string };

function displayDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "full", timeStyle: "short" }).format(new Date(value));
}

export default function EventDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const [eventId, setEventId] = useState("");
  const [event, setEvent] = useState<EventRecord | null>(null);
  const [venue, setVenue] = useState<VenueRecord | null>(null);
  const [tickets, setTickets] = useState<TicketCategoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [tokens, setTokens] = useState<SavedTokens | null>(null);
  const [selectedTicket, setSelectedTicket] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [busy, setBusy] = useState(false);
  const [reservation, setReservation] = useState<ReservationRecord | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => { params.then(({ id }) => setEventId(id)); }, [params]);

  useEffect(() => {
    if (!eventId) return;
    let active = true;
    setLoading(true);
    Promise.all([
      apiRequest<EventRecord>(`/api/v1/events/${eventId}`),
      apiRequest<VenueRecord[]>(`/api/v1/venues?limit=100`),
      apiRequest<TicketCategoryRecord[]>(`/api/v1/events/${eventId}/ticket-categories`),
    ]).then(([eventData, venues, ticketData]) => {
      if (!active) return;
      setEvent(eventData);
      setVenue(venues.find((item) => item.id === eventData.venue_id) ?? null);
      setTickets(ticketData);
      setSelectedTicket(ticketData.find((ticket) => ticket.sales_open && ticket.available_quantity >= ticket.min_per_order)?.id ?? null);
      setError("");
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Could not load this event.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [eventId]);

  useEffect(() => {
    const saved = window.localStorage.getItem("seatflow_tokens");
    if (saved) {
      try { setTokens(JSON.parse(saved) as SavedTokens); } catch { window.localStorage.removeItem("seatflow_tokens"); }
    }
  }, []);

  async function handleAuth(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (isRegister) await apiRequest("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, full_name: fullName, password }) });
      const result = await apiRequest<SavedTokens>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      window.localStorage.setItem("seatflow_tokens", JSON.stringify(result));
      setTokens(result); setNotice(isRegister ? "Account created and signed in." : "Signed in successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally { setBusy(false); }
  }

  async function createHold() {
    if (!selectedTicket) { setError("Choose an available ticket category first."); return; }
    if (!tokens) { setError("Sign in before reserving tickets."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const key = `seatflow-${crypto.randomUUID()}`;
      const created = await apiRequest<ReservationRecord>("/api/v1/reservations", {
        method: "POST", headers: { "Idempotency-Key": key },
        body: JSON.stringify({ ticket_category_id: selectedTicket, quantity }),
      }, tokens.access_token);
      setReservation(created);
      setNotice(`Hold created. It expires at ${new Date(created.expires_at).toLocaleTimeString()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reserve tickets.");
    } finally { setBusy(false); }
  }

  async function confirmHold() {
    if (!reservation || !tokens) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const confirmed = await apiRequest<ReservationRecord>(`/api/v1/reservations/${reservation.id}/confirm`, { method: "POST" }, tokens.access_token);
      setReservation(confirmed); setNotice("Reservation confirmed. Payment is not integrated in this phase.");
      const refreshed = await apiRequest<TicketCategoryRecord[]>(`/api/v1/events/${eventId}/ticket-categories`);
      setTickets(refreshed);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not confirm reservation."); }
    finally { setBusy(false); }
  }

  async function cancelHold() {
    if (!reservation || !tokens) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const cancelled = await apiRequest<ReservationRecord>(`/api/v1/reservations/${reservation.id}/cancel`, { method: "POST" }, tokens.access_token);
      setReservation(cancelled); setNotice(`Reservation status: ${cancelled.status}.`);
      const refreshed = await apiRequest<TicketCategoryRecord[]>(`/api/v1/events/${eventId}/ticket-categories`);
      setTickets(refreshed);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not cancel reservation."); }
    finally { setBusy(false); }
  }

  const selected = tickets.find((ticket) => ticket.id === selectedTicket) ?? null;
  const maxAvailable = selected ? Math.min(selected.max_per_order, selected.available_quantity) : 0;

  return (
    <main style={{ minHeight: "100vh", background: "var(--paper)", color: "var(--ink)" }}>
      <header style={{ padding: "24px 6%", borderBottom: "1px solid var(--line)" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 10, fontWeight: 700 }}><ArrowLeft size={17} /> Back to SeatFlow</Link>
      </header>
      <section style={{ maxWidth: 980, margin: "0 auto", padding: "48px 24px 80px" }}>
        {loading && <p role="status">Loading event details…</p>}
        {!loading && error && !event && <p role="alert">{error}</p>}
        {!loading && event && <>
          <p style={{ color: "var(--muted)", fontSize: 12, letterSpacing: ".1em" }}>SEATFLOW EVENT / {event.category.toUpperCase()}</p>
          <h1 style={{ font: "600 clamp(36px, 6vw, 60px)/1.05 var(--display)", letterSpacing: "-.05em", margin: "16px 0" }}>{event.title}</h1>
          {event.description && <p style={{ maxWidth: 680, lineHeight: 1.8, color: "var(--muted)" }}>{event.description}</p>}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 18, margin: "24px 0 36px", color: "var(--muted)", fontSize: 14 }}>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}><CalendarDays size={16} /> {displayDate(event.starts_at)}</span>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}><MapPin size={16} /> {venue ? `${venue.name}, ${venue.city}` : "Venue to be announced"}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 28, alignItems: "start" }}>
            <section style={{ padding: 24, background: "white", border: "1px solid var(--line)" }}>
              <h2 style={{ font: "600 24px var(--display)", marginTop: 0 }}>Choose your ticket</h2>
              {tickets.length === 0 && <p>No active ticket categories are available for this event.</p>}
              {tickets.map((ticket) => {
                const canBuy = ticket.sales_open && ticket.available_quantity >= ticket.min_per_order;
                return <label key={ticket.id} style={{ display: "flex", gap: 12, padding: "16px 0", borderBottom: "1px solid var(--line)", cursor: canBuy ? "pointer" : "not-allowed", opacity: canBuy ? 1 : .55 }}>
                  <input type="radio" name="ticket" checked={selectedTicket === ticket.id} disabled={!canBuy || Boolean(reservation && reservation.status === "pending")} onChange={() => { setSelectedTicket(ticket.id); setQuantity(ticket.min_per_order); }} />
                  <span style={{ flex: 1 }}><strong style={{ display: "block" }}>{ticket.name}</strong><small>{ticket.available_quantity} available · {canBuy ? "Sales open" : "Unavailable"}</small></span>
                  <strong>₹{Number(ticket.price).toLocaleString("en-IN")}</strong>
                </label>;
              })}
              {selected && !reservation && <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginTop: 20 }}>
                <label htmlFor="quantity">Quantity</label>
                <select id="quantity" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} style={{ padding: 9 }}>
                  {Array.from({ length: Math.max(0, maxAvailable - selected.min_per_order + 1) }, (_, i) => selected.min_per_order + i).map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>}
              {selected && <p style={{ fontWeight: 700 }}>Total: ₹{(Number(selected.price) * quantity).toLocaleString("en-IN")}</p>}
              {!reservation && <button className="button-primary" disabled={busy || !selected?.sales_open || !selected || selected.available_quantity < selected.min_per_order} onClick={createHold} style={{ border: 0, width: "100%", cursor: busy ? "wait" : "pointer", marginTop: 12 }}>{busy ? "Working…" : "Reserve tickets"} <Ticket size={16} /></button>}
              {reservation && <div style={{ marginTop: 20, padding: 16, background: "#f4f2e9" }}>
                <strong>Reservation #{reservation.id} · {reservation.status.toUpperCase()}</strong>
                <p>Quantity: {reservation.quantity} · Total: ₹{Number(reservation.total_price).toLocaleString("en-IN")}</p>
                {reservation.status === "pending" && <p>Hold expires: {new Date(reservation.expires_at).toLocaleString()}</p>}
                {reservation.status === "pending" && <button className="button-primary" disabled={busy} onClick={confirmHold} style={{ border: 0, marginRight: 8 }}>Confirm reservation</button>}
                {(reservation.status === "pending" || reservation.status === "confirmed") && <button disabled={busy} onClick={cancelHold} style={{ padding: "12px 16px", marginTop: 8 }}>Cancel reservation</button>}
              </div>}
            </section>
            <section style={{ padding: 24, border: "1px solid var(--line)" }}>
              <h2 style={{ font: "600 24px var(--display)", marginTop: 0 }}><UserRound size={20} style={{ verticalAlign: "middle", marginRight: 8 }} />Your account</h2>
              {tokens ? <><p>You are signed in. You can create a temporary ticket hold.</p><button onClick={() => { window.localStorage.removeItem("seatflow_tokens"); setTokens(null); setReservation(null); setNotice("Signed out on this device."); }} style={{ padding: "12px 16px" }}>Sign out</button></> : <form onSubmit={handleAuth} style={{ display: "grid", gap: 12 }}>
                {isRegister && <label>Full name<input required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} style={{ display: "block", width: "100%", padding: 12, marginTop: 5 }} /></label>}
                <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={{ display: "block", width: "100%", padding: 12, marginTop: 5 }} /></label>
                <label>Password<input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} style={{ display: "block", width: "100%", padding: 12, marginTop: 5 }} /></label>
                <button className="button-primary" disabled={busy} type="submit" style={{ border: 0 }}>{busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}</button>
                <button type="button" onClick={() => setIsRegister((value) => !value)} style={{ padding: 10, border: 0, background: "transparent", textDecoration: "underline", cursor: "pointer" }}>{isRegister ? "Already registered? Sign in" : "New here? Create an account"}</button>
              </form>}
            </section>
          </div>
          {error && <p role="alert" style={{ color: "#b42318", marginTop: 20 }}>{error}</p>}
          {notice && <p role="status" style={{ color: "#27723b", marginTop: 20 }}>{notice}</p>}
          <p style={{ marginTop: 32, color: "var(--muted)", fontSize: 12 }}>Development note: confirming a reservation updates ticket inventory. Payment processing is not connected yet.</p>
        </>}
      </section>
    </main>
  );
}
