// Runs the JS port on the parity fixture and compares with the Python output.
const fs = require("fs");
const path = require("path");
const { Predictor } = require("../extension/predictor.js");
const dir = path.join(__dirname, "fixtures");
const evs = JSON.parse(fs.readFileSync(path.join(dir, "parity_events.json"), "utf8"));
const p = new Predictor();
const lines = [];
for (const [x, hr, d] of evs) {
  const r = p.observe(x, hr, d);
  lines.push(r === null ? "skip" : `${r[0]}\t${r[1].toFixed(10)}\t${p.choice}`);
}
const top = p.predict(evs[evs.length - 1][1], 5);
lines.push(`final\t${p.bitsPerEvent().toFixed(10)}\t` + top.map(([s, q]) => `${s}:${q.toFixed(10)}`).join(","));
const js = lines.join("\n") + "\n";
const py = fs.readFileSync(path.join(dir, "parity_py.txt"), "utf8");
// round-trip through JSON must not change predictions either
const p2 = Predictor.fromJSON(JSON.parse(JSON.stringify(p)));
const same = JSON.stringify(p2.predict(5, 5)) === JSON.stringify(p.predict(5, 5));
if (js !== py || !same) {
  const a = js.split("\n"), b = py.split("\n");
  const i = a.findIndex((l, k) => l !== b[k]);
  console.error(`PARITY FAIL at line ${i}: js=${a[i]} py=${b[i]} jsonRoundTrip=${same}`);
  process.exit(1);
}
console.log(`parity OK: ${evs.length} events, ${a_len(js)} lines identical, JSON round trip identical`);
function a_len(s) { return s.split("\n").length - 1; }
