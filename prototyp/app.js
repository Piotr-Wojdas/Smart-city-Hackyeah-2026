// Klikalny prototyp Netless. Bez frameworka i bez budowania: ekrany to funkcje zwracające HTML,
// adres ekranu jest w hashu (#/<wariant>/<ekran>), więc działa przycisk „wstecz” przeglądarki.
// Wszystkie dane są fikcyjne i nic nie jest nigdzie wysyłane.

const VARIANTS = ["netless", "mobywatel"];
const START = { netless: "home", mobywatel: "shell" };
// ekran nadrzędny: dokąd prowadzi strzałka „wstecz”, gdy nie ma historii (np. po wejściu z linku)
const PARENT = {
  messages: "home",
  chat: "messages",
  notice: "home",
  report: "home",
  guides: "home",
  guide: "guides",
  assistant: "home",
  mdowod: "shell",
};

const state = {
  variant: "netless",
  screen: "home",
  depth: 0,
  messagesFilter: "all",
  guidesFilter: "all",
  guidesQuery: "",
  incidentType: "water",
  noticeSaved: false,
  guideSaved: true,
  chatRead: false,
  chat: [
    { from: "me", text: "The haystack is still smouldering in Lipinki Łużyckie. There is still smoke.", meta: "09:05 • Sent" },
    { from: "them", text: "Report BL-024 received. Is anyone at risk? Please stay away from the fire.", meta: "Fire service • 09:12" },
    { from: "me", text: "I cannot see anyone injured. The haystack is still smouldering.", meta: "09:14 • Sent" },
  ],
  assistantExtra: [],
};

const phone = document.getElementById("phone");
const toastEl = document.getElementById("toast");

// ---------------------------------------------------------------------------- drobne elementy

function icon(name, size = 20, cls = "") {
  const body = ICONS[name];
  if (!body) {
    console.error(`Brak ikony: ${name}`);
    return "";
  }
  return (
    `<svg class="icon ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ` +
    `aria-hidden="true">${body}</svg>`
  );
}

function esc(text) {
  return String(text).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
}

function statusBar() {
  return `
    <div class="statusbar" aria-hidden="true">
      <span>9:41</span>
      <span class="sys">
        <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1"/><rect x="5" y="5.5" width="3" height="6.5" rx="1"/><rect x="10" y="3" width="3" height="9" rx="1"/><rect x="15" y="0" width="3" height="12" rx="1"/></svg>
        <svg width="17" height="12" viewBox="0 0 24 17" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M12 15.5 2.2 5.6a14 14 0 0 1 19.6 0Z"/></svg>
        <svg width="26" height="12" viewBox="0 0 26 12" fill="currentColor"><rect x="0" y="0" width="23" height="12" rx="3.5"/><rect x="24" y="4" width="2" height="4" rx="1"/></svg>
      </span>
    </div>`;
}

function topBar({ left, title, right }) {
  const lead =
    left === "back"
      ? `<button class="iconbtn" data-back aria-label="Back">${icon("arrow-left", 24)}</button>`
      : `<span class="lead">${icon("map-pin", 24)}</span>`;
  const trail =
    right === "bell"
      ? `<button class="iconbtn" data-go="messages" aria-label="Messages and notices">${icon("bell", 24)}</button>`
      : `<button class="iconbtn" data-toast="Demo prototype — no extra options on this screen." aria-label="More options">${icon("ellipsis", 24)}</button>`;
  return `<div class="topbar">${lead}<h1>${title}</h1>${trail}</div>`;
}

function tab(target, name, label, active) {
  const current = active === target ? ' aria-current="page"' : "";
  const action = target === "more" ? 'data-toast="Demo prototype — this section is not part of the demo."' : `data-go="${target}"`;
  return `<button class="tab" ${action}${current}>${icon(name, 22)}<span>${label}</span></button>`;
}

function bottomNav(active) {
  return `
    <nav class="tabbar" aria-label="Main">
      ${tab("home", "house", "Home", active)}
      ${tab("messages", "message-circle", "Messages", active)}
      ${tab("guides", "book-open", "Guides", active)}
      ${tab("more", "layout-grid", "More", active)}
    </nav>
    <div class="homebar" aria-hidden="true"></div>`;
}

