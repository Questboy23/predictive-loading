// Action, download and non-http(s) links must never be preloadable.
const assert = require("assert");
const { isSafeLink, ACTION_WORDS } = require("../extension/linksafety.js");
const loc = { origin: "https://ex.com", protocol: "https:", pathname: "/home", search: "" };
function link(href, extra = {}) {
  const u = new URL(href, "https://ex.com/home");
  return { href: u.href, origin: u.origin, protocol: u.protocol, pathname: u.pathname, search: u.search, hash: u.hash,
    text: extra.text || "", download: extra.download, dataset: extra.dataset || {}, rel: extra.rel || "" };
}
const bad = [
  ...ACTION_WORDS.map((w) => `/account/${w}`), ...ACTION_WORDS.map((w) => `/${w.toUpperCase()}`),
  "/user/log%6Fut", "/files/report.pdf", "/dl/app.dmg", "/x.zip", "mailto:a@b.c", "javascript:void(0)",
  "ftp://ex.com/a", "data:text/html,hi", "https://other.com/a", "http://ex.com/a", "/home#top", "/home",
  "/search?q=1", "/orders/12", "/my-cart", "/checkout/step1",
];
for (const h of bad) assert.strictEqual(isSafeLink(link(h), loc), false, "should block " + h);
assert.strictEqual(isSafeLink(link("/a", { download: true }), loc), false, "download attribute");
assert.strictEqual(isSafeLink(link("/a", { text: "Log out" }), loc), false, "action text");
assert.strictEqual(isSafeLink(link("/a", { text: "Buy now" }), loc), false, "action text");
assert.strictEqual(isSafeLink(link("/a", { dataset: { noInstant: "" } }), loc), false, "data-no-instant");
assert.strictEqual(isSafeLink(link("/a", { rel: "nofollow" }), loc), false, "nofollow");
const good = ["/a", "/news/today", "/borders", "/docs/guide.html", "/about/", "/profile"];
for (const h of good) assert.strictEqual(isSafeLink(link(h), loc), true, "should allow " + h);
console.log(`links OK: ${bad.length + 5} blocked cases, ${good.length} allowed cases`);
