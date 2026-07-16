const { getSheetsClient } = require("./sheets-common");

const URLS_TAB = "Pages Urls";

async function main() {
  const spreadsheetId = process.env.SPREADSHEET_ID;
  const siteName = process.env.SITE_NAME;
  const siteUrl = process.env.SITE_URL;

  if (!spreadsheetId) throw new Error("SPREADSHEET_ID is required");
  if (!siteName) throw new Error("SITE_NAME is required");
  if (!siteUrl) throw new Error("SITE_URL is required");

  const sheets = await getSheetsClient();

  await sheets.spreadsheets.values.append({
    spreadsheetId,
    range: `${URLS_TAB}!A:C`,
    valueInputOption: "RAW",
    insertDataOption: "INSERT_ROWS",
    requestBody: {
      values: [[siteName, siteUrl, new Date().toISOString()]],
    },
  });

  console.log(`Appended ${siteName} -> ${siteUrl} to "${URLS_TAB}"`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