const verified = () => icon("badge-check", 16, "verified");
const warning = (title, text) => `
    <div class="card warn row top">
      ${icon("triangle-alert", 22, "warn-ico")}
      <span class="col"><span class="strong">${title}</span><span class="fine">${text}</span></span>
    </div>`;

function bubble(message) {
  return `<div class="bubble ${message.from}"><span>${esc(message.text)}</span><span class="meta">${esc(message.meta)}</span></div>`;
}

// ---------------------------------------------------------------------------- ekrany modułu

function screenHome() {
  return `
    ${statusBar()}
    ${topBar({ left: "pin", title: "Netless", right: "bell" })}
    <div class="content">
      <header class="col">
        <p class="eyebrow">YOUR AREA • DEMO SCENARIO</p>
        <h2 class="h1">Brzeziny Municipality</h2>
        <p class="muted">Local information, close to you.</p>
      </header>
      <button class="card tint row" data-go="notice">
        ${icon("shield-check", 30, "primary")}
        <span class="col"><span class="t16">Local situation</span><span class="fine">1 important notice • updated 09:20</span></span>
      </button>
      <button class="card col gap12" data-go="notice">
        <span class="chip warn">${icon("triangle-alert", 14)} Important notice</span>
        <span class="t18">Water supply interruption</span>
        <span class="muted">Today, 10:00–16:00. Check the affected streets and water distribution point.</span>
        <span class="row between link"><span>View guidance</span>${icon("arrow-right", 20)}</span>
      </button>
      <h3 class="section">How can we help?</h3>
      <div class="grid2">
        <button class="tile" data-go="report">${icon("map-pin-plus", 24)}<span>Report an incident</span></button>
        <button class="tile" data-go="messages">${icon("message-circle", 24)}<span>Chat</span></button>
        <button class="tile" data-go="guides">${icon("book-open", 24)}<span>Guides</span></button>
        <button class="tile" data-go="assistant">${icon("sparkles", 24)}<span>Local assistant</span></button>
      </div>
      <h3 class="section">Latest message</h3>
      <button class="card col gap12" data-go="messages">
        <span class="row">
          <span class="ico-box">${icon("landmark", 22)}</span>
          <span class="col"><span class="strong">Municipal Office${verified()}</span><span class="fine">Notice to residents • 08:45</span></span>
        </span>
        <span class="muted">The support point at the community centre is open until 18:00 today.</span>
      </button>
    </div>
    ${bottomNav("home")}`;
}

function screenMessages() {
  const unreadOnly = state.messagesFilter === "unread";
  const hide = (unread) => (unreadOnly && !unread ? " hidden" : "");
  const chatUnread = !state.chatRead;
  return `
    ${statusBar()}
    ${topBar({ left: "pin", title: "Chat", right: "bell" })}
    <div class="content">
      <header class="col gap8">
        <h2 class="h1">Local messages</h2>
        <p class="muted">Official updates and chats with local institutions.</p>
      </header>
      <div class="segmented" role="group" aria-label="Filter">
        <button data-action="filter-messages" data-value="all" aria-pressed="${!unreadOnly}">All</button>
        <button data-action="filter-messages" data-value="unread" aria-pressed="${unreadOnly}">Unread</button>
      </div>
      <div class="row between"><h3 class="section">Official notices</h3><span class="small primary">2 new</span></div>
      <button class="card col gap12" data-go="notice"${hide(true)}>
        <span class="row">
          <span class="ico-box">${icon("landmark", 22)}</span>
          <span class="col"><span class="strong">Municipal Office${verified()}</span><span class="fine">Today, 09:20 • to residents</span></span>
        </span>
        <span class="t16">Water supply interruption</span>
        <span class="muted">Lipowa and Ogrodowa streets. Guidance and a water distribution point.</span>
        <span class="chip">${icon("info", 14)} Notice • read-only</span>
      </button>
      <button class="card col gap12" data-toast="Demo prototype — only the water notice has a detail screen."${hide(true)}>
        <span class="row">
          <span class="ico-box">${icon("flame", 22)}</span>
          <span class="col"><span class="strong">Fire service${verified()}</span><span class="fine">Yesterday, 16:30 • to residents</span></span>
        </span>
        <span class="t16">Reminder: keep access roads clear for emergency services.</span>
        <span class="small primary">New notice</span>
      </button>
      <div class="row between"><h3 class="section">Your conversations</h3><span class="small primary">${chatUnread ? "1 unread" : "All read"}</span></div>
      <button class="card col gap12" data-go="chat"${hide(chatUnread)}>
        <span class="row">
          <span class="ico-box">${icon("flame", 22)}</span>
          <span class="col"><span class="strong">Fire service${verified()}</span><span class="fine">Report BL-024 • today, 09:12</span></span>
        </span>
        <span class="row between">
          <span class="muted">Is anyone at risk near the haystack in Lipinki Łużyckie?</span>
          ${chatUnread ? '<span class="badge">1</span>' : ""}
        </span>
      </button>
      <button class="card col gap12" data-toast="Demo prototype — this conversation has no detail screen."${hide(false)}>
        <span class="row">
          <span class="ico-box">${icon("landmark", 22)}</span>
          <span class="col"><span class="strong">Municipal Office${verified()}</span><span class="fine">Local support • yesterday, 14:05</span></span>
        </span>
        <span class="muted">Your request has been received for review. We will reply after checking the details.</span>
      </button>
      <p class="fine">The badge marks an institution account in this concept, not an actual verification.</p>
    </div>
    ${bottomNav("messages")}`;
}

