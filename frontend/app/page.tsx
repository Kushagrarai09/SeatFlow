"use client";

import { useEffect, useState } from "react";
import {
  ArrowRight, CalendarDays, MapPin, Menu, Music2, Palette, Sparkles,
  Ticket, Trophy, Users, X,
} from "lucide-react";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

type LiveEvent = {
  id: number;
  title: string;
  category: string;
  description?: string | null;
  starts_at: string;
  ends_at: string;
  price: string | number;
  venue_id: number;
  venueName: string;
  city: string;
};

const eventArtwork = [
  { theme: "event-coral", icon: Music2, tag: "LIVE EXPERIENCE", art: "FEEL\\nEVERYTHING" },
  { theme: "event-lilac", icon: Palette, tag: "FIND SOMETHING NEW", art: "LOOK\\nCLOSER" },
  { theme: "event-lime", icon: Trophy, tag: "MADE FOR YOU", art: "THINK\\nTOGETHER" },
];

function formatEventDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "DATE TO BE ANNOUNCED";
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", month: "short", day: "numeric" }).format(date).toUpperCase();
}

const categories = [
  { label:"Live music", icon:Music2, description:"For the main-character moments" },
  { label:"Art & culture", icon:Palette, description:"See something differently" },
  { label:"Meet people", icon:Users, description:"Find your kind of crowd" },
  { label:"Something new", icon:Sparkles, description:"Take the scenic route" },
];

type ApiStatus = "checking" | "online" | "offline";

