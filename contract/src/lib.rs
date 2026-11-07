//! Dark Matter: a public weigh station for NEAR Confidential Intents.
//!
//! Shielded balances live on a private chain that has no public RPC or explorer. Their backing
//! does not: every shielded token is held by one treasury account on `intents.near`, on the public
//! chain. So the private economy can be weighed from outside.
//!
//! Anyone may call `weigh()`. The contract asks `intents.near` for the treasury's balances and its
//! signing keys in a cross-contract call, and stores the answer. There is no oracle, no enclave and
//! no trusted reporter: the numbers come straight from the contract that holds the money, and any
//! other NEAR contract can read them.
//!
//! Two public warnings come out of it, as NEP-297 events anyone can subscribe to:
//! - `treasury_keys_changed` if the set of keys that can move the treasury changes;
//! - `outflow_alert` if a tracked token falls by more than `alert_bps` between two readings.
//!
//! The owner can only append: new tokens to track and hashes of published data. It cannot edit a
//! reading, and `renounce_ownership` removes even that.

use near_sdk::borsh::BorshSerialize;
use near_sdk::json_types::U128;
use near_sdk::store::Vector;
use near_sdk::{
    env, ext_contract, near, require, AccountId, BorshStorageKey, Gas, PanicOnDefault, Promise,
    PromiseError,
};

/// Gas for each read of `intents.near`.
const GAS_READ: Gas = Gas::from_tgas(12);
/// Gas for the callback that stores the reading.
const GAS_CALLBACK: Gas = Gas::from_tgas(30);
/// `weigh` needs the two reads, the callback, and a little for itself.
const GAS_WEIGH_MIN: Gas = Gas::from_tgas(60);

/// One token id is about 60 bytes and every reading stores one balance per token. This bound keeps
/// the state read by every call, and the gas of a read, small.
const MAX_TOKENS: usize = 64;
/// Never weigh more often than this, whatever `new` was given, so that storage stays bounded.
const MIN_INTERVAL_FLOOR_MS: u64 = 60 * 60 * 1000;
const MAX_PAGE: u64 = 100;
const BPS: u128 = 10_000;

#[derive(BorshSerialize, BorshStorageKey)]
#[borsh(crate = "near_sdk::borsh")]
enum StorageKey {
    Readings,
    KeyChanges,
    Anchors,
}

/// One weighing of the treasury. `balances[i]` is the balance of the i-th tracked token, in the
/// token's own smallest unit. Tokens are append-only, so old readings are simply shorter.
#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Reading {
    pub index: u64,
    pub block_height: u64,
    pub timestamp_ms: u64,
    pub balances: Vec<U128>,
    pub weighed_by: AccountId,
}

/// The set of keys registered for the treasury on `intents.near` changed.
#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct KeyChange {
    pub block_height: u64,
    pub timestamp_ms: u64,
    pub before: Vec<String>,
    pub after: Vec<String>,
}

/// The hash of something published elsewhere: a data manifest or a list of pre-registered tests.
#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Anchor {
    pub kind: String,
    pub sha256: String,
    pub note: String,
    pub block_height: u64,
    pub timestamp_ms: u64,
}

#[near(serializers = [json])]
pub struct Config {
    pub owner: Option<AccountId>,
    pub verifier: AccountId,
    pub treasury: AccountId,
    pub min_interval_ms: u64,
    pub alert_bps: u32,
    pub token_count: u64,
    pub reading_count: u64,
    pub next_weigh_at_ms: u64,
}

#[near(event_json(standard = "darkmatter"))]
pub enum Event {
    #[event_version("1.0.0")]
    Weighed {
        index: u64,
        block_height: u64,
        weighed_by: AccountId,
    },
    #[event_version("1.0.0")]
    WeighFailed { reason: String },
    #[event_version("1.0.0")]
    TreasuryKeysChanged {
        before: Vec<String>,
        after: Vec<String>,
    },
    #[event_version("1.0.0")]
    OutflowAlert {
        token: String,
        before: U128,
        after: U128,
        drop_bps: u32,
    },
    #[event_version("1.0.0")]
    Anchored { kind: String, sha256: String },
}