function screenChat() {
  return `
    ${statusBar()}
    ${topBar({ left: "back", title: "Fire service", right: "more" })}
    <div class="content" data-stick-bottom>
      <div class="row">
        <span class="ico-box">${icon("flame", 22)}</span>
        <span class="col"><span class="strong">Fire service${verified()}</span><span class="fine">Institution account • demo scenario</span></span>
      </div>
      ${warning("This is not an emergency channel", "In immediate danger, call 112. A chat reply may take time.")}
      <div class="row between"><span class="fine">Report BL-024 • 03.10.2026</span><span class="chip">${icon("info", 14)} In progress</span></div>
      <p class="fine center">Today</p>
      <div class="bubbles">${state.chat.map(bubble).join("")}</div>
      <p class="fine">Stay away from fire and smoke. In immediate danger, call 112.</p>
    </div>
    <form class="composer" data-form="chat">
      <button type="button" class="attach" data-toast="Demo prototype — attachments are not sent." aria-label="Attach a file">${icon("paperclip", 20)}</button>
      <input name="text" autocomplete="off" placeholder="Type a message…" aria-label="Message">
      <button class="send" aria-label="Send">${icon("arrow-up", 20)}</button>
    </form>
    <div class="homebar" aria-hidden="true"></div>`;
}

function screenNotice() {
  const saved = state.noticeSaved;
  return `
    ${statusBar()}
    ${topBar({ left: "back", title: "Official notice", right: "more" })}
    <div class="content">
      <span class="chip warn">${icon("triangle-alert", 14)} Important • water supply</span>
      <h2 class="h1">Water supply interruption</h2>
      <div class="row">
        <span class="ico-box">${icon("landmark", 22)}</span>
        <span class="col"><span class="strong">Brzeziny Municipal Office${verified()}</span><span class="fine">To residents • 03.10.2026, 09:20</span></span>
      </div>
      <div class="card stack">
        <div class="row top">${icon("clock", 22, "primary")}<span class="col"><span class="t16">Today, 10:00–16:00</span><span class="muted">Scheduled work on the water network.</span></span></div>
        <div class="row top">${icon("map-pin", 22, "primary")}<span class="col"><span class="t16">Affected area</span><span class="muted">Brzeziny: Lipowa and Ogrodowa streets.</span></span></div>
      </div>
      <h3 class="section">What you can do now</h3>
      <div class="card">
        <ul class="bullets">
          <li>Store water for drinking and basic hygiene.</li>
          <li>Keep taps closed during the interruption.</li>
          <li>Once the supply resumes, check the office’s latest guidance on water quality.</li>
        </ul>
      </div>
      <div class="card tint row top">
        ${icon("droplets", 22, "primary")}
        <span class="col"><span class="t16">Water distribution point</span><span class="muted">Community centre, 4 Szkolna St. Today, 11:00–16:00. Bring a clean container.</span></span>
      </div>
      <p class="fine">Fictional scenario: times, streets and the distribution point are for demonstration only. This is not a live alert.</p>
      <button class="btn ${saved ? "outline" : "primary"}" data-action="save-notice">${saved ? "Saved on this device" : "Save notice offline"}</button>
    </div>
    <div class="homebar" aria-hidden="true"></div>`;
}

