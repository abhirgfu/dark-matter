# The weigh station

A NEAR contract that anyone can call to record how much money sits behind NEAR Confidential Intents,
and who can move it.

Shielded balances live on a private chain. Their backing lives on `intents.near`, on the public chain,
under one treasury account. `weigh()` reads that account's balances and keys in a cross-contract call
and stores the answer. No oracle, enclave or reporter stands between the money and the reading, and
any other NEAR contract can use the result.

## What it does

| Call | Who | What |
|---|---|---|
| `weigh()` | Anyone, once per interval | Reads `mt_batch_balance_of` and `public_keys_of` from `intents.near`, stores a reading |
| `get_latest()`, `get_reading(index)`, `get_readings(from, limit)` | Anyone | Stored readings |
| `get_balance(token)` | Anyone | One token's latest balance, for other contracts |
| `get_keys()`, `get_key_changes(from, limit)` | Anyone | The treasury's keys, and every change to them |
| `get_config()`, `get_tokens()`, `get_anchors(from, limit)` | Anyone | Settings and published hashes |
| `add_token(token)`, `anchor(kind, sha256, note)` | Owner | Append only. Neither can change a reading |
| `renounce_ownership()` | Owner | Gives up the role for good |

Two NEP-297 events give the ecosystem a free warning system:

- `treasury_keys_changed` when the keys that can move the treasury change
- `outflow_alert` when a tracked token falls by `alert_bps` or more between readings

## Build and test

Rust 1.96 is pinned in `rust-toolchain.toml`. The unit tests need no network.

```bash
cd contract
cargo test
cargo build --target wasm32-unknown-unknown --release
```

On Windows, use the MSVC toolchain and set `AWS_LC_SYS_PREBUILT_NASM=1` before `cargo test`.

The 36 unit tests cover the read path, every refusal, the alert and key logic, ownership and paging.

`weigh()` calls `intents.near`, which exists only on mainnet (Q-007), so the full call can only happen
there. `vm-test/` is the next best thing. It loads the compiled wasm, validates it as a node does, and runs
`new`, `weigh` and the callback in NEAR's own VM with the settings of mainnet protocol 88, feeding the
callback real treasury balances:

```bash
cd contract/vm-test
cargo run --release -- ../target/wasm32-unknown-unknown/release/dark_matter.wasm fixture.json
```

It ends with `ALL VM CHECKS PASS`. The latest run: `weigh` burns 1.9 Tgas, a callback storing 32 balances
burns 0.9 Tgas, and a stranger's call to `on_weigh` is refused. On Windows, Wasmtime needs
`native_unwind_info(true)` in a local copy of `near-vm-runner`. Linux and macOS need no change.

## Deploy

Deploying spends mainnet NEAR and needs your account, so it is yours to run. Storage costs about 2 NEAR
for the code and 3.2 NEAR for each year of daily readings. Install
[near-cli-rs](https://github.com/near/near-cli-rs) and sign in with your own wallet, then run:

```bash
python pipeline/contract_args.py YOUR-ACCOUNT.near
```

```bash
near account create-account fund-myself darkmatter.YOUR-ACCOUNT.near '6 NEAR' autogenerate-new-keypair save-to-keychain sign-as YOUR-ACCOUNT.near network-config mainnet sign-with-keychain send
```

```bash
near contract deploy darkmatter.YOUR-ACCOUNT.near use-file contract/target/wasm32-unknown-unknown/release/dark_matter.wasm with-init-call new file-args contract/init_args.json prepaid-gas '100 Tgas' attached-deposit '0 NEAR' network-config mainnet sign-with-keychain send
```

Then weigh once:

```bash
near contract call-function as-transaction darkmatter.YOUR-ACCOUNT.near weigh json-args '{}' prepaid-gas '100 Tgas' attached-deposit '0 NEAR' sign-as YOUR-ACCOUNT.near network-config mainnet sign-with-keychain send
```

Read it back, with no account:

```bash
near contract call-function as-read-only darkmatter.YOUR-ACCOUNT.near get_latest json-args '{}' network-config mainnet now
```

Put the account in `data/static/deployment.json` and run `python rebuild.py`. The site then shows it.

To make the contract immutable, delete its full-access key after deploying. There is no upgrade
method in the code.
