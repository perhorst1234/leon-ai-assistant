import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const HOST = "https://www.vinted.nl";
const MAX_TEXT = 80;
const MAX_ITEMS = 20;
const MAX_BODY = 256 * 1024;
const MAX_OUTPUT = 100000;
const TOOLS = ["search_items", "get_item", "get_seller", "compare_prices", "get_trending"];
const schema = (description: string, properties: Record<string, unknown>, required: string[] = []) => ({type:"object",description,properties,required,additionalProperties:false});
const tools = [
  {name:"search_items",description:"Zoek advertenties op Vinted Nederland.",annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true},inputSchema:schema("Zoekterm en optionele filters.",{query:{type:"string",maxLength:MAX_TEXT},page:{type:"integer",minimum:1,maximum:10},limit:{type:"integer",minimum:1,maximum:MAX_ITEMS}},["query"])},
  {name:"get_item",description:"Lees één advertentie.",annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true},inputSchema:schema("Advertentie-ID.",{itemId:{type:"integer",minimum:1,maximum:2147483647}},["itemId"])},
  {name:"get_seller",description:"Lees een verkopersprofiel.",annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true},inputSchema:schema("Verkoper-ID.",{sellerId:{type:"integer",minimum:1,maximum:2147483647}},["sellerId"])},
  {name:"compare_prices",description:"Vergelijk prijzen van een zoekterm.",annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true},inputSchema:schema("Zoekterm.",{query:{type:"string",maxLength:MAX_TEXT},limit:{type:"integer",minimum:1,maximum:MAX_ITEMS}},["query"])},
  {name:"get_trending",description:"Rangschik relevante advertenties op aantal favorieten binnen een begrensde sample.",annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true},inputSchema:schema("Optionele zoekterm.",{query:{type:"string",maxLength:MAX_TEXT},limit:{type:"integer",minimum:1,maximum:MAX_ITEMS}})}
];

