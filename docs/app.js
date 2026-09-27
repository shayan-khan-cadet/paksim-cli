/* ==================== PAKSIM-CLI Browser Tool ==================== */

const PROVINCE_NAMES = {
  "1": "Khyber Pakhtunkhwa",
  "2": "FATA",
  "3": "Punjab",
  "4": "Sindh",
  "5": "Balochistan",
  "6": "Islamabad",
  "7": "Gilgit-Baltistan",
  "8": "Azad Kashmir",
};

/* Pakistani carrier prefixes (without leading 0) */
const PK_CARRIERS = {
  "300": "Jazz", "301": "Jazz", "302": "Jazz", "303": "Jazz",
  "305": "Jazz", "306": "Jazz", "307": "Jazz", "308": "Jazz",
  "309": "Jazz", "320": "Jazz", "321": "Jazz", "322": "Jazz",
  "323": "Jazz", "324": "Jazz",
  "310": "Zong", "311": "Zong", "312": "Zong", "313": "Zong",
  "314": "Zong", "315": "Zong", "316": "Zong", "317": "Zong",
  "318": "Zong", "319": "Zong",
  "340": "Telenor", "341": "Telenor", "342": "Telenor",
  "343": "Telenor", "344": "Telenor", "345": "Telenor",
  "346": "Telenor", "347": "Telenor", "348": "Telenor",
  "330": "Ufone", "331": "Ufone", "332": "Ufone",
  "333": "Ufone", "334": "Ufone", "335": "Ufone",
  "355": "SCOM",
  "325": "Warid (Jazz)", "326": "Warid (Jazz)", "327": "Warid (Jazz)",
};

/* ==================== INPUT DETECTION ==================== */
function detectType(raw) {
  const clean = raw.replace(/[^0-9]/g, "");
  if (clean.length === 13) return { type: "cnic", clean };
  if (clean.length >= 11 && clean.length <= 12 &&
      (clean.startsWith("0") || clean.startsWith("92"))) {
    return { type: "sim", clean };
  }
  if (clean.length >= 10 && clean.length <= 15) {
    return { type: "phone", clean };
  }
  return { type: "unknown", clean };
}

/* ==================== CNIC DECODER ==================== */
function decodeCNIC(clean) {
  if (clean.length !== 13) {
    return { error: "CNIC must be 13 digits" };
  }

  const first5 = clean.slice(0, 5);
  const genderCode = clean[12];
  const gender = parseInt(genderCode, 10) % 2 === 1 ? "Male" : "Female";

  let matched = null;
  let matchedLen = 0;

  for (let len = 5; len >= 1; len--) {
    const key = first5.slice(0, len);
    if (CNIC_CODES[key]) {
      matched = CNIC_CODES[key];
      matchedLen = len;
      break;
    }
  }

  if (!matched) {
    return {
      error: `Location code '${first5}' not found in database`,
      province: PROVINCE_NAMES[clean[0]] || "Unknown",
      gender,
    };
  }

  const names = (matched.full_path || "").split(" > ");
  const codes = matched.codes || [];
  const cleanPairs = names
    .map((n, i) => [codes[i], n])
    .filter(([c, n]) => n && n.toLowerCase() !== "empty");

  const filtered = cleanPairs.map(([c, n]) => n);

  return {
    cnic: clean,
    formatted: `${clean.slice(0, 5)}-${clean.slice(5, 12)}-${clean[12]}`,
    gender,
    genderCode,
    province: filtered[0] || PROVINCE_NAMES[clean[0]] || "N/A",
    division: filtered[1] || "N/A",
    district: filtered[2] || "N/A",
    tehsil: filtered[3] || "N/A",
    unionCouncil: filtered[4] || "N/A",
    fullPath: filtered.join(" > ") || "N/A",
    matchedLen,
  };
}

/* ==================== PHONE INTEL ==================== */
function detectCarrier(clean) {
  let c = clean.replace(/[^0-9]/g, "");
  if (c.startsWith("92")) c = "0" + c.slice(2);
  if (c.startsWith("0")) c = c.slice(1);        // strip leading 0 → "344"
  const prefix = c.slice(0, 3);
  return PK_CARRIERS[prefix] || null;
}