/// The two public view methods of `intents.near` that we read.
#[ext_contract(ext_verifier)]
#[allow(dead_code)]
trait Verifier {
    fn mt_batch_balance_of(&self, account_id: AccountId, token_ids: Vec<String>) -> Vec<U128>;
    fn public_keys_of(&self, account_id: AccountId) -> Vec<String>;
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct DarkMatter {
    owner: Option<AccountId>,
    verifier: AccountId,
    treasury: AccountId,
    min_interval_ms: u64,
    alert_bps: u32,
    tokens: Vec<String>,
    keys: Vec<String>,
    readings: Vector<Reading>,
    key_changes: Vector<KeyChange>,
    anchors: Vector<Anchor>,
}

#[near]
impl DarkMatter {
    #[init]
    pub fn new(
        owner: AccountId,
        verifier: AccountId,
        treasury: AccountId,
        tokens: Vec<String>,
        min_interval_ms: u64,
        alert_bps: u32,
    ) -> Self {
        require!(!tokens.is_empty(), "track at least one token");
        require!(tokens.len() <= MAX_TOKENS, "too many tokens");
        require!(
            min_interval_ms >= MIN_INTERVAL_FLOOR_MS,
            "minimum interval is one hour"
        );
        require!(
            alert_bps > 0 && u128::from(alert_bps) <= BPS,
            "alert_bps must be 1 to 10000"
        );
        Self::assert_unique(&tokens);
        Self {
            owner: Some(owner),
            verifier,
            treasury,
            min_interval_ms,
            alert_bps,
            tokens,
            keys: Vec::new(),
            readings: Vector::new(StorageKey::Readings),
            key_changes: Vector::new(StorageKey::KeyChanges),
            anchors: Vector::new(StorageKey::Anchors),
        }
    }

    /// Weigh the treasury. Anyone may call this; it takes no deposit and pays no reward.
    pub fn weigh(&mut self) -> Promise {
        require!(
            env::block_timestamp_ms() >= self.next_weigh_at_ms(),
            "too soon: see next_weigh_at_ms in get_config"
        );
        require!(
            env::prepaid_gas() >= GAS_WEIGH_MIN,
            "attach at least 60 Tgas"
        );
        let balances = ext_verifier::ext(self.verifier.clone())
            .with_static_gas(GAS_READ)
            .mt_batch_balance_of(self.treasury.clone(), self.tokens.clone());
        let keys = ext_verifier::ext(self.verifier.clone())
            .with_static_gas(GAS_READ)
            .public_keys_of(self.treasury.clone());
        balances.and(keys).then(
            Self::ext(env::current_account_id())
                .with_static_gas(GAS_CALLBACK)
                .on_weigh(env::predecessor_account_id()),
        )
    }

    /// Stores what `intents.near` answered. Returns whether a reading was stored.
    pub fn on_weigh(
        &mut self,
        #[callback_result] balances: Result<Vec<U128>, PromiseError>,
        #[callback_result] keys: Result<Vec<String>, PromiseError>,
        weighed_by: AccountId,
    ) -> bool {
        // Spelled out rather than `#[private]`, because that attribute only acts in the wasm
        // wrapper, and this is the one check that must be covered by a unit test: if a stranger
        // could call this, they could write any balances they liked.
        require!(
            env::predecessor_account_id() == env::current_account_id(),
            "only this contract can store a reading"
        );
        // Two calls can pass the check in `weigh` before either callback runs.
        if env::block_timestamp_ms() < self.next_weigh_at_ms() {
            Self::fail("a reading landed first");
            return false;
        }
        let (balances, keys) = match (balances, keys) {
            (Ok(balances), Ok(keys)) => (balances, keys),
            _ => {
                Self::fail("intents.near did not answer");
                return false;
            }
        };
        if balances.len() != self.tokens.len() {
            Self::fail("token list changed during the read");
            return false;
        }

        self.check_outflows(&balances);
        self.check_keys(keys);

        let reading = Reading {
            index: u64::from(self.readings.len()),
            block_height: env::block_height(),
            timestamp_ms: env::block_timestamp_ms(),
            balances,
            weighed_by: weighed_by.clone(),
        };
        Event::Weighed {
            index: reading.index,
            block_height: reading.block_height,
            weighed_by,
        }
        .emit();
        self.readings.push(reading);
        true
    }

    /// Track one more token. Tokens are only ever appended, so old readings keep their meaning.
    pub fn add_token(&mut self, token: String) {
        self.assert_owner();
        require!(self.tokens.len() < MAX_TOKENS, "too many tokens");
        require!(!self.tokens.contains(&token), "already tracked");
        self.tokens.push(token);
    }

    /// Record the hash of something published elsewhere, such as a data manifest.
    pub fn anchor(&mut self, kind: String, sha256: String, note: String) {
        self.assert_owner();
        require!(!kind.is_empty() && kind.len() <= 32, "kind: 1 to 32 bytes");
        require!(note.len() <= 200, "note: at most 200 bytes");
        require!(
            sha256.len() == 64 && sha256.chars().all(|c| matches!(c, '0'..='9' | 'a'..='f')),
            "sha256: 64 lowercase hex characters"
        );
        Event::Anchored {
            kind: kind.clone(),
            sha256: sha256.clone(),
        }
        .emit();
        self.anchors.push(Anchor {
            kind,
            sha256,
            note,
            block_height: env::block_height(),
            timestamp_ms: env::block_timestamp_ms(),
        });
    }

