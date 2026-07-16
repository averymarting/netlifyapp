const { google } = require("googleapis");

/**
 * Builds an authenticated Sheets client from a service account JSON
 * stored in the GOOGLE_SERVICE_ACCOUNT_JSON secret (as a single-line string).
 */
async function getSheetsClient() {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!raw) {
    throw new Error("GOOGLE_SERVICE_ACCOUNT_JSON env var is missing");
  }
  const credentials = JSON.parse(raw);

  const auth = new google.auth.GoogleAuth({
    credentials,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });

  const client = await auth.getClient();
  return google.sheets({ version: "v4", auth: client });
}

/**
 * Turns any string into a safe Netlify site-name slug.
 */
function slugify(name, fallbackIndex) {
  const slug = String(name || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || `site-${fallbackIndex}`;
}

module.exports = { getSheetsClient, slugify };
