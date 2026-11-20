// Popup: ms saved against the random 20% holdout, on/off switch, delete data.
// Uses textContent only.
(async function () {
  "use strict";
  const store = chrome.storage.local;
  const $ = (id) => document.getElementById(id);
  const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length;

  function bootstrapCI(treat, hold) {
    let seed = 1;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
    const pick = (a) => a[Math.floor(rnd() * a.length)];
    const diffs = [];
    for (let i = 0; i < 1000; i++) {
      const t = treat.map(() => pick(treat));
      const h = hold.map(() => pick(hold));
      diffs.push((mean(h) - mean(t)) * treat.length);
    }
    diffs.sort((x, y) => x - y);
    return [diffs[25], diffs[974]];
  }

  async function render() {
    const { enabled, stats } = await store.get(["enabled", "stats"]);
    $("enabled").checked = enabled !== false;
    const s = stats || { treat: [], hold: [] };
    if (s.treat.length && s.hold.length) {
      const per = mean(s.hold) - mean(s.treat);
      const total = per * s.treat.length;
      const [lo, hi] = bootstrapCI(s.treat, s.hold);
      $("saved").textContent = `${Math.round(total).toLocaleString()} ms saved`;
      $("detail").textContent = `Predicted pages: ${Math.round(mean(s.treat))} ms loaded early (n=${s.treat.length}) vs ` +
        `${Math.round(mean(s.hold))} ms in the random 20% holdout (n=${s.hold.length}). 95% CI ${Math.round(lo)} to ${Math.round(hi)} ms.`;
    } else {
      $("saved").textContent = "No measurements yet";
      $("detail").textContent = `Correct predictions so far: n=${s.treat.length} loaded early, n=${s.hold.length} held out.`;
    }
  }

  $("enabled").addEventListener("change", async (e) => {
    await store.set({ enabled: e.target.checked });
    $("note").textContent = e.target.checked ? "On. Applies from the next page load." : "Off. Nothing is preloaded.";
  });
  $("delete").addEventListener("click", async () => {
    const { enabled } = await store.get("enabled");
    await store.clear();
    await store.set({ enabled: enabled !== false });
    $("note").textContent = "All data deleted.";
    render();
  });
  render();
})();