    /// Give up the owner role for good. After this nobody can add tokens or anchors.
    pub fn renounce_ownership(&mut self) {
        self.assert_owner();
        self.owner = None;
    }

    // ---- views ----

    pub fn get_config(&self) -> Config {
        Config {
            owner: self.owner.clone(),
            verifier: self.verifier.clone(),
            treasury: self.treasury.clone(),
            min_interval_ms: self.min_interval_ms,
            alert_bps: self.alert_bps,
            token_count: self.tokens.len() as u64,
            reading_count: u64::from(self.readings.len()),
            next_weigh_at_ms: self.next_weigh_at_ms(),
        }
    }

    pub fn get_tokens(&self) -> Vec<String> {
        self.tokens.clone()
    }

    /// The keys registered for the treasury at the latest reading.
    pub fn get_keys(&self) -> Vec<String> {
        self.keys.clone()
    }

    pub fn get_latest(&self) -> Option<Reading> {
        self.last_reading().cloned()
    }

    pub fn get_reading(&self, index: u64) -> Option<Reading> {
        u32::try_from(index)
            .ok()
            .and_then(|i| self.readings.get(i).cloned())
    }

    /// The latest balance of one token, for other contracts that only want one number.
    pub fn get_balance(&self, token: String) -> Option<U128> {
        let at = self.tokens.iter().position(|t| *t == token)?;
        self.last_reading()
            .and_then(|r| r.balances.get(at).copied())
    }

    pub fn get_readings(&self, from: u64, limit: u64) -> Vec<Reading> {
        Self::page(&self.readings, from, limit)
    }

    pub fn get_key_changes(&self, from: u64, limit: u64) -> Vec<KeyChange> {
        Self::page(&self.key_changes, from, limit)
    }

    pub fn get_anchors(&self, from: u64, limit: u64) -> Vec<Anchor> {
        Self::page(&self.anchors, from, limit)
    }
}

impl DarkMatter {
    fn page<T>(items: &Vector<T>, from: u64, limit: u64) -> Vec<T>
    where
        T: Clone + BorshSerialize + near_sdk::borsh::BorshDeserialize,
    {
        items
            .iter()
            .skip(from as usize)
            .take(limit.min(MAX_PAGE) as usize)
            .cloned()
            .collect()
    }

    /// By index, not by iterating: the list grows every day and this runs on every call.
    fn last_reading(&self) -> Option<&Reading> {
        self.readings
            .len()
            .checked_sub(1)
            .and_then(|i| self.readings.get(i))
    }

    fn next_weigh_at_ms(&self) -> u64 {
        self.last_reading()
            .map_or(0, |r| r.timestamp_ms.saturating_add(self.min_interval_ms))
    }

    fn assert_owner(&self) {
        require!(
            self.owner.as_ref() == Some(&env::predecessor_account_id()),
            "only the owner can do this"
        );
    }

    fn assert_unique(tokens: &[String]) {
        for (i, token) in tokens.iter().enumerate() {
            require!(!tokens[..i].contains(token), "duplicate token");
        }
    }

    fn fail(reason: &str) {
        Event::WeighFailed {
            reason: reason.to_string(),
        }
        .emit();
    }

    /// Warn when a token's balance falls by `alert_bps` or more since the last reading.
    fn check_outflows(&self, balances: &[U128]) {
        let Some(last) = self.last_reading() else {
            return;
        };
        for (i, before) in last.balances.iter().enumerate() {
            let drop_bps = drop_bps(before.0, balances[i].0);
            if drop_bps >= u128::from(self.alert_bps) {
                Event::OutflowAlert {
                    token: self.tokens[i].clone(),
                    before: *before,
                    after: balances[i],
                    drop_bps: drop_bps as u32,
                }
                .emit();
            }
        }
    }

    /// Remember the key set, and warn if it moved. The first reading only sets the baseline.
    fn check_keys(&mut self, mut keys: Vec<String>) {
        keys.sort();
        if self.readings.is_empty() {
            self.keys = keys;
            return;
        }
        if keys != self.keys {
            let before = std::mem::replace(&mut self.keys, keys);
            let after = self.keys.clone();
            Event::TreasuryKeysChanged {
                before: before.clone(),
                after: after.clone(),
            }
            .emit();
            self.key_changes.push(KeyChange {
                block_height: env::block_height(),
                timestamp_ms: env::block_timestamp_ms(),
                before,
                after,
            });
        }
    }
}

/// How far `after` fell below `before`, in basis points. Multiplying first could overflow u128 for
/// a token with 24 decimals and a very large supply, so large balances divide first.
fn drop_bps(before: u128, after: u128) -> u128 {
    if before == 0 || after >= before {
        return 0;
    }
    let fall = before - after;
    match fall.checked_mul(BPS) {
        Some(scaled) => scaled / before,
        None => fall / (before / BPS),
    }
}

#[cfg(test)]
mod tests;
