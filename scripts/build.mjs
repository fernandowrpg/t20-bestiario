// Compila as fontes JSON em compêndio LevelDB e monta dist/ com o módulo pronto.
// Uso: node scripts/build.mjs [versão]
import { compilePack } from "@foundryvtt/foundryvtt-cli";
import fs from "node:fs";
import path from "node:path";

const ID = "bestiario-de-arton-t20";
const version = (process.argv[2] || "").replace(/^v/, "");
const out = path.join("dist", ID);

fs.rmSync("dist", { recursive: true, force: true });
fs.mkdirSync(path.join(out, "packs"), { recursive: true });

const manifest = JSON.parse(fs.readFileSync("module.json", "utf8"));
if (version) {
  manifest.version = version;
  manifest.download = `https://github.com/fernandowrpg/t20-bestiario/releases/download/v${version}/${ID}.zip`;
}
for (const pack of manifest.packs) {
  await compilePack(path.join("src", "packs", pack.name), path.join(out, pack.path), { log: false });
  fs.rmSync(path.join(out, pack.path, "LOCK"), { force: true });
}
fs.writeFileSync(path.join(out, "module.json"), JSON.stringify(manifest, null, 2) + "\n");
fs.writeFileSync(path.join("dist", "module.json"), JSON.stringify(manifest, null, 2) + "\n");
fs.copyFileSync("README.md", path.join(out, "README.md"));
console.log(`Módulo ${manifest.id} v${manifest.version} montado em ${out}`);
