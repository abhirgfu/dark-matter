//! Runs the compiled contract through NEAR's own VM with the settings mainnet uses today.
//!
//! `intents.near` has no testnet, so the full call can only happen on mainnet. This is the next best
//! thing. It loads the real wasm, validates it the way a node does, and executes `new`, `weigh` and
//! the callback in Wasmtime, feeding the callback the answers `intents.near` gave for real treasury
//! balances and keys. Storage persists between calls, as it does on chain.
//!
//!     cargo run --release -- <path to dark_matter.wasm> <path to fixture.json>

use near_parameters::RuntimeConfigStore;
use near_primitives_core::account::AccountContract;
use near_primitives_core::types::{Balance, Gas};
use near_vm_runner::internal::VMKindExt;
use near_vm_runner::logic::mocks::mock_external::{MockAction, MockedExternal};
use near_vm_runner::logic::types::{PromiseResult, ReturnData};
use near_vm_runner::logic::VMContext;
use near_vm_runner::ContractCode;
use serde_json::{json, Value};
use std::sync::Arc;

const MAINNET_PROTOCOL: u32 = 88;
const CONTRACT: &str = "darkmatter.near";
const T0_NS: u64 = 1_794_000_000_000_000_000;
const DAY_NS: u64 = 86_400_000_000_000;

struct Chain {
    ext: MockedExternal,
    config: Arc<near_parameters::vm::Config>,
    fees: Arc<near_parameters::RuntimeFeesConfig>,
    storage_usage: u64,
}

struct Call<'a> {
    method: &'a str,
    input: Value,
    caller: &'a str,
    time_ns: u64,
    promise_results: Vec<PromiseResult>,
    gas_tgas: u64,
    view: bool,
}

impl Chain {
    fn run(&mut self, call: Call) -> near_vm_runner::logic::VMOutcome {
        let context = VMContext {
            current_account_id: CONTRACT.parse().unwrap(),
            signer_account_id: call.caller.parse().unwrap(),
            signer_account_pk: vec![0; 33],
            predecessor_account_id: call.caller.parse().unwrap(),
            refund_to_account_id: call.caller.parse().unwrap(),
            input: std::rc::Rc::from(serde_json::to_vec(&call.input).unwrap()),
            promise_results: call.promise_results.into(),
            block_height: 223_000_000 + (call.time_ns - T0_NS) / 600_000_000,
            block_timestamp: call.time_ns,
            epoch_height: 1,
            account_balance: Balance::from_near(20),
            account_locked_balance: Balance::ZERO,
            storage_usage: self.storage_usage,
            account_contract: AccountContract::None,
            attached_deposit: Balance::ZERO,
            prepaid_gas: Gas::from_teragas(call.gas_tgas),
            random_seed: vec![1; 32],
            view_config: call.view.then_some(near_primitives_core::config::ViewConfig {
                max_gas_burnt: Gas::from_teragas(300),
            }),
            output_data_receivers: vec![],
        };
        let runtime = self.config.vm_kind.runtime(self.config.clone()).expect("runtime compiled in");
        let gas = context.make_gas_counter(&self.config);
        let outcome = runtime
            .prepare(&self.ext, None, gas, call.method)
            .run(&mut self.ext, &context, self.fees.clone())
            .expect("the VM itself failed");
        self.storage_usage = outcome.storage_usage;
        outcome
    }
}

fn returned(outcome: &near_vm_runner::logic::VMOutcome) -> Value {
    match &outcome.return_data {
        ReturnData::Value(bytes) => serde_json::from_slice(bytes).unwrap_or(Value::Null),
        _ => Value::Null,
    }
}

fn ok_or_die(name: &str, outcome: &near_vm_runner::logic::VMOutcome) {
    if let Some(err) = &outcome.aborted {
        panic!("{name} aborted: {err:?}");
    }
    println!(
        "PASS  {name}: {:.2} Tgas burnt, {} logs",
        outcome.burnt_gas.as_gas() as f64 / 1e12,
        outcome.logs.len()
    );
}

