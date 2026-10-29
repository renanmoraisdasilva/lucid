#!/usr/bin/env node
/**
 * Run `uv` from PATH, or from a known install location when the terminal's PATH
 * is stale (common right after installing uv with winget).
 *
 * Usage: node tools/uv.mjs <uv args...>
 *   node tools/uv.mjs sync
 *   node tools/uv.mjs run uvicorn lucid.main:app --reload
 */
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const backendDir = fileURLToPath(new URL("../backend", import.meta.url));

function onPath() {
  const probe = spawnSync(process.platform === "win32" ? "where" : "which", ["uv"], {
    encoding: "utf8",
  });
  return probe.status === 0;
}

function knownLocations() {
  const locations = [];
  if (process.platform === "win32") {
    locations.push(join(homedir(), ".local", "bin", "uv.exe"));
    const packages = join(process.env.LOCALAPPDATA ?? "", "Microsoft", "WinGet", "Packages");
    if (existsSync(packages)) {
      for (const entry of readdirSync(packages)) {
        if (entry.startsWith("astral-sh.uv_")) {
          locations.push(join(packages, entry, "uv.exe"));
        }
      }
    }
  } else {
    locations.push(join(homedir(), ".local", "bin", "uv"));
  }
  return locations;
}

function resolveUv() {
  if (onPath()) {
    return "uv";
  }
  return knownLocations().find((candidate) => existsSync(candidate)) ?? null;
}

const uv = resolveUv();
if (uv === null) {
  console.error(
    "uv was not found. Install it with:\n" +
      "  winget install --id=astral-sh.uv -e\n" +
      "then open a new terminal.",
  );
  process.exit(1);
}

const result = spawnSync(uv, process.argv.slice(2), { cwd: backendDir, stdio: "inherit" });
process.exit(result.status ?? 1);