function screenReport() {
  const option = (value, name, label) =>
    `<button class="option" data-action="incident-type" data-value="${value}" aria-pressed="${state.incidentType === value}">${icon(name, 18)}<span>${label}</span></button>`;
  return `
    ${statusBar()}
    ${topBar({ left: "back", title: "Report an incident", right: "more" })}
    <div class="content">
      <p class="muted">Send information to the relevant institution in Brzeziny Municipality.</p>
      ${warning("Immediate danger? Call 112", "This form is not a substitute for the emergency number. Do not expect an immediate response.")}
      <div class="col gap8">
        <span class="label">Incident type</span>
        <div class="grid2" role="group" aria-label="Incident type">
          ${option("fire", "flame", "Fire")}
          ${option("water", "droplets", "No water")}
          ${option("food", "utensils", "Food shortage")}
          ${option("other", "ellipsis", "Other")}
        </div>
      </div>
      <label class="col gap8">
        <span class="label">Location</span>
        <input class="field active" value="Brzeziny, 12 Lipowa St">
        <span class="fine">Location entered manually • you can edit it</span>
      </label>
      <label class="col gap8">
        <span class="label">Incident description</span>
        <textarea class="field">There has been no water at 12 Lipowa St since 09:30. Please confirm whether this address is affected by the scheduled interruption.</textarea>
        <span class="fine">Do not include other people’s personal data.</span>
      </label>
      <button class="dropzone" data-toast="Demo prototype — photos are not uploaded.">
        ${icon("camera", 22)}
        <span class="col grow"><span class="strong">Add a photo</span><span class="fine">Optional • no faces or documents</span></span>
        ${icon("plus", 20)}
      </button>
      <p class="fine">Your report will go to the institution handling it. Include only the information needed to resolve the issue.</p>
      <button class="btn primary" data-action="submit-report">Submit report</button>
      <p class="fine center">Demo form — no data will be sent.</p>
    </div>
    <div class="homebar" aria-hidden="true"></div>`;
}

const GUIDES = [
  { id: "water", name: "droplets", title: "No water at home", meta: "Water • 3 min read", text: "Water supplies, hygiene and using local support points.", offline: true },
  { id: "food", name: "refrigerator", title: "Food during a power outage", meta: "Food • 4 min read", text: "How to reduce the risk of food spoilage during a power outage.", offline: true },
  { id: "fire", name: "flame", title: "Fire safety", meta: "Safety • 5 min read", text: "Preparing your home, smoke alarms and safe evacuation.", offline: false },
];

function guideCard(guide) {
  const query = state.guidesQuery.trim().toLowerCase();
  const matches = !query || `${guide.title} ${guide.meta} ${guide.text}`.toLowerCase().includes(query);
  const shown = matches && (state.guidesFilter === "all" || guide.offline);
  const action =
    guide.id === "food" ? 'data-go="guide"' : 'data-toast="Demo prototype — only “Food during a power outage” has a detail screen."';
  return `
      <button class="card col gap12" ${action}${shown ? "" : " hidden"}>
        <span class="row top">
          <span class="ico-box big">${icon(guide.name, 24)}</span>
          <span class="col grow"><span class="t16">${guide.title}</span><span class="fine">${guide.meta}</span></span>
          ${icon(guide.offline ? "bookmark-check" : "bookmark", 20, "primary")}
        </span>
        <span class="muted">${guide.text}</span>
        <span class="row between">
          ${guide.offline ? `<span class="chip ok">${icon("circle-check", 14)} Saved offline</span>` : '<span class="fine">Available to download</span>'}
          ${icon("chevron-right", 20, "primary")}
        </span>
      </button>`;
}

