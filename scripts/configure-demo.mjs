import { randomBytes } from "node:crypto";
import { existsSync, writeFileSync } from "node:fs";
const envPath = new URL("../src/backend/.env", import.meta.url);
const composePath = new URL("../.env.demo", import.meta.url);
if (existsSync(envPath) || existsSync(composePath)) {
  throw new Error("Local demo configuration already exists. Keep it or remove it deliberately before regenerating.");
}
const databasePassword = randomBytes(24).toString("hex");
const jwtSecret = randomBytes(32).toString("hex");
const brandPassword = randomBytes(24).toString("hex");
writeFileSync(composePath, `DEMO_DATABASE_PASSWORD=${databasePassword}\n`, { mode: 0o600, flag: "wx" });
writeFileSync(envPath, `APP_ENV=development\nAPP_DEBUG=false\nDATABASE_URL=postgresql+asyncpg://portfolio_demo:${databasePassword}@127.0.0.1:15432/portfolio_demo\nREDIS_URL=redis://127.0.0.1:16379/0\nJWT_SECRET_KEY=${jwtSecret}\nDEMO_BRAND_PASSWORD=${brandPassword}\nFRONTEND_BASE_URL=http://127.0.0.1:3200\nAPI_BASE_URL=http://127.0.0.1:18000/api/v1\nCORS_ORIGINS=http://127.0.0.1:3200,http://127.0.0.1:3201\n`, { mode: 0o600, flag: "wx" });
console.log("Created ignored local demo configuration with fresh random credentials. No real service credentials are configured.");