fn answer(value: &Value) -> PromiseResult {
    PromiseResult::Successful(std::rc::Rc::from(serde_json::to_vec(value).unwrap()))
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let wasm = std::fs::read(&args[1]).expect("wasm file");
    let fixture: Value = serde_json::from_slice(&std::fs::read(&args[2]).expect("fixture")).unwrap();

    let store = RuntimeConfigStore::new(None);
    let runtime_config = store.get_config(MAINNET_PROTOCOL);
    let config = runtime_config.wasm_config.clone();
    println!(
        "NEAR protocol {MAINNET_PROTOCOL}, VM {:?}, bulk memory {}",
        config.vm_kind, config.reftypes_bulk_memory
    );

    let prepared = near_vm_runner::prepare::prepare_contract(&wasm, &config, config.vm_kind);
    assert!(prepared.is_ok(), "validation failed: {:?}", prepared.err());
    println!("PASS  a node would accept this wasm: {} bytes", wasm.len());

    let code = ContractCode::new(wasm, None);
    let mut chain = Chain {
        ext: MockedExternal::with_code(code),
        config,
        fees: Arc::new(runtime_config.fees.as_ref().clone()),
        storage_usage: 300_000,
    };
    let tokens = fixture["tokens"].as_array().unwrap().clone();
    let balances = fixture["balances"].clone();
    let keys = fixture["keys"].clone();
    let start = chain.storage_usage;

    let out = chain.run(Call {
        method: "new",
        input: json!({
            "owner": "owner.near", "verifier": "intents.near", "treasury": fixture["treasury"],
            "tokens": tokens, "min_interval_ms": 86_400_000u64, "alert_bps": 2000,
        }),
        caller: CONTRACT,
        time_ns: T0_NS,
        promise_results: vec![],
        gas_tgas: 100,
        view: false,
    });
    ok_or_die("new", &out);
    println!("      storage after new: {} bytes", out.storage_usage - start);

    chain.ext.action_log.clear();
    let out = chain.run(Call {
        method: "weigh",
        input: json!({}),
        caller: "anyone.near",
        time_ns: T0_NS + 1_000_000_000,
        promise_results: vec![],
        gas_tgas: 100,
        view: false,
    });
    ok_or_die("weigh", &out);
    let mut calls = vec![];
    for action in &chain.ext.action_log {
        if let MockAction::FunctionCallWeight { method_name, prepaid_gas, .. } = action {
            calls.push((String::from_utf8_lossy(method_name).to_string(), prepaid_gas.as_gas() / 1_000_000_000_000));
        }
    }
    println!("      receipts: {calls:?}");
    let names: Vec<&str> = calls.iter().map(|c| c.0.as_str()).collect();
    assert_eq!(names, ["mt_batch_balance_of", "public_keys_of", "on_weigh"]);

    let out = chain.run(Call {
        method: "on_weigh",
        input: json!({"weighed_by": "anyone.near"}),
        caller: CONTRACT,
        time_ns: T0_NS + 3_000_000_000,
        promise_results: vec![answer(&balances), answer(&keys)],
        gas_tgas: 30,
        view: false,
    });
    ok_or_die("on_weigh with real balances", &out);
    assert_eq!(returned(&out), json!(true));
    let first_reading_bytes = out.storage_usage;

    let out = chain.run(Call {
        method: "get_latest",
        input: json!({}),
        caller: "anyone.near",
        time_ns: T0_NS + 4_000_000_000,
        promise_results: vec![],
        gas_tgas: 300,
        view: true,
    });
    ok_or_die("get_latest", &out);
    let latest = returned(&out);
    assert_eq!(latest["balances"], balances, "the stored reading differs from the answer");
    println!("PASS  the reading matches intents.near's answer for {} tokens", tokens.len());

    let first_token = tokens[0].clone();
    let out = chain.run(Call {
        method: "get_balance",
        input: json!({"token": first_token}),
        caller: "another-contract.near",
        time_ns: T0_NS + 4_000_000_000,
        promise_results: vec![],
        gas_tgas: 300,
        view: true,
    });
    ok_or_die("get_balance", &out);
    assert_eq!(returned(&out), balances[0]);

    // A stranger cannot write a reading.
    let out = chain.run(Call {
        method: "on_weigh",
        input: json!({"weighed_by": "attacker.near"}),
        caller: "attacker.near",
        time_ns: T0_NS + DAY_NS * 2,
        promise_results: vec![answer(&balances), answer(&keys)],
        gas_tgas: 30,
        view: false,
    });
    assert!(out.aborted.is_some(), "a stranger wrote a reading");
    println!("PASS  a stranger's on_weigh is refused");

    // Second day: half of one token leaves and a key is added.
    let mut less = balances.clone();
    let halved = less[0].as_str().unwrap().parse::<u128>().unwrap() / 2;
    less[0] = json!(halved.to_string());
    let mut more_keys = keys.clone();
    more_keys.as_array_mut().unwrap().push(json!("ed25519:NewKeyAddedToTheTreasury11111111111111111"));
    let out = chain.run(Call {
        method: "on_weigh",
        input: json!({"weighed_by": "anyone.near"}),
        caller: CONTRACT,
        time_ns: T0_NS + DAY_NS + 10_000_000_000,
        promise_results: vec![answer(&less), answer(&more_keys)],
        gas_tgas: 30,
        view: false,
    });
    ok_or_die("on_weigh on the second day", &out);
    let logs = out.logs.join("\n");
    assert!(logs.contains("outflow_alert"), "no outflow alert in: {logs}");
    assert!(logs.contains("treasury_keys_changed"), "no key alert in: {logs}");
    println!("PASS  a 50% fall and a new key each raise an on-chain event");

    let per_reading = out.storage_usage - first_reading_bytes;
    println!("      one reading stores {per_reading} bytes");
    println!("      a year of daily readings needs about {:.2} NEAR of storage", per_reading as f64 * 365.0 / 1e5);
    println!("\nALL VM CHECKS PASS");
}