function screenGuides() {
  const all = state.guidesFilter === "all";
  return `
    ${statusBar()}
    ${topBar({ left: "pin", title: "Guides", right: "bell" })}
    <div class="content">
      <header class="col gap8">
        <h2 class="h1">Guidance for difficult times</h2>
        <p class="muted">Save useful guidance to keep it handy, even without an internet connection.</p>
      </header>
      <div class="search">
        ${icon("search", 18)}
        <input class="field" data-input="guides-query" value="${esc(state.guidesQuery)}" placeholder="Search topics" aria-label="Search topics">
      </div>
      <div class="row gap8">
        <button class="chip" data-action="filter-guides" data-value="all" aria-pressed="${all}">${icon("info", 14)} All</button>
        <button class="chip ok" data-action="filter-guides" data-value="offline" aria-pressed="${!all}">${icon("circle-check", 14)} Offline • 2</button>
      </div>
      <h3 class="section">Prepare with confidence</h3>
      <div class="stack" id="guide-list">${GUIDES.map(guideCard).join("")}</div>
      <p class="fine">Source: sample information from the Netless concept. This is not official institutional guidance.</p>
    </div>
    ${bottomNav("guides")}`;
}

function screenGuide() {
  const saved = state.guideSaved;
  return `
    ${statusBar()}
    ${topBar({ left: "back", title: "Guide", right: "more" })}
    <div class="content">
      <div class="row gap8">${icon("refrigerator", 26, "primary")}<span class="chip">${icon("info", 14)} Food • 4 min</span></div>
      <h2 class="h1">How to store food during a power outage</h2>
      <p class="fine">Author / source: Netless concept team. Sample information. Updated: 02.10.2026.</p>
      ${saved ? `<span class="chip ok">${icon("circle-check", 14)} Available offline • saved</span>` : '<span class="fine">Not saved on this device</span>'}
      <div class="card tint col gap8">
        <span class="t16">Priority: keep food cold</span>
        <span>Open the fridge and freezer as little as possible. Never taste food to check whether it is safe.</span>
      </div>
      <div class="col gap8"><h3 class="section">1. Keep doors closed</h3><p class="muted">A closed fridge usually stays cold for about 4 hours. This is an estimate — temperature, appliance condition and how cold the food was beforehand all matter.</p></div>
      <div class="col gap8"><h3 class="section">2. Check the temperature</h3><p class="muted">If you have a thermometer, check the food’s temperature. Discard perishable foods such as meat, fish and dairy that have been above 4°C for more than 2 hours.</p></div>
      <div class="col gap8"><h3 class="section">3. Assess food carefully</h3><p class="muted">Frozen food that still contains ice crystals or is at 4°C or below can usually be refrozen. If in doubt, do not eat it. Smell is not a reliable test of food safety.</p></div>
      <div class="card tint row top">
        ${icon("info", 22, "primary")}
        <span class="col"><span class="strong">General guidance, not a personal assessment</span><span class="fine">Check product labels and current notices from the relevant authorities. This example is not an official publication or medical advice.</span></span>
      </div>
      <button class="btn ${saved ? "outline" : "primary"}" data-action="toggle-guide-saved">${saved ? "Saved on this device" : "Save on this device"}</button>
    </div>
    <div class="homebar" aria-hidden="true"></div>`;
}

