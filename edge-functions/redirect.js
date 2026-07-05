export default async (request, context) => {
  const url = new URL(request.url);
  const ref = url.searchParams.get("ref") || "default";

  const destinations = {
    partner1: "https://example.com/?src=partner1",
    partner2: "https://example.com/?src=partner2",
    default: "https://example.com"
  };

  const target = destinations[ref] || destinations.default;

  return Response.redirect(target, 302);
};
