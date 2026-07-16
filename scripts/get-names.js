const fs = require("fs");
const { getSheetsClient, slugify } = require("./sheets-common");

const NAMES_TAB = "Pages Names";
const URLS_TAB = "Pages Urls";

async function main() {
  const spreadsheetId = process.env.SPREADSHEET_ID;
  const numPages = parseInt(process.env.NUM_PAGES || "1", 10);
  const nameSource = process.env.NAME_SOURCE || "from_sheet"; // "from_sheet" | "manual"
  const manualNames = (process.env.MANUAL_NAMES || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const baseSiteName = process.env.BASE_SITE_NAME || "site";

  if (!spreadsheetId) throw new Error("SPREADSHEET_ID is required");
  if (!numPages || numPages < 1) throw new Error("NUM_PAGES must be >= 1");

  const sheets = await getSheetsClient();
  let candidateNames = [];

  if (nameSource === "manual") {
    candidateNames = manualNames;
  } else {
    // Pull the candidate name list from "Pages Names" column A
    const namesResp = await sheets.spreadsheets.values.get({
      spreadsheetId,
      range: `${NAMES_TAB}!A:A`,
    });
    const allNames = (namesResp.data.values || [])
      .flat()
      .map((s) => String(s).trim())
      .filter(Boolean);

    // Skip a header row if the first cell looks like a header, not a name
    if (allNames.length && /name/i.test(allNames[0])) {
      allNames.shift();
    }

    // Exclude names already used (already present in "Pages Urls" column A)
    let usedNames = [];
    try {
      const usedResp = await sheets.spreadsheets.values.get({
        spreadsheetId,
        range: `${URLS_TAB}!A:A`,
      });
      usedNames = (usedResp.data.values || []).flat().map((s) => String(s).trim());
    } catch (e) {
      // Tab might not exist yet on first run — that's fine.
    }

    candidateNames = allNames.filter((n) => !usedNames.includes(n));
  }

  // Fill up to numPages, generating fallback names if we run short
  const picked = [];
  for (let i = 0; i < numPages; i++) {
    if (candidateNames[i]) {
      picked.push(candidateNames[i]);
    } else {
      picked.push(`${baseSiteName}-${Date.now()}-${i}`);
    }
  }

  const slugs = picked.map((n, i) => slugify(n, i));

  console.log("Picked names:", picked);
  console.log("Slugs:", slugs);

  const matrix = JSON.stringify(slugs);
  const githubOutput = process.env.GITHUB_OUTPUT;
  if (githubOutput) {
    fs.appendFileSync(githubOutput, `matrix=${matrix}\n`);
  } else {
    console.log(`matrix=${matrix}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