function screenAssistant() {
  const extra = state.assistantExtra
    .map(
      (question) => `
      <div class="bubbles">${bubble({ from: "me", text: question, meta: "Sent" })}</div>
      <div class="card col gap8">
        <span class="row gap8 small primary">${icon("sparkles", 16)} AI-generated response</span>
        <span>Demo prototype: the assistant shows only this sample answer. In the concept it would search the notices and guides saved on this device.</span>
      </div>`
    )
    .join("");
  return `
    ${statusBar()}
    ${topBar({ left: "back", title: "Local assistant", right: "more" })}
    <div class="content" data-stick-bottom>
      <div class="card tint col gap12">
        <span class="row top">
          ${icon("sparkles", 28, "primary")}
          <span class="col"><span class="t16">LocalLLM • on-device support</span><span class="fine">Offline concept. This is an AI assistant, not an office representative.</span></span>
        </span>
        <span class="chip ok">${icon("circle-check", 14)} Offline mode • saved content</span>
      </div>
      ${warning("Not a substitute for emergency services", "In immediate danger, call 112. The model’s response may contain errors.")}
      <div class="bubbles">${bubble({ from: "me", text: "I have no water on Lipowa St. What can I do now?", meta: "Sent" })}</div>
      <div class="card col gap12">
        <span class="row gap8 small primary">${icon("sparkles", 16)} AI-generated response</span>
        <span>The saved demo notice lists Lipowa St as affected from 10:00–16:00. Prepare a clean container and conserve your water supply. The saved guide “No water at home” includes hygiene advice.</span>
        <span class="fine">While offline, I cannot confirm whether the notice is still current. Check the office’s updates once you reconnect.</span>
        <button class="source" data-go="guides">${icon("book-open", 18)} No water at home • offline</button>
      </div>
      <p class="fine">Sources: a saved demo notice and a sample Netless guide.</p>
      ${extra}
    </div>
    <form class="composer" data-form="assistant">
      <input name="text" autocomplete="off" placeholder="Ask about saved guidance…" aria-label="Question">
      <button class="send" aria-label="Send">${icon("arrow-up", 20)}</button>
    </form>
    <div class="homebar" aria-hidden="true"></div>`;
}

// ---------------------------------------------------------------------------- ekrany mObywatela (demo)

const DEMO = "Demo: ten element nie jest częścią prototypu.";

function shellTab(name, label, active) {
  const current = active ? ' aria-current="page"' : ` data-toast="${DEMO}"`;
  return `<button class="tab pill"${current}>${icon(name, 22)}<span>${label}</span></button>`;
}

function screenShell() {
  return `
    ${statusBar()}
    <div class="topbar">
      <span class="lead">${icon("shield-check", 26)}</span>
      <h1>mObywatel</h1>
      <button class="iconbtn" data-toast="${DEMO}" aria-label="Powiadomienia">${icon("bell", 24)}</button>
    </div>
    <div class="content">
      <span class="chip caps">${icon("info", 14)} PROPOZYCJA INTEGRACJI • DEMO</span>
      <div class="row between"><h2 class="display">Dokumenty</h2><button class="pill-outline" data-toast="${DEMO}">Dodaj</button></div>
      <div class="docs">
        <button class="doc doc-id" data-go="mdowod" aria-label="mDowód – wzór demonstracyjny"><span class="doc-title">mDowód</span>${icon("shield", 26)}</button>
        <button class="doc doc-student" data-toast="Demo: legitymacja jest tylko wzorem koncepcyjnym."><span class="doc-title">Legitymacja studencka</span><span class="doc-foot">DEMO • wzór koncepcyjny</span></button>
      </div>
      <button class="link" data-toast="${DEMO}">Dostosuj widok</button>
      <div class="row between"><h3 class="h2">Usługi</h3><button class="link" data-toast="${DEMO}">Wszystkie</button></div>
      <div class="card col gap12">
        <span class="row top">
          <span class="ico-box big">${icon("shield-check", 26)}</span>
          <span class="col"><span class="t16 strong">Bezpieczeństwo lokalne</span><span class="fine">Komunikaty, zgłoszenia i poradniki w jednym miejscu.</span></span>
        </span>
        <button class="btn primary" data-go="home">Otwórz usługę</button>
      </div>
      <div class="card col gap8">
        <span class="row gap8">${icon("droplets", 22, "primary")}<span class="t16 strong">Gmina Brzeziny • ważne</span></span>
        <span class="muted">Przerwa w dostawie wody, 10:00–16:00. Komunikat demonstracyjny.</span>
        <button class="link" data-go="notice">Przeczytaj komunikat →</button>
      </div>
      <div class="grid3">
        <button class="service-tile" data-toast="${DEMO}"><span class="ico-box">${icon("car", 28)}</span>Punkty karne</button>
        <button class="service-tile" data-toast="${DEMO}"><span class="ico-box">${icon("trees", 28)}</span>Środowisko</button>
        <button class="service-tile" data-toast="${DEMO}"><span class="ico-box">${icon("heart-pulse", 28)}</span>eRecepta</button>
      </div>
    </div>
    <nav class="tabbar" aria-label="mObywatel">
      ${shellTab("inbox", "Dokumenty", true)}
      ${shellTab("folder", "Usługi", false)}
      ${shellTab("qr-code", "Kod QR", false)}
      ${shellTab("search", "Szukaj", false)}
      ${shellTab("layout-grid", "Więcej", false)}
    </nav>
    <div class="homebar" aria-hidden="true"></div>`;
}

