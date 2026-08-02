const ACTIONS = new Set([
  "save",
  "unsave",
  "read",
  "more_method",
  "more_topic",
  "low_quality",
  "not_now",
  "not_llm",
  "irrelevant",
  "transferable",
  "useful",
  "unuseful",
  "not_useful",
]);

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin, env.ALLOWED_ORIGIN);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }

    const url = new URL(request.url);
    if (url.pathname === "/api/health" && request.method === "GET") {
      return json({ ok: true, service: "dawnlit-api" }, 200, headers);
    }

    if (!authorized(request, env.ADMIN_TOKEN)) {
      return json({ error: "Unauthorized" }, 401, headers);
    }

    try {
      if (url.pathname === "/api/profile" && request.method === "GET") {
        return getProfile(env, headers);
      }
      if (url.pathname === "/api/profile" && request.method === "PUT") {
        return putProfile(request, env, headers);
      }
      if (url.pathname === "/api/feedback" && request.method === "GET") {
        return getFeedback(url, env, headers);
      }
      if (url.pathname === "/api/feedback" && request.method === "POST") {
        return postFeedback(request, env, headers);
      }
      return json({ error: "Not found" }, 404, headers);
    } catch (error) {
      return json({ error: error.message || "Internal error" }, 500, headers);
    }
  },
};

function authorized(request, expected) {
  if (!expected) return false;
  return request.headers.get("Authorization") === `Bearer ${expected}`;
}

function corsHeaders(origin, allowedOrigin) {
  const allowed =
    allowedOrigin === "*" || (origin && origin === allowedOrigin) ? origin || "*" : allowedOrigin;
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, PUT, POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...extraHeaders,
    },
  });
}

async function getProfile(env, headers) {
  const row = await env.DB.prepare("SELECT payload FROM profiles WHERE id = 'current'").first();
  if (!row) return json({ error: "Profile has not been initialized" }, 404, headers);
  return json(JSON.parse(row.payload), 200, headers);
}

async function putProfile(request, env, headers) {
  const profile = await request.json();
  if (!profile || !Array.isArray(profile.topics) || !profile.ranking || !profile.scope) {
    return json({ error: "Invalid profile" }, 400, headers);
  }
  const payload = JSON.stringify(profile);
  if (payload.length > 100_000) {
    return json({ error: "Profile is too large" }, 413, headers);
  }
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        "INSERT INTO profiles (id, payload, updated_at) VALUES ('current', ?, ?) " +
          "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at",
      )
      .bind(payload, now),
    env.DB
      .prepare("INSERT INTO profile_versions (payload, created_at) VALUES (?, ?)")
      .bind(payload, now),
  ]);
  return json({ ok: true, updated_at: now }, 200, headers);
}

async function getFeedback(url, env, headers) {
  const requested = Number(url.searchParams.get("limit") || 200);
  const limit = Math.max(1, Math.min(requested, 1000));
  const result = await env.DB.prepare(
    "SELECT id, paper_id, action, title, abstract, topics, created_at " +
      "FROM feedback ORDER BY created_at DESC LIMIT ?",
  )
    .bind(limit)
    .all();
  const items = result.results.map((row) => ({
    ...row,
    topics: JSON.parse(row.topics || "[]"),
  }));
  return json({ items }, 200, headers);
}

async function postFeedback(request, env, headers) {
  const item = await request.json();
  if (!item?.id || !item.paper_id || !ACTIONS.has(item.action)) {
    return json({ error: "Invalid feedback" }, 400, headers);
  }
  await env.DB.prepare(
    "INSERT OR REPLACE INTO feedback " +
      "(id, paper_id, action, title, abstract, topics, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
  )
    .bind(
      String(item.id).slice(0, 100),
      String(item.paper_id).slice(0, 100),
      item.action,
      String(item.title || "").slice(0, 1000),
      String(item.abstract || "").slice(0, 12_000),
      JSON.stringify(Array.isArray(item.topics) ? item.topics : []),
      item.created_at || new Date().toISOString(),
    )
    .run();
  return json({ ok: true }, 201, headers);
}
