import { readFileSync } from "node:fs";
const text = readFileSync(new URL("./src/index.ts", import.meta.url), "utf8");
const expected = ["search_aliexpress", "get_aliexpress_product", "search_aliexpress_bundle_deals", "build_aliexpress_bundle"];
const names = [...text.matchAll(/name: \"([^\"]+)\"/g)].map(m => m[1]).filter(x => expected.includes(x));
if (names.length !== expected.length || new Set(names).size !== expected.length) throw new Error("tool policy");
for (const word of ["cookie", "browser", "proxy", "oauth", "account", "cart", "http://", "fetch(url)"]) if (text.toLowerCase().includes(word.toLowerCase())) throw new Error(`forbidden: ${word}`);
for (const method of ["POST", "PUT", "PATCH", "DELETE"]) if (new RegExp(`\\b${method}\\b`).test(text)) throw new Error(`forbidden: ${method}`);
for (const invariant of ["const HOST = \"https://www.aliexpress.com\"", "redirect: \"error\"", "method: \"GET\"", "MAX_BODY = 256 * 1024", "MAX_OUTPUT = 80_000", "trust: \"untrusted_marketplace\"", "readOnlyHint: true", "additionalProperties: false", "AbortSignal.timeout(MAX_TIMEOUT)", "Number.isFinite(v)", "minimum > maximum", "Promise.all"]) if (!text.includes(invariant)) throw new Error(`missing invariant: ${invariant}`);
console.log("audit ok");