export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 3500);
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        return response.json();
      })
      .then((data: { status?: string }) => setApiStatus(data.status === "ok" ? "online" : "offline"))
      .catch(() => setApiStatus("offline"))
      .finally(() => window.clearTimeout(timeoutId));
    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setEventsLoading(true);
    Promise.all([
      fetch(`${API_URL}/api/v1/events?limit=12`, { signal: controller.signal }),
      fetch(`${API_URL}/api/v1/venues?limit=100`, { signal: controller.signal }),
    ])
      .then(async ([eventsResponse, venuesResponse]) => {
        if (!eventsResponse.ok || !venuesResponse.ok) throw new Error("Could not load live events.");
        const liveEvents = await eventsResponse.json();
        const venues = await venuesResponse.json();
        const venueById = new Map<number, { name: string; city: string }>(
          venues.map((venue: { id: number; name: string; city: string }) => [venue.id, venue] as const),
        );
        setEvents(liveEvents.map((event: Omit<LiveEvent, "venueName" | "city">) => ({
          ...event,
          venueName: venueById.get(event.venue_id)?.name ?? "Venue to be announced",
          city: venueById.get(event.venue_id)?.city ?? "",
        })));
        setEventsError("");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setEventsError(error instanceof Error ? error.message : "Could not load live events.");
      })
      .finally(() => setEventsLoading(false));
    return () => controller.abort();
  }, []);

  return (
    <main>
      <div className="announcement-bar"><span className="announcement-dot" aria-hidden="true" /><span>YOUR NEXT STORY STARTS HERE</span><span className="announcement-divider">✳</span><span className="announcement-secondary">Meet the new way to make plans.</span></div>
      <header className="site-header">
        <a className="brand" href="#home" aria-label="SeatFlow home"><span className="brand-mark"><Ticket size={19} strokeWidth={2.6} /></span><span>seatflow<span className="brand-period">.</span></span></a>
        <nav className={menuOpen ? "main-nav nav-open" : "main-nav"} aria-label="Main navigation">
          <a href="#discover" onClick={() => setMenuOpen(false)}>Discover</a><a href="#categories" onClick={() => setMenuOpen(false)}>Experiences</a><a href="#about" onClick={() => setMenuOpen(false)}>How it works</a>
        </nav>
        <div className="header-actions"><a className="organizer-link" href="#organizers">Host an event <span aria-hidden="true">↗</span></a><a className="header-cta" href="#discover">Find your plans <ArrowRight size={15} /></a></div>
        <button className="menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? <X size={23} /> : <Menu size={23} />}</button>
      </header>
      <section className="hero" id="home">
        <div className="hero-left">
          <div className="eyebrow"><span className="eyebrow-star">✳</span> LESS SCROLLING, MORE LIVING</div>
          <h1>Life happens<br />when you <span className="scribble-word">show up<span className="scribble-underline" /></span><span className="hero-spark">✳</span></h1>
          <p className="hero-copy">The gig you can’t stop talking about. The pop-up you stumble into. The people you didn’t know you needed to meet. It’s all out there.</p>
          <div className="hero-buttons"><a className="button-primary" href="#discover">Find your next thing <ArrowRight size={17} /></a><a className="button-quiet" href="#about"><span className="play-icon">▶</span> How SeatFlow works</a></div>
          <div className="hero-social-proof"><div className="avatar-stack" aria-hidden="true"><span>AR</span><span>MK</span><span>SP</span><span>✳</span></div><div><strong>Good plans. Great people.</strong><small>Built for your out-of-office era.</small></div></div>
          <div className="hero-bottom-note"><span className="note-line" /> NO FOMO. JUST FLOW.</div>
        </div>
        <div className="hero-art" aria-label="Illustrated SeatFlow event collage" role="img">
          <div className="art-grid" /><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-sun">✳</div>
          <div className="art-title-card"><span>GOOD THINGS<br />HAPPEN OUTSIDE</span><small>SEATFLOW FIELD NOTES · VOL. 001</small></div>
          <div className="art-ticket art-ticket-one"><span>SF / 014</span><Music2 size={29} /><strong>AFTER<br />HOURS</strong><small>ENTRY FOR A GOOD TIME</small></div>
          <div className="art-ticket art-ticket-two"><span>MAKE ROOM FOR</span><strong>THE<br />UNEXPECTED<span className="ticket-star">✳</span></strong><small>NEW PLACES. NEW FACES.</small></div>
          <div className="art-disc"><div className="disc-center">sf<span>.</span></div></div><div className="art-doodle">↗</div><div className="art-caption"><span>FIG. 01</span><span>AN EVENING WELL SPENT</span></div><div className="art-side-label">COLLECT MOMENTS / NOT TABS</div>
        </div>
        <div className="hero-bottom-strip"><span>GOOD PLANS ONLY</span><span>✳</span><span>REAL PEOPLE, REAL PLACES</span><span>✳</span><span>MAKE IT A STORY</span><span>✳</span><span>GOOD PLANS ONLY</span></div>
      </section>
      <section className="discover-section" id="discover">
        <div className="section-heading-row"><div><div className="eyebrow"><span className="eyebrow-star">↘</span> THE GOOD STUFF</div><h2>Plans worth<br className="mobile-break" /> <span>leaving home for.</span></h2></div><a href="#categories" className="text-link">Browse experiences <ArrowRight size={16} /></a></div>
        {eventsLoading && <p className="demo-note" role="status">Loading live events from SeatFlow…</p>}
        {!eventsLoading && eventsError && <p className="demo-note" role="alert">{eventsError} Make sure the backend and database are running.</p>}
        {!eventsLoading && !eventsError && events.length === 0 && <p className="demo-note">No published events are available yet. An organizer can publish an event through the API, and it will appear here.</p>}
        <div className="events-grid">
          {events.map((event, index) => {
            const artwork = eventArtwork[index % eventArtwork.length];
            const EventIcon = artwork.icon;
            return (
              <article className={`event-card ${artwork.theme}`} key={event.id}>
                <div className="event-artwork"><div className="event-art-top"><span>{event.category.toUpperCase()}</span><span className="event-number">/ {String(event.id).padStart(2, "0")}</span></div><span className="event-tag">{artwork.tag}</span><div className="event-symbol"><EventIcon size={72} strokeWidth={1.2} /></div><div className="event-artword">{artwork.art}</div><span className="event-art-corner">SF✳</span></div>
                <div className="event-info"><div className="event-date"><CalendarDays size={13} /> {formatEventDate(event.starts_at)}</div><h3>{event.title}</h3><p className="event-venue"><MapPin size={14} /> {event.venueName}{event.city ? ` · ${event.city}` : ""}</p><div className="event-card-footer"><span>From ₹{Number(event.price).toLocaleString("en-IN")}</span><a href={`/events/${event.id}`} aria-label={`View tickets for ${event.title}`}><ArrowRight size={17} /></a></div></div>
              </article>
            );
          })}
        </div>
      </section>
      <section className="category-section" id="categories">
        <div className="category-intro"><div className="eyebrow"><span className="eyebrow-star">✳</span> YOUR KIND OF OUT</div><h2>What are you<br />in the mood <span>for?</span></h2><p>There’s no wrong answer. Except staying in because you couldn’t decide.</p></div>
        <div className="category-list">{categories.map((category, index) => { const CategoryIcon = category.icon; return <a href="#discover" className="category-row" key={category.label}><span className="category-number">0{index + 1}</span><span className="category-icon"><CategoryIcon size={20} /></span><span className="category-copy"><strong>{category.label}</strong><small>{category.description}</small></span><ArrowRight className="category-arrow" size={20} /></a>; })}</div>
      </section>
      <section className="about-section" id="about">
        <div className="about-topline"><span>THE SEATFLOW WAY</span><span>LESS PLANNING, MORE DOING ✳</span></div>
        <div className="about-content"><span className="about-sticker">MAKE<br />MEMORIES<br /><span>↘</span></span><div><h2>Good plans<br />should feel <span>easy.</span></h2><p>We’re building a calmer way to discover experiences and a more dependable way to book your spot. Less noise, more of the things that make a day memorable.</p><a className="button-light" href="#discover">Explore the preview <ArrowRight size={16} /></a></div></div>
        <div className="about-values"><div><span>01 / DISCOVER</span><strong>Find your next yes.</strong><small>Explore events by interest and place.</small></div><div><span>02 / BOOK</span><strong>Your seat, sorted.</strong><small>Reliable booking is on the roadmap.</small></div><div><span>03 / SHOW UP</span><strong>Be where it happens.</strong><small>Keep the good part of making plans.</small></div></div>
      </section>
      <section className="organizer-section" id="organizers"><div><div className="eyebrow"><span className="eyebrow-star">↗</span> FOR THE PEOPLE WHO MAKE IT HAPPEN</div><h2>Got a good thing<br />going <span>on?</span></h2><p>We’re building tools to help event hosts bring the right people together.</p></div><a className="button-primary" href="mailto:hello@seatflow.example?subject=SeatFlow%20organizer%20interest">I’m an organizer <ArrowRight size={16} /></a></section>
      <footer className="site-footer"><a className="brand footer-brand" href="#home"><span className="brand-mark"><Ticket size={18} strokeWidth={2.6} /></span><span>seatflow<span className="brand-period">.</span></span></a><p>Find the thing. Feel the thing. Remember the thing.</p><div className="footer-status" id="phase-status"><span className={`status-light status-${apiStatus}`} /> API {apiStatus === "checking" ? "CHECKING" : apiStatus === "online" ? "CONNECTED" : "NOT CONNECTED"} <span className="footer-phase">· LIVE EVENT FEED</span></div><a className="back-top" href="#home">BACK TO TOP ↑</a></footer>
    </main>
  );
}
