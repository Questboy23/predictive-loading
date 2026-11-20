// Which links may be preloaded. The checks marked [instant.page] are adapted
// from instant.page isPreloadable() (MIT, (C) 2019-2025 Alexandre Dieulot);
// the ones marked [quicklink] from GoogleChromeLabs/quicklink (Apache-2.0).
// See THIRD_PARTY_NOTICES.md.
(function (root) {
  "use strict";
  const ACTION_WORDS = ["logout", "signout", "logoff", "delete", "remove", "unsubscribe", "cart", "basket",
    "checkout", "buy", "pay", "order", "confirm", "cancel", "settings"];
  // "log out", "log-out", "log_out" and "check out" all match: optional separator after the first part.
  const ACTION_RE = new RegExp("(^|[^a-z])(" + ACTION_WORDS.map((w) =>
    w.replace(/^(log|sign|check)(.+)$/, "$1[\\s_-]?$2")).join("|") + ")", "i");
  const DOWNLOAD_EXT = /\.(zip|gz|tgz|bz2|xz|7z|rar|dmg|pkg|exe|msi|apk|iso|img|pdf|docx?|xlsx?|pptx?|csv|mp3|mp4|mov|avi|mkv|wav|flac)$/i;

  // a: {href, origin, protocol, pathname, search, hash, text, download, dataset, rel}
  // loc: {origin, protocol, pathname, search}
  function isSafeLink(a, loc) {
    if (!a || !a.href) return false;
    if (a.protocol !== "http:" && a.protocol !== "https:") return false; // [instant.page]
    if (a.origin !== loc.origin) return false; // same origin only [instant.page]
    if (a.protocol === "http:" && loc.protocol === "https:") return false; // [instant.page]
    if (a.search) return false; // query strings skipped by default [instant.page]
    if (a.hash && a.pathname + a.search === loc.pathname + loc.search) return false; // in-page anchor [instant.page]
    if (a.pathname + a.search === loc.pathname + loc.search) return false; // the current page
    if (a.dataset && ("noInstant" in a.dataset || "noPrefetch" in a.dataset || "noPreload" in a.dataset)) return false; // [instant.page]
    if (a.download !== undefined && a.download !== null && a.download !== false) return false; // [quicklink] hasAttribute('download')
    if (DOWNLOAD_EXT.test(a.pathname)) return false;
    if (a.rel && /\b(nofollow|external)\b/i.test(a.rel)) return false;
    let path = a.pathname + a.search;
    try { path = decodeURIComponent(path); } catch (e) { /* keep raw */ }
    if (ACTION_RE.test(path) || ACTION_RE.test(a.text || "")) return false;
    return true;
  }

  const api = { isSafeLink, ACTION_WORDS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PLlinks = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