function bad(): never { throw new Error("Ongeldige invoer of tijdelijke Vinted-fout."); }
function text(v: unknown, required = false): string | undefined { if (v === undefined && !required) return undefined; if (typeof v !== "string" || v.length > MAX_TEXT || /[\u0000-\u001f]/.test(v) || (required && !v.trim())) bad(); return v.trim(); }
function integer(v: unknown, fallback: number, maximum: number): number { if (v === undefined) return fallback; if (!Number.isInteger(v) || Number(v) < 1 || Number(v) > maximum) bad(); return Number(v); }
function id(v: unknown): number { if (!Number.isInteger(v) || Number(v) < 1 || Number(v) > 2147483647) bad(); return Number(v); }
async function get(path: string, query: Record<string,string> = {}) {
  const url = new URL(path, HOST); for (const [k,v] of Object.entries(query)) url.searchParams.set(k,v);
  if (url.origin !== HOST || !url.pathname.startsWith("/api/")) throw new Error("Ongeldige aanvraag.");
  const response = await fetch(url, {headers:{accept:"application/json"}, redirect:"error", signal:AbortSignal.timeout(10000)});
  if (!response.ok) throw new Error("Vinted-fout.");
  if (!(response.headers.get("content-type") ?? "").toLowerCase().includes("application/json")) throw new Error("Vinted-fout.");
  const announced = Number(response.headers.get("content-length") ?? 0); if (announced > MAX_BODY) throw new Error("Vinted-fout.");
  if (!response.body) throw new Error("Vinted-fout.");
  const reader = response.body.getReader(); let total = 0; const chunks: Uint8Array[] = [];
  try { for (;;) { const part = await reader.read(); if (part.done) break; total += part.value.byteLength; if (total > MAX_BODY) { await reader.cancel(); throw new Error("Vinted-fout."); } chunks.push(part.value); } }
  finally { reader.releaseLock(); }
  const bytes = new Uint8Array(total); let offset = 0; for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let data: unknown; try { data = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error("Vinted-fout."); }
  return data;
}
function clean(v: unknown, max = 200): string { return typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0,max) : ""; }
function itemId(v: unknown): number | null { const n=typeof v === "number" ? v : Number(v); return Number.isInteger(n)&&n>0&&n<=2147483647?n:null; }
function finite(v: unknown): number | null { const n=Number(v); return Number.isFinite(n)&&n>=0?n:null; }
function record(v: unknown): Record<string,unknown> { return typeof v === "object" && v !== null && !Array.isArray(v) ? v as Record<string,unknown> : {}; }
function envelope(data: unknown): string { const out = JSON.stringify({trust:"untrusted_marketplace",source:"vinted.nl",data}); if (out.length > MAX_OUTPUT) throw new Error("Vinted-fout."); return out; }
function money(value:unknown): {price:number|null,currency:string} { const x=record(value); const price=record(x.price); const n=Object.keys(price).length ? price.amount : x.price; const p=Number(n); return {price:Number.isFinite(p)&&p>=0?p:null,currency:clean(Object.keys(price).length ? price.currency_code : (x.currency ?? x.currency_code),8)}; }
type Item = {id:number|null,title:string,price:number|null,currency:string,brand:string,condition:string,size:string,favouriteCount:number|null,url:string|null};
function items(data: unknown): Item[] { const source=record(data).items; return (Array.isArray(source) ? source : []).slice(0,MAX_ITEMS).map(value=>{const x=record(value); const iid=itemId(x.id); const m=money(x); return {id:iid,title:clean(x.title),price:m.price,currency:m.currency,brand:clean(x.brand_title ?? x.brand,80),condition:clean(x.condition,40),size:clean(x.size,40),favouriteCount:finite(x.favourite_count ?? x.favouriteCount),url:iid?`https://www.vinted.nl/items/${iid}`:null};}); }
function prices(data: unknown): unknown { const vals = items(data).map(x=>x.price).filter((x): x is number=>typeof x === "number"); if (!vals.length) return {count:0}; vals.sort((a,b)=>a-b); const mid=Math.floor(vals.length/2); return {count:vals.length,min:vals[0],max:vals[vals.length-1],average:Math.round(vals.reduce((a,b)=>a+b,0)/vals.length*100)/100,median:vals.length%2?vals[mid]:(vals[mid-1]+vals[mid])/2}; }
async function call(name: string, a: Record<string,unknown>): Promise<string> {
  switch(name) {
    case "search_items": return envelope({query:clean(a.query),items:items(await get("/api/v2/catalog/items", {search_text:text(a.query,true)!, page:String(integer(a.page,1,10)), per_page:String(integer(a.limit,20,MAX_ITEMS))}))});
    case "get_item": { const raw=record(await get(`/api/v2/items/${id(a.itemId)}`)); const x=record(raw.item ?? raw); const iid=itemId(x.id); const m=money(x); return envelope({item:{id:iid,title:clean(x.title),description:clean(x.description,2000),price:m.price,currency:m.currency,brand:clean(x.brand_title ?? x.brand,80),condition:clean(x.condition,40),size:clean(x.size,40),url:iid?`https://www.vinted.nl/items/${iid}`:null}}); }
    case "get_seller": { const raw=record(await get(`/api/v2/users/${id(a.sellerId)}`)); const x=record(raw.user ?? raw); const sellerId=itemId(x.id); return envelope({seller:{id:sellerId,username:clean(x.login ?? x.username,80),feedback_rating:typeof x.feedback_rating === "number" ? x.feedback_rating : clean(x.feedback_rating,20),feedback_count:typeof x.feedback_count === "number" ? x.feedback_count : clean(x.feedback_count,20),city:clean(x.city,80),member_since:clean(x.created_at,40),url:sellerId?`https://www.vinted.nl/member/${sellerId}`:null}}); }
    case "compare_prices": { const x=await get("/api/v2/catalog/items", {search_text:text(a.query,true)!, per_page:String(integer(a.limit,20,MAX_ITEMS))}); return envelope({query:clean(a.query),statistics:prices(x)}); }
    case "get_trending": { const x=await get("/api/v2/catalog/items", {search_text:text(a.query) ?? "", order:"relevance", per_page:String(integer(a.limit,20,MAX_ITEMS))}); const ranked=items(x).sort((left,right)=>(right.favouriteCount ?? -1)-(left.favouriteCount ?? -1)); return envelope({query:clean(a.query),ranking:"favorite_count_within_sample",items:ranked}); }
    default: throw new Error("Onbekende tool.");
  }
}
export function createServer() {
  const server = new Server({name:"vinted-safe",version:"1.0.0"},{capabilities:{tools:{}}});
  server.setRequestHandler(ListToolsRequestSchema, async () => ({tools}));
  server.setRequestHandler(CallToolRequestSchema, async ({params}) => {
    try { if (!TOOLS.includes(params.name)) throw new Error("Onbekende tool."); const value = await call(params.name, (params.arguments ?? {}) as Record<string,unknown>); return {content:[{type:"text",text:value}]}; }
    catch { return {isError:true,content:[{type:"text",text:"Ongeldige invoer of tijdelijke Vinted-fout."}]}; }
  });
  return server;
}
await createServer().connect(new StdioServerTransport());
