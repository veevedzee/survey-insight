// Copies the Python analysis package and the sample survey into public/py/,
// so the browser can load them into Pyodide. Runs before `npm run dev` and
// `npm run build`; the output is generated, so it's git-ignored.
//
// api.py and schemas.py are left out: they are the FastAPI server layer, which
// the in-browser version doesn't need.
import { copyFileSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const packageDir = join(root, "backend", "survey_insight");
const sample = join(root, "sample_data", "student_wellbeing_survey.csv");
const out = join(root, "frontend", "public", "py");
const SERVER_ONLY = new Set(["api.py", "schemas.py"]);

rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "survey_insight"), { recursive: true });

const files = readdirSync(packageDir).filter((f) => f.endsWith(".py") && !SERVER_ONLY.has(f));
for (const file of files) {
  copyFileSync(join(packageDir, file), join(out, "survey_insight", file));
}
copyFileSync(sample, join(out, "student_wellbeing_survey.csv"));

writeFileSync(
  join(out, "manifest.json"),
  JSON.stringify({ package: files.map((f) => `survey_insight/${f}`), sample: "student_wellbeing_survey.csv" }, null, 2),
);
console.log(`Copied ${files.length} Python modules and the sample survey to public/py/`);
