// Weigh the treasury from this browser, with nothing in between: one call to a public NEAR node for
// the balances, and one public token list for prices. Nothing here is fetched from our own servers,
// because there are none.
"use strict";

const RPCS = ["https://free.rpc.fastnear.com", "https://rpc.mainnet.fastnear.com", "https://rpc.mainnet.near.org"];
const VERIFIER = "intents.near";

function b64(text) { return btoa(text); }

function fromBytes(bytes) { return JSON.parse(new TextDecoder().decode(new Uint8Array(bytes))); }

async function rpcCall(method, params) {
  let last;
  for (const url of RPCS) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: "dm", method, params }),
      });
      const json = await res.json();
      if (json.result) return { result: json.result, url };
      last = new Error(JSON.stringify(json.error || json).slice(0, 160));
    } catch (err) {
      last = err;
    }
  }
  throw last;
}

async function viewCall(account, method, args, block) {
  const params = {
    request_type: "call_function",
    account_id: account,
    method_name: method,
    args_base64: b64(JSON.stringify(args)),
  };
  if (block) params.block_id = block;
  else params.finality = "final";
  const { result, url } = await rpcCall("query", params);
  return { value: fromBytes(result.result), height: result.block_height, url };
}

async function weighNow(treasury, log) {
  const tokens = await viewCall(VERIFIER, "mt_tokens_for_owner", { account_id: treasury, limit: 500 });
  const ids = tokens.value.map((t) => t.token_id);
  log(`${tokens.url}\nintents.near mt_tokens_for_owner -> ${ids.length} tokens at block ${tokens.height}`);
  const balances = await viewCall(VERIFIER, "mt_batch_balance_of", { account_id: treasury, token_ids: ids }, tokens.height);
  log(`intents.near mt_batch_balance_of at block ${tokens.height} -> ${balances.value.length} balances`);
  const list = await (await fetch("https://1click.chaindefuser.com/v0/tokens")).json();
  const info = new Map(list.map((t) => [t.assetId, t]));
  log(`1click.chaindefuser.com/v0/tokens -> ${list.length} token prices (used here, kept nowhere)`);
  let usd = 0;
  let priced = 0;
  const top = [];
  ids.forEach((id, i) => {
    const t = info.get(id);
    if (!t || t.price == null) return;
    const value = (Number(BigInt(balances.value[i]) / 10n ** BigInt(Math.max(0, t.decimals - 6))) / 1e6) * t.price;
    usd += value;
    priced += 1;
    top.push([t.symbol, value]);
  });
  top.sort((a, b) => b[1] - a[1]);
  return { usd, priced, tokens: ids.length, height: tokens.height, top: top.slice(0, 5) };
}

window.DMWeigh = { weighNow, viewCall };