function formatPhoneLocal(clean) {
  let c = clean.replace(/[^0-9]/g, "");
  if (c.startsWith("92")) c = "0" + c.slice(2);
  if (c.length === 11) {
    return `${c.slice(0, 4)}-${c.slice(4)}`;
  }
  return c;
}

function formatPhoneNational(clean) {
  let c = clean.replace(/[^0-9]/g, "");
  if (c.startsWith("92")) c = "0" + c.slice(2);
  if (c.length === 11) {
    return `${c.slice(0, 4)} ${c.slice(4)}`;
  }
  return c;
}

function formatPhoneInternational(clean) {
  let c = clean.replace(/[^0-9]/g, "");
  if (c.startsWith("0")) c = "92" + c.slice(1);
  if (c.startsWith("92")) {
    const rest = c.slice(2);
    if (rest.length === 10) {
      return `+92 ${rest.slice(0, 3)} ${rest.slice(3)}`;
    }
  }
  return "+" + c;
}

function formatPhoneE164(clean) {
  let c = clean.replace(/[^0-9]/g, "");
  if (c.startsWith("0")) c = "92" + c.slice(1);
  return "+" + c;
}

/* ==================== RENDERING ==================== */
function showResult(html) {
  const el = document.getElementById("result");
  el.innerHTML = html;
  el.style.display = "block";
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderCNIC(d) {
  if (d.error) {
    return `
      <div class="result-inner">
        <div class="result-error">✗ ${d.error}</div>
        <div class="result-hint">Gender: ${d.gender} · Try a different CNIC or install the CLI for full lookup.</div>
      </div>`;
  }
  return `
    <div class="result-inner">
      <div class="result-title">🧬 CNIC STRUCTURAL DECODE</div>
      <div class="result-grid">
        <div class="result-row"><span class="rk">CNIC</span><span class="rv hl">${d.formatted}</span></div>
        <div class="result-row"><span class="rk">Gender</span><span class="rv">${d.gender}</span></div>
        <div class="result-row"><span class="rk">Province</span><span class="rv hl">${d.province}</span></div>
        <div class="result-row"><span class="rk">Division</span><span class="rv">${d.division}</span></div>
        <div class="result-row"><span class="rk">District</span><span class="rv hl">${d.district}</span></div>
        <div class="result-row"><span class="rk">Tehsil</span><span class="rv hl">${d.tehsil}</span></div>
        <div class="result-row"><span class="rk">Union Council</span><span class="rv">${d.unionCouncil}</span></div>
        <div class="result-row"><span class="rk">Full Path</span><span class="rv">${d.fullPath}</span></div>
      </div>
      <div class="result-note">
        ℹ️ Decoded from CNIC structure — shows <strong>registered region</strong>, not current address.
        Matched ${d.matchedLen} digit(s) of the location code.
      </div>
      <div class="result-gate">
        🔒 <strong>Want the full SIM/CNIC database lookup?</strong>
        <button class="gate-btn" onclick="openModal()">Install CLI →</button>
      </div>
    </div>`;
}

function renderPhone(d, clean) {
  const carrier = detectCarrier(clean);
  const national = formatPhoneNational(clean);
  const local = formatPhoneLocal(clean);
  const international = formatPhoneInternational(clean);
  const e164 = formatPhoneE164(clean);

  return `
    <div class="result-inner">
      <div class="result-title">📞 PHONE INTELLIGENCE</div>
      <div class="result-grid">
        <div class="result-row"><span class="rk">National</span><span class="rv hl">${national}</span></div>
        <div class="result-row"><span class="rk">Local</span><span class="rv">${local}</span></div>
        <div class="result-row"><span class="rk">International</span><span class="rv hl">${international}</span></div>
        <div class="result-row"><span class="rk">E164</span><span class="rv">${e164}</span></div>
        <div class="result-row"><span class="rk">Country Code</span><span class="rv">+92 (PK)</span></div>
        <div class="result-row"><span class="rk">Country</span><span class="rv">Pakistan</span></div>
        <div class="result-row"><span class="rk">Carrier</span><span class="rv hl">${carrier || "Unknown"}</span></div>
        <div class="result-row"><span class="rk">Line Type</span><span class="rv">Mobile</span></div>
        <div class="result-row"><span class="rk">Timezone</span><span class="rv">Asia/Karachi (UTC+5)</span></div>
        <div class="result-row"><span class="rk">Region</span><span class="rv">PK</span></div>
      </div>
      <div class="result-note">
        ℹ️ Decoded from the number prefix using ITU-T E.164 formatting — no database lookup.
      </div>
      <div class="result-gate">
        🔒 <strong>Want to see all SIMs registered against this number?</strong>
        <button class="gate-btn" onclick="openModal()">Install CLI →</button>
      </div>
    </div>`;
}

function renderSIMAttempt(clean) {
  const carrier = detectCarrier(clean);
  const local = formatPhoneLocal(clean);
  const national = formatPhoneNational(clean);
  const international = formatPhoneInternational(clean);
  const e164 = formatPhoneE164(clean);

  return `
    <div class="result-inner">
      <div class="result-title">📱 SIM LOOKUP</div>
      <div class="result-grid">
        <div class="result-row"><span class="rk">Local</span><span class="rv hl">${local}</span></div>
        <div class="result-row"><span class="rk">National</span><span class="rv">${national}</span></div>
        <div class="result-row"><span class="rk">International</span><span class="rv hl">${international}</span></div>
        <div class="result-row"><span class="rk">E164</span><span class="rv">${e164}</span></div>
        <div class="result-row"><span class="rk">Country Code</span><span class="rv">+92 (PK)</span></div>
        <div class="result-row"><span class="rk">Carrier</span><span class="rv hl">${carrier || "Unknown"}</span></div>
        <div class="result-row"><span class="rk">Type</span><span class="rv">Mobile (SIM)</span></div>
        <div class="result-row"><span class="rk">Timezone</span><span class="rv">Asia/Karachi (UTC+5)</span></div>
      </div>
      <div class="result-note warn">
        ⚠️ Full SIM ownership lookup (CNIC, name, address) requires the CLI tool.
        Browser sandbox cannot query the database directly.
      </div>
      <div class="result-gate">
        🔒 <strong>The juicy data is one command away.</strong>
        <button class="gate-btn" onclick="openModal()">Install CLI →</button>
      </div>
    </div>`;
}

/* ==================== MAIN HANDLER ==================== */
function handleAnalyze() {
  const raw = document.getElementById("queryInput").value.trim();
  if (!raw) {
    document.getElementById("toolHint").textContent = "Enter a number to begin.";
    return;
  }

  const { type, clean } = detectType(raw);

  if (type === "unknown") {
    showResult(`
      <div class="result-inner">
        <div class="result-error">✗ Unrecognized format</div>
        <div class="result-hint">Enter 13 digits (CNIC) or 11-15 digits (SIM/phone).</div>
      </div>`);
    return;
  }

  if (type === "cnic") {
    showResult(renderCNIC(decodeCNIC(clean)));
  } else if (type === "sim") {
    showResult(renderSIMAttempt(clean));
  } else if (type === "phone") {
    showResult(renderPhone({}, clean));
  }
}

/* ==================== MODAL ==================== */
function openModal() {
  document.getElementById("modal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closeModal() {
  document.getElementById("modal").style.display = "none";
  document.body.style.overflow = "";
}

/* ==================== UTIL ==================== */
function copyCode(btn) {
  const code = btn.closest(".code-block").querySelector("code").innerText;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = "✓ Copied";
    setTimeout(() => (btn.textContent = "Copy"), 2000);
  });
}

/* ==================== INIT ==================== */
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("queryInput");
  const btn = document.getElementById("queryBtn");

  btn.addEventListener("click", handleAnalyze);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleAnalyze();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
});