function screenMdowod() {
  const row = (label, value) => `<div class="datarow"><span class="fine">${label}</span><span class="t16">${value}</span></div>`;
  return `
    ${statusBar()}
    <div class="topbar">
      <button class="iconbtn" data-back aria-label="Wstecz">${icon("arrow-left", 24)}</button>
      <h1>mDowód</h1>
      <button class="iconbtn" data-toast="${DEMO}" aria-label="Więcej">${icon("ellipsis", 24)}</button>
    </div>
    <div class="content">
      <p class="fine center">ADAPTACJA 2.0 • DEMO • dane fikcyjne</p>
      <div class="card idcard">
        <div class="idcard-top">
          <span class="row between">${icon("shield", 26)}<span class="chip">${icon("info", 14)} DEMO</span></span>
          <span class="row">
            <span class="avatar">${icon("user", 56)}</span>
            <span class="col gap8"><span class="t16 strong">ANNA PRZYKŁADOWA</span><span class="small">Obywatelstwo polskie</span><span class="small">Dane fikcyjne • bez numeru PESEL</span></span>
          </span>
          <span class="small">Wzór koncepcyjny. Nie potwierdza tożsamości.</span>
        </div>
        <button class="idcard-bottom" data-toast="Demo: wzór nie ma dalszych ekranów."><span>mDowód</span>${icon("chevron-right", 22)}</button>
      </div>
      <div class="card col gap8">
        <span class="chip ok">${icon("circle-check", 14)} Dokument ważny • wzór statusu</span>
        <span class="fine">Status demonstracyjny, bez skutków prawnych.</span>
      </div>
      <button class="btn primary" data-toast="Demo: potwierdzanie danych jest wyłącznie przykładem widoku.">Potwierdź swoje dane • demo</button>
      <div class="card stack">
        <span class="row gap8">${icon("contact", 24, "primary")}<span class="t18">Dane dokumentu</span></span>
        ${row("Imię i nazwisko", "Anna Przykładowa")}
        ${row("Obywatelstwo", "Polskie • dane przykładowe")}
        ${row("Numer dokumentu / PESEL", "Nie nadano — demonstracja")}
      </div>
      <div class="card ok row top">
        ${icon("info", 22, "ok-ico")}
        <span class="col"><span class="strong">DEMO — nie jest dokumentem tożsamości</span><span class="fine">Nie zawiera ważnego numeru dokumentu, PESEL ani kodu QR. Potwierdzanie danych jest wyłącznie przykładem widoku.</span></span>
      </div>
    </div>
    <div class="homebar" aria-hidden="true"></div>`;
}

const SCREENS = {
  home: screenHome,
  messages: screenMessages,
  chat: screenChat,
  notice: screenNotice,
  report: screenReport,
  guides: screenGuides,
  guide: screenGuide,
  assistant: screenAssistant,
  shell: screenShell,
  mdowod: screenMdowod,
};
// ekrany dostępne tylko w wariancie mObywatel
const SHELL_ONLY = ["shell", "mdowod"];

// ---------------------------------------------------------------------------- nawigacja

function parseHash() {
  const [, variant, screen] = location.hash.split("/");
  const okVariant = VARIANTS.includes(variant) ? variant : "netless";
  const known = SCREENS[screen] && (okVariant === "mobywatel" || !SHELL_ONLY.includes(screen));
  return { variant: okVariant, screen: known ? screen : START[okVariant] };
}

