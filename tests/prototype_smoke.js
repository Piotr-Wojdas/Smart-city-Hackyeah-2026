// Test dymny klikalnego prototypu (prototyp/): uruchamia app.js w Node z atrapą przeglądarki
// i przechodzi po ekranach tak, jak robi to użytkownik. Wywoływany przez tests/test_prototype.py.
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const dir = path.join(__dirname, "..", "prototyp");
const errors = [];
const listeners = {};
let hashListener = null;

function element() {
  return {
    innerHTML: "",
    textContent: "",
    dataset: {},
    classList: { add() {}, remove() {} },
    setAttribute() {},
    hasAttribute: () => false,
    querySelector: () => null,
    contains: () => true,
    focus() {},
    addEventListener(type, fn) {
      listeners[type] = fn;
    },
  };
}

const phone = element();
const toast = element();
const guideList = element();
// historia przeglądarki: zmiana hasha dopisuje wpis i wywołuje „hashchange”
const stack = ["#/netless/home"];
const location = {
  search: "",
  get hash() {
    return stack[stack.length - 1];
  },
  set hash(value) {
    stack.push(value);
    hashListener();
  },
  replace(value) {
    stack[stack.length - 1] = value;
    hashListener();
  },
};
const sandbox = {
  console: { ...console, error: (...args) => errors.push(args.join(" ")) },
  document: {
    body: element(),
    title: "",
    getElementById: (id) => ({ phone, toast, "guide-list": guideList })[id],
    querySelectorAll: () => [],
  },
  location,
  history: {
    back() {
      stack.pop();
      hashListener();
    },
  },
  window: {
    addEventListener(type, fn) {
      if (type === "hashchange") hashListener = fn;
    },
  },
  URLSearchParams,
  setTimeout: () => 0,
  clearTimeout() {},
};
vm.createContext(sandbox);
for (const file of ["icons.js", "app.js"]) {
  vm.runInContext(fs.readFileSync(path.join(dir, file), "utf8"), sandbox, { filename: file });
}
const app = (code) => vm.runInContext(code, sandbox);

function check(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function click(attributes) {
  const el = {
    dataset: attributes,
    hasAttribute: (name) => name === "data-back" && "back" in attributes,
  };
  listeners.click({ target: { closest: () => el } });
}

const shows = (text) => phone.innerHTML.includes(text);

// start: wariant samodzielny, ekran główny
check(shows("Brzeziny Municipality") && shows("Netless"), "ekran główny się nie wyświetlił");
check(app("document.body.dataset.theme") === "netless", "motyw samodzielny nie został ustawiony");

// każdy ekran w każdym wariancie rysuje się z ikonami i bez błędów
const screens = app("Object.keys(SCREENS)");
for (const variant of ["netless", "mobywatel"]) {
  for (const screen of screens) {
    location.hash = `#/${variant}/${screen}`;
    const shellOnly = ["shell", "mdowod"].includes(screen);
    const expected = variant === "netless" && shellOnly ? "home" : screen;
    check(app("state.screen") === expected, `${variant}/${screen}: wyświetlono ${app("state.screen")}`);
    check(phone.innerHTML.includes("<svg"), `${variant}/${screen}: brak ikon`);
    check(!phone.innerHTML.includes("undefined"), `${variant}/${screen}: „undefined” w treści ekranu`);
  }
}
check(errors.length === 0, `błędy podczas rysowania: ${errors.join("; ")}`);

// nawigacja: kafelek -> ekran -> wstecz
location.hash = "#/netless/home";
app("state.depth = 0");
click({ go: "report" });
check(shows("Report an incident") && shows("Submit report"), "kafelek nie otworzył formularza zgłoszenia");
click({ back: "" });
check(app("state.screen") === "home", "strzałka wstecz nie wróciła na ekran główny");

// strzałka wstecz po wejściu z linku prowadzi do ekranu nadrzędnego
location.replace("#/netless/guide");
app("state.depth = 0");
click({ back: "" });
check(app("state.screen") === "guides", "wstecz z poradnika nie prowadzi do listy poradników");

// działania na ekranach
app("state.chatRead = false"); // przegląd ekranów wyżej otworzył już rozmowę
location.hash = "#/netless/messages";
check(shows('<span class="badge">1</span>'), "brak znacznika nieprzeczytanej rozmowy");
click({ action: "filter-messages", value: "unread" });
check((phone.innerHTML.match(/ hidden>/g) || []).length === 1, "filtr „Unread” nie ukrył przeczytanej rozmowy");
click({ go: "chat" });
listeners.submit({ preventDefault() {}, target: { dataset: { form: "chat" }, elements: { text: { value: " Road is clear <b> " } } } });
check(shows("Road is clear &lt;b&gt;"), "wysłana wiadomość nie pojawiła się w rozmowie albo nie została zabezpieczona");
click({ back: "" });
check(!shows('<span class="badge">1</span>') && shows("All read"), "otwarta rozmowa nadal jest oznaczona jako nieprzeczytana");

location.hash = "#/netless/report";
click({ action: "incident-type", value: "fire" });
check(/data-value="fire" aria-pressed="true"/.test(phone.innerHTML), "wybór rodzaju zdarzenia nie działa");

location.hash = "#/netless/notice";
click({ action: "save-notice" });
check(shows("Saved on this device"), "zapis komunikatu nie zmienił przycisku");

location.hash = "#/netless/guides";
listeners.input({ target: { dataset: { input: "guides-query" }, value: "fire" } });
check((guideList.innerHTML.match(/ hidden>/g) || []).length === 2, "wyszukiwarka poradników nie filtruje listy");

// wariant mObywatel: ekran dokumentów -> usługa -> wzór mDowodu z oznaczeniami demo
location.hash = "#/mobywatel/shell";
check(app("document.body.dataset.theme") === "mobywatel", "motyw mObywatel nie został ustawiony");
check(shows("Dokumenty") && shows("PROPOZYCJA INTEGRACJI • DEMO"), "ekran dokumentów bez oznaczenia demo");
click({ go: "home" });
check(shows("Brzeziny Municipality") && app("state.variant") === "mobywatel", "usługa nie otworzyła się w mObywatelu");
click({ back: "" });
click({ go: "mdowod" });
for (const label of ["DEMO — nie jest dokumentem tożsamości", "Wzór koncepcyjny. Nie potwierdza tożsamości.", "dane fikcyjne"]) {
  check(shows(label), `wzór mDowodu bez oznaczenia: ${label}`);
}
check(errors.length === 0, `błędy podczas działania: ${errors.join("; ")}`);
console.log(`ok: ${screens.length} ekranów w 2 wariantach`);
