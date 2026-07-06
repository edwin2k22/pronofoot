import { createCipheriv, pbkdf2Sync, randomBytes } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";

const [, , password, ...files] = process.argv;

if (!password || files.length === 0) {
  console.error("Usage: node scripts/encrypt_static_site.mjs <password> <file...>");
  process.exit(1);
}

const ITERATIONS = 250000;

function b64(buf) {
  return Buffer.from(buf).toString("base64");
}

function encryptHtml(file) {
  const html = readFileSync(file, "utf8");
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = pbkdf2Sync(password, salt, ITERATIONS, 32, "sha256");
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const encrypted = Buffer.concat([cipher.update(html, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  const payload = {
    v: 1,
    kdf: "PBKDF2-SHA256",
    iterations: ITERATIONS,
    salt: b64(salt),
    iv: b64(iv),
    data: b64(Buffer.concat([encrypted, tag])),
  };
  writeFileSync(file, renderLockedPage(payload, basename(file)), "utf8");
}

function renderLockedPage(payload, pageName) {
  const payloadJson = JSON.stringify(payload);
  return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>PronoFoot - acces prive</title>
<style>
  :root{color-scheme:dark;--bg:#071019;--panel:#101c2b;--line:#26384f;--txt:#edf6ff;--muted:#8ba0b7;--acc:#34d399;--bad:#fb7185}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 20% 0,rgba(52,211,153,.16),transparent 34%),var(--bg);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--txt);padding:20px}
  main{width:min(420px,100%);background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.025));border:1px solid var(--line);border-radius:12px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.42)}
  h1{margin:0 0 6px;font-size:22px}
  p{margin:0 0 18px;color:var(--muted);line-height:1.45;font-size:14px}
  label{display:block;font-size:12px;font-weight:800;text-transform:uppercase;color:var(--muted);margin-bottom:7px}
  input{width:100%;border:1px solid var(--line);border-radius:8px;background:#07111f;color:var(--txt);font-size:16px;padding:12px 13px;outline:none}
  input:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(52,211,153,.16)}
  button{width:100%;margin-top:12px;border:0;border-radius:8px;background:var(--acc);color:#04130d;font-weight:900;padding:12px 14px;cursor:pointer}
  button:disabled{opacity:.65;cursor:wait}
  .err{min-height:20px;margin-top:12px;color:var(--bad);font-size:13px}
  .hint{margin-top:14px;font-size:12px;color:var(--muted)}
</style>
</head>
<body>
<main>
  <h1>PronoFoot prive</h1>
  <p>Cette version est protegee. Entre le code que le proprietaire t'a donne pour ouvrir ${pageName === "scouting.html" ? "le scouting" : "le dashboard"}.</p>
  <form id="gate">
    <label for="pass">Code d'acces</label>
    <input id="pass" name="pass" type="password" autocomplete="current-password" aria-label="Code d'acces" autofocus>
    <button id="btn" type="submit">Deverrouiller</button>
    <div class="err" id="err" role="alert"></div>
  </form>
  <div class="hint">Le lien seul ne suffit pas : il faut aussi le code d'acces.</div>
</main>
<script id="payload" type="application/json">${payloadJson.replace(/</g, "\\u003c")}</script>
<script>
const form = document.getElementById("gate");
const input = document.getElementById("pass");
const btn = document.getElementById("btn");
const err = document.getElementById("err");
const payload = JSON.parse(document.getElementById("payload").textContent);
const SESSION_PASS_KEY = "pronofoot-session-pass";

function fromB64(s){
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function derive(password){
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    {name:"PBKDF2", salt:fromB64(payload.salt), iterations:payload.iterations, hash:"SHA-256"},
    material,
    {name:"AES-GCM", length:256},
    false,
    ["decrypt"]
  );
}

form.addEventListener("submit", async (event)=>{
  event.preventDefault();
  err.textContent = "";
  btn.disabled = true;
  try{
    const key = await derive(input.value);
    const html = await crypto.subtle.decrypt({name:"AES-GCM", iv:fromB64(payload.iv)}, key, fromB64(payload.data));
    const text = new TextDecoder().decode(html);
    sessionStorage.setItem(SESSION_PASS_KEY, input.value);
    document.open();
    document.write(text);
    document.close();
  }catch(e){
    sessionStorage.removeItem(SESSION_PASS_KEY);
    err.textContent = "Code incorrect. Verifie le code recu.";
    btn.disabled = false;
    input.select();
  }
});

const savedPass = sessionStorage.getItem(SESSION_PASS_KEY);
if(savedPass){
  input.value = savedPass;
  setTimeout(()=>form.requestSubmit(), 0);
}
</script>
</body>
</html>`;
}

for (const file of files) {
  encryptHtml(file);
  console.log(`encrypted ${file}`);
}