function go(screen, variant = state.variant) {
  const target = `#/${variant}/${screen}`;
  if (location.hash === target) {
    render();
    return;
  }
  state.depth += 1;
  location.hash = target;
}

function back() {
  if (state.depth > 0) {
    state.depth -= 1;
    history.back();
    return;
  }
  // wejście bezpośrednio z linku: nie ma dokąd wracać w historii, więc idziemy do ekranu nadrzędnego
  const parent = state.variant === "mobywatel" && state.screen === "home" ? "shell" : PARENT[state.screen];
  location.replace(`#/${state.variant}/${parent || START[state.variant]}`);
}

function render(keepScroll = false) {
  const content = phone.querySelector(".content");
  const scroll = keepScroll && content ? content.scrollTop : 0;
  document.body.dataset.theme = state.variant;
  phone.innerHTML = SCREENS[state.screen]();
  const fresh = phone.querySelector(".content");
  if (fresh) {
    fresh.scrollTop = keepScroll && fresh.hasAttribute("data-stick-bottom") ? fresh.scrollHeight : scroll;
  }
  for (const button of document.querySelectorAll(".switcher button")) {
    button.setAttribute("aria-pressed", String(button.dataset.variant === state.variant));
  }
  document.title = state.variant === "mobywatel" ? "Netless w mObywatelu – prototyp" : "Netless – prototyp";
}

function onRoute() {
  const route = parseHash();
  state.variant = route.variant;
  state.screen = route.screen;
  if (state.screen === "chat") {
    state.chatRead = true;
  }
  render();
}

let toastTimer = 0;
function toast(text) {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
}

function clock() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------- zdarzenia

const ACTIONS = {
  "filter-messages": (el) => {
    state.messagesFilter = el.dataset.value;
  },
  "filter-guides": (el) => {
    state.guidesFilter = el.dataset.value;
  },
  "incident-type": (el) => {
    state.incidentType = el.dataset.value;
  },
  "save-notice": () => {
    state.noticeSaved = !state.noticeSaved;
    toast(state.noticeSaved ? "Notice saved on this device (demo)." : "Notice removed from this device (demo).");
  },
  "toggle-guide-saved": () => {
    state.guideSaved = !state.guideSaved;
    toast(state.guideSaved ? "Guide saved on this device (demo)." : "Guide removed from this device (demo).");
  },
  "submit-report": () => {
    toast("Demo form — no data was sent.");
  },
};

phone.addEventListener("click", (event) => {
  const el = event.target.closest("[data-go], [data-back], [data-toast], [data-action]");
  if (!el || !phone.contains(el)) {
    return;
  }
  if (el.dataset.go) {
    go(el.dataset.go);
  } else if (el.hasAttribute("data-back")) {
    back();
  } else if (el.dataset.toast) {
    toast(el.dataset.toast);
  } else if (ACTIONS[el.dataset.action]) {
    ACTIONS[el.dataset.action](el);
    render(true);
  }
});

phone.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const text = form.elements.text.value.trim();
  if (!text) {
    return;
  }
  if (form.dataset.form === "chat") {
    state.chat.push({ from: "me", text, meta: `${clock()} • Sent (demo)` });
  } else {
    state.assistantExtra.push(text);
  }
  render(true);
  const input = phone.querySelector(".composer input");
  if (input) {
    input.focus();
  }
});

phone.addEventListener("input", (event) => {
  if (event.target.dataset.input !== "guides-query") {
    return;
  }
  // filtrujemy bez przerysowania całego ekranu, żeby pole nie traciło fokusu
  state.guidesQuery = event.target.value;
  document.getElementById("guide-list").innerHTML = GUIDES.map(guideCard).join("");
});

for (const button of document.querySelectorAll(".switcher button")) {
  button.addEventListener("click", () => go(START[button.dataset.variant], button.dataset.variant));
}

// index.html?full pokazuje ekran w pełnej wysokości, bez przewijania w ramce (do zrzutów na slajdy)
if (new URLSearchParams(location.search).has("full")) {
  document.body.classList.add("full");
}

window.addEventListener("hashchange", onRoute);
onRoute();
