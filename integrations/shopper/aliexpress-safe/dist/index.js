import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
const HOST = "https://www.aliexpress.com";
const API_HOST = "https://www.aliexpress.com";
const MAX_TEXT = 120;
const MAX_ITEMS = 12;
const MAX_BODY = 256 * 1024;
const MAX_OUTPUT = 80_000;
const MAX_TIMEOUT = 15_000;
const TOOLS = ["search_aliexpress", "get_aliexpress_product", "search_aliexpress_bundle_deals", "build_aliexpress_bundle"];
const schema = (description, properties, required = []) => ({ type: "object", description, properties, required, additionalProperties: false });
const annotations = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true };
const tools = [
    { name: "search_aliexpress", description: "Search public AliExpress listings.", annotations, inputSchema: schema("Bounded search query and page.", { query: { type: "string", maxLength: MAX_TEXT }, page: { type: "integer", minimum: 1, maximum: 5 }, sort: { type: "string", enum: ["default", "orders", "price_asc", "price_desc"] }, min_price: { type: "number", minimum: 0, maximum: 100000 }, max_price: { type: "number", minimum: 0, maximum: 100000 } }, ["query"]) },
    { name: "get_aliexpress_product", description: "Read one public AliExpress product page.", annotations, inputSchema: schema("Numeric product id only.", { product_id: { type: "string", pattern: "^[0-9]{8,20}$", maxLength: 20 } }, ["product_id"]) },
    { name: "search_aliexpress_bundle_deals", description: "Find public listings for a small set of bundle terms.", annotations, inputSchema: schema("Search one bounded category and optional terms.", { query: { type: "string", maxLength: MAX_TEXT }, bundle_category: { type: "string", maxLength: 60 }, limit: { type: "integer", minimum: 1, maximum: 8 } }, ["query"]) },
    { name: "build_aliexpress_bundle", description: "Compose a read-only bundle shortlist from bounded terms.", annotations, inputSchema: schema("At most four search terms.", { queries: { type: "array", minItems: 1, maxItems: 4, items: { type: "string", maxLength: 80 } }, bundle_category: { type: "string", maxLength: 60 }, limit: { type: "integer", minimum: 1, maximum: 4 } }, ["queries"]) }
];
function fail() { throw new Error("Invalid input or temporary AliExpress error."); }
function text(v, required = false, max = MAX_TEXT) { if (v === undefined && !required)
    return undefined; if (typeof v !== "string" || v.length > max || /[\u0000-\u001f\u007f]/.test(v) || (required && !v.trim()))
    fail(); return v.trim(); }
function integer(v, fallback, max) { if (v === undefined)
    return fallback; if (!Number.isInteger(v) || Number(v) < 1 || Number(v) > max)
    fail(); return Number(v); }
function price(v) { if (v === undefined)
    return undefined; if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 100000)
    fail(); return v; }
function productId(v) { const s = text(v, true, 20); if (!/^[0-9]{8,20}$/.test(s))
    fail(); return s; }
function money(v) { const n = Number(String(v ?? "").replace(/[^0-9.]/g, "")); return Number.isFinite(n) && n >= 0 && n <= 1000000 ? n : null; }
function clean(v, max = 240) { return typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max) : ""; }
function envelope(data) { const out = JSON.stringify({ trust: "untrusted_marketplace", source: "aliexpress.com", data }); if (out.length > MAX_OUTPUT)
    fail(); return out; }
async function get(path, params = {}) {
    const url = new URL(path, API_HOST);
    for (const [k, v] of Object.entries(params))
        url.searchParams.set(k, v);
    if (url.origin !== HOST || !url.pathname.startsWith("/"))
        fail();
    const response = await fetch(url, { method: "GET", headers: { accept: "text/html,application/xhtml+xml" }, redirect: "error", signal: AbortSignal.timeout(MAX_TIMEOUT) });
    if (!response.ok)
        fail();
    const length = Number(response.headers.get("content-length") ?? 0);
    if (length > MAX_BODY || !response.body)
        fail();
    const reader = response.body.getReader();
    const chunks = [];
    let total = 0;
    try {
        for (;;) {
            const part = await reader.read();
            if (part.done)
                break;
            total += part.value.byteLength;
            if (total > MAX_BODY) {
                await reader.cancel();
                fail();
            }
            chunks.push(part.value);
        }
    }
    finally {
        reader.releaseLock();
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
    }
    return new TextDecoder().decode(bytes);
}
function listings(html, limit = MAX_ITEMS) {
    const out = [];
    const re = /(?:item-title|product-title)[^>]*>([^<]{1,300})[\s\S]{0,800}?(?:\$|US\s*\$)\s*([0-9.,]+)/gi;
    let match;
    while (out.length < limit && (match = re.exec(html)))
        out.push({ title: clean(match[1]), price: money(match[2]), currency: "USD" });
    return out;
}
async function search(query, page = 1, extra = {}, limit = MAX_ITEMS) { const html = await get("/w/wholesale.html", { SearchText: query, page: String(page), ...extra }); return { query, page, items: listings(html, limit) }; }
async function call(name, a) {
    if (name === "search_aliexpress") {
        const q = text(a.query, true);
        const page = integer(a.page, 1, 5);
        const sort = text(a.sort, false, 20) ?? "default";
        if (!["default", "orders", "price_asc", "price_desc"].includes(sort))
            fail();
        const minimum = price(a.min_price);
        const maximum = price(a.max_price);
        if (minimum !== undefined && maximum !== undefined && minimum > maximum)
            fail();
        const extra = { sortType: sort };
        if (minimum !== undefined)
            extra.minPrice = String(minimum);
        if (maximum !== undefined)
            extra.maxPrice = String(maximum);
        return envelope(await search(q, page, extra));
    }
    if (name === "get_aliexpress_product") {
        const id = productId(a.product_id);
        const html = await get(`/item/${id}.html`);
        return envelope({ product: { id, title: clean((html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) ?? [])[1], 300), price: money((html.match(/(?:US\s*)?\$\s*([0-9.,]+)/i) ?? [])[1]), url: `${HOST}/item/${id}.html` } });
    }
    if (name === "search_aliexpress_bundle_deals") {
        const q = text(a.query, true);
        const category = text(a.bundle_category, false, 60);
        return envelope({ category: category ?? null, ...(await search(category ? `${category} ${q}` : q, 1, {}, integer(a.limit, 8, 8))) });
    }
    if (name === "build_aliexpress_bundle") {
        if (!Array.isArray(a.queries) || a.queries.length < 1 || a.queries.length > 4)
            fail();
        const category = text(a.bundle_category, false, 60);
        const limit = integer(a.limit, 4, 4);
        const queries = a.queries.map(x => text(x, true, 80));
        const bundles = await Promise.all(queries.map(q => search(category ? `${category} ${q}` : q, 1, {}, limit)));
        return envelope({ category: category ?? null, bundles });
    }
    fail();
}
export function createServer() { const server = new Server({ name: "aliexpress-safe", version: "1.0.0" }, { capabilities: { tools: {} } }); server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools })); server.setRequestHandler(CallToolRequestSchema, async ({ params }) => { try {
    if (!TOOLS.includes(params.name))
        fail();
    return { content: [{ type: "text", text: await call(params.name, (params.arguments ?? {})) }] };
}
catch {
    return { isError: true, content: [{ type: "text", text: "Invalid input or temporary AliExpress error." }] };
} }); return server; }
await createServer().connect(new StdioServerTransport());
