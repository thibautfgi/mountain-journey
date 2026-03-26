#!/usr/bin/env node
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const choice = process.argv[2] ?? "local";
const scriptDir = __dirname;
const rootDir = path.resolve(scriptDir, "..");
const outputDir = path.join(scriptDir, "out");
fs.mkdirSync(outputDir, { recursive: true });

const resolveTarget = () => {
  if (choice === "local") return "k6-script-local.js";
  if (choice === "prod") return "k6-script-prod.js";
  const candidate = path.join(scriptDir, choice);
  if (fs.existsSync(candidate)) return choice;
  console.error("Usage: npm run k6:<local|prod> or node run-k6.js <script>");
  process.exit(1);
};

const targetScript = resolveTarget();
const scriptBase = path.basename(targetScript, path.extname(targetScript));
const stamp = new Date().toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
const runDir = path.join(outputDir, `${scriptBase}-${stamp}`);
fs.mkdirSync(runDir, { recursive: true });
const csvFile = "result.csv";
const summaryFile = "summary.json";

const dockerArgs = [
  "compose",
  "run",
  "--rm",
  "k6",
  "run",
  `/scripts/${targetScript}`,
  "-o",
  `csv=/scripts/out/${scriptBase}-${stamp}/${csvFile}`,
  "--summary-export",
  `/scripts/out/${scriptBase}-${stamp}/${summaryFile}`
];

execFileSync("docker", dockerArgs, { stdio: "inherit", cwd: rootDir });
