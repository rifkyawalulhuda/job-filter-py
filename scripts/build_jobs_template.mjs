import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const outputDir = path.join(projectRoot, "outputs", "job-template");

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Jobs Template");

const headers = [
  "job_title",
  "company",
  "location",
  "work_mode",
  "job_level",
  "salary_min",
  "salary_max",
  "currency",
  "skills",
  "posted_date",
  "job_type",
  "apply_url",
  "description",
];

const blankRows = Array.from({ length: 20 }, () => Array(headers.length).fill(""));
sheet.getRange("A1:M21").values = [headers, ...blankRows];

sheet.getRange("A1:M1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};

sheet.getRange("A2:M21").format = {
  fill: "#FFFFFF",
};

sheet.getRange("A1:M21").format.borders = {
  top: { style: "thin", color: "#D9E2F3" },
  bottom: { style: "thin", color: "#D9E2F3" },
  left: { style: "thin", color: "#D9E2F3" },
  right: { style: "thin", color: "#D9E2F3" },
};

sheet.getRange("F2:G21").format.numberFormat = "0";
sheet.getRange("J2:J21").format.numberFormat = "yyyy-mm-dd";

const widths = [22, 22, 18, 14, 14, 14, 14, 10, 24, 14, 14, 34, 42];
for (let index = 0; index < widths.length; index += 1) {
  sheet.getRangeByIndexes(0, index, 21, 1).format.columnWidth = widths[index];
}

sheet.freezePanes.freezeRows(1);

const table = sheet.tables.add("A1:M21", true, "JobsTemplateTable");
table.style = "TableStyleMedium2";

const instructionSheet = workbook.worksheets.add("Instructions");
instructionSheet.getRange("A1:B8").values = [
  ["Field", "Notes"],
  ["job_title", "Required. Example: Backend Engineer"],
  ["company", "Required. Example: Acme Inc"],
  ["work_mode", "Recommended values: remote, hybrid, onsite"],
  ["job_level", "Recommended values: internship, entry, junior, mid, senior, lead, manager"],
  ["skills", "Use semicolon-separated values. Example: Python;FastAPI;PostgreSQL"],
  ["posted_date", "Use yyyy-mm-dd when available"],
  ["apply_url", "Paste the public application link when available"],
];
instructionSheet.getRange("A1:B1").format = {
  fill: "#2F5597",
  font: { bold: true, color: "#FFFFFF" },
};
instructionSheet.getRange("A1:B8").format.borders = {
  top: { style: "thin", color: "#D9E2F3" },
  bottom: { style: "thin", color: "#D9E2F3" },
  left: { style: "thin", color: "#D9E2F3" },
  right: { style: "thin", color: "#D9E2F3" },
};
instructionSheet.getRange("A:A").format.columnWidth = 18;
instructionSheet.getRange("B:B").format.columnWidth = 68;
instructionSheet.freezePanes.freezeRows(1);

const preview = await workbook.render({
  sheetName: "Jobs Template",
  range: "A1:M12",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "job_vacancy_template_preview.png"),
  new Uint8Array(await preview.arrayBuffer()),
);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "job_vacancy_template.xlsx"));
