use super::*;
use near_sdk::test_utils::{get_logs, VMContextBuilder};
use near_sdk::testing_env;

const HOUR_MS: u64 = 3_600_000;
const DAY_MS: u64 = 24 * HOUR_MS;
const T0_MS: u64 = 1_794_000_000_000;

fn acct(name: &str) -> AccountId {
    name.parse().unwrap()
}

fn context(at_ms: u64, caller: &str) -> VMContextBuilder {
    let mut b = VMContextBuilder::new();
    b.current_account_id(acct("darkmatter.near"))
        .predecessor_account_id(acct(caller))
        .block_timestamp(at_ms * 1_000_000)
        .block_height(1000 + (at_ms - T0_MS) / 1000)
        .prepaid_gas(Gas::from_tgas(100));
    b
}

fn at(at_ms: u64, caller: &str) {
    testing_env!(context(at_ms, caller).build());
}

fn fresh(tokens: &[&str]) -> DarkMatter {
    at(T0_MS, "owner.near");
    DarkMatter::new(
        acct("owner.near"),
        acct("intents.near"),
        acct("treasury.near"),
        tokens.iter().map(|t| t.to_string()).collect(),
        DAY_MS,
        2000,
    )
}

fn ok_bal(values: &[u128]) -> Result<Vec<U128>, PromiseError> {
    Ok(values.iter().copied().map(U128).collect())
}

fn ok_keys(keys: &[&str]) -> Result<Vec<String>, PromiseError> {
    Ok(keys.iter().map(|k| k.to_string()).collect())
}

/// What the runtime does after the reads: calls the callback as the contract itself.
fn land(c: &mut DarkMatter, at_ms: u64, bal: &[u128], keys: &[&str]) -> bool {
    at(at_ms, "darkmatter.near");
    c.on_weigh(ok_bal(bal), ok_keys(keys), acct("anyone.near"))
}

fn logged(fragment: &str) -> bool {
    get_logs().iter().any(|l| l.contains(fragment))
}

// ---- construction ----

#[test]
fn new_stores_config() {
    let c = fresh(&["a", "b"]);
    let cfg = c.get_config();
    assert_eq!(cfg.owner, Some(acct("owner.near")));
    assert_eq!(cfg.verifier, acct("intents.near"));
    assert_eq!(cfg.treasury, acct("treasury.near"));
    assert_eq!(cfg.token_count, 2);
    assert_eq!(cfg.reading_count, 0);
    assert_eq!(cfg.next_weigh_at_ms, 0);
    assert_eq!(c.get_tokens(), vec!["a", "b"]);
    assert!(c.get_latest().is_none());
}

#[test]
#[should_panic(expected = "track at least one token")]
fn new_needs_a_token() {
    fresh(&[]);
}

#[test]
#[should_panic(expected = "duplicate token")]
fn new_refuses_duplicates() {
    fresh(&["a", "a"]);
}

#[test]
#[should_panic(expected = "too many tokens")]
fn new_refuses_too_many_tokens() {
    let names: Vec<String> = (0..=MAX_TOKENS).map(|i| format!("t{i}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    fresh(&refs);
}

#[test]
#[should_panic(expected = "minimum interval is one hour")]
fn new_refuses_a_short_interval() {
    at(T0_MS, "owner.near");
    DarkMatter::new(
        acct("o.near"),
        acct("i.near"),
        acct("t.near"),
        vec!["a".into()],
        HOUR_MS - 1,
        2000,
    );
}

#[test]
#[should_panic(expected = "alert_bps must be 1 to 10000")]
fn new_refuses_a_zero_alert() {
    at(T0_MS, "owner.near");
    DarkMatter::new(
        acct("o.near"),
        acct("i.near"),
        acct("t.near"),
        vec!["a".into()],
        DAY_MS,
        0,
    );
}

// ---- weigh ----

#[test]
fn anyone_can_weigh_with_no_deposit() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "stranger.near");
    let _ = c.weigh();
}

#[test]
#[should_panic(expected = "attach at least 60 Tgas")]
fn weigh_needs_gas() {
    let mut c = fresh(&["a"]);
    testing_env!(context(T0_MS, "x.near")
        .prepaid_gas(Gas::from_tgas(59))
        .build());
    let _ = c.weigh();
}

#[test]
#[should_panic(expected = "too soon")]
fn weigh_respects_the_interval() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[5], &["k"]);
    at(T0_MS + DAY_MS - 1, "x.near");
    let _ = c.weigh();
}

#[test]
fn weigh_opens_again_after_the_interval() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[5], &["k"]);
    assert_eq!(c.get_config().next_weigh_at_ms, T0_MS + DAY_MS);
    at(T0_MS + DAY_MS, "x.near");
    let _ = c.weigh();
}

// ---- callback ----

#[test]
#[should_panic(expected = "only this contract can store a reading")]
fn strangers_cannot_write_a_reading() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "attacker.near");
    c.on_weigh(ok_bal(&[1]), ok_keys(&["k"]), acct("attacker.near"));
}

#[test]
fn a_reading_stores_what_intents_answered() {
    let mut c = fresh(&["a", "b"]);
    assert!(land(&mut c, T0_MS + 5000, &[7, 9], &["k"]));
    let r = c.get_latest().unwrap();
    assert_eq!(r.index, 0);
    assert_eq!(r.balances, vec![U128(7), U128(9)]);
    assert_eq!(r.timestamp_ms, T0_MS + 5000);
    assert_eq!(r.block_height, 1005);
    assert_eq!(r.weighed_by, acct("anyone.near"));
    assert_eq!(c.get_reading(0), Some(r));
    assert!(logged("\"event\":\"weighed\""));
}

#[test]
fn a_failed_balance_read_stores_nothing() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "darkmatter.near");
    assert!(!c.on_weigh(Err(PromiseError::Failed), ok_keys(&["k"]), acct("x.near")));
    assert_eq!(c.get_config().reading_count, 0);
    assert!(logged("weigh_failed"));
}

#[test]
fn a_failed_key_read_stores_nothing() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "darkmatter.near");
    assert!(!c.on_weigh(ok_bal(&[1]), Err(PromiseError::Failed), acct("x.near")));
    assert_eq!(c.get_config().reading_count, 0);
}

#[test]
fn a_short_answer_stores_nothing() {
    let mut c = fresh(&["a", "b"]);
    assert!(!land(&mut c, T0_MS, &[1], &["k"]));
    assert_eq!(c.get_config().reading_count, 0);
}

#[test]
fn a_second_callback_in_the_same_interval_is_dropped() {
    let mut c = fresh(&["a"]);
    assert!(land(&mut c, T0_MS, &[1], &["k"]));
    assert!(!land(&mut c, T0_MS + 1, &[2], &["k"]));
    assert_eq!(c.get_config().reading_count, 1);
    assert_eq!(c.get_latest().unwrap().balances, vec![U128(1)]);
}

// ---- warnings ----

#[test]
fn a_fall_at_the_threshold_raises_an_alert() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1000], &["k"]);
    land(&mut c, T0_MS + DAY_MS, &[800], &["k"]);
    assert!(logged("outflow_alert"));
    assert!(logged("\"drop_bps\":2000"));
}

#[test]
fn a_fall_below_the_threshold_is_quiet() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1000], &["k"]);
    land(&mut c, T0_MS + DAY_MS, &[801], &["k"]);
    assert!(!logged("outflow_alert"));
}

#[test]
fn a_rise_is_quiet() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1000], &["k"]);
    land(&mut c, T0_MS + DAY_MS, &[5000], &["k"]);
    assert!(!logged("outflow_alert"));
}

#[test]
fn alerts_name_only_the_token_that_fell() {
    let mut c = fresh(&["steady", "falling"]);
    land(&mut c, T0_MS, &[100, 100], &["k"]);
    land(&mut c, T0_MS + DAY_MS, &[100, 10], &["k"]);
    assert!(logged("\"token\":\"falling\""));
    assert!(!logged("\"token\":\"steady\""));
}

#[test]
fn the_first_reading_sets_the_key_baseline_quietly() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1], &["k2", "k1"]);
    assert_eq!(c.get_keys(), vec!["k1", "k2"]);
    assert!(!logged("treasury_keys_changed"));
    assert!(c.get_key_changes(0, 10).is_empty());
}

#[test]
fn the_same_keys_in_another_order_are_not_a_change() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1], &["k1", "k2"]);
    land(&mut c, T0_MS + DAY_MS, &[1], &["k2", "k1"]);
    assert!(!logged("treasury_keys_changed"));
}

#[test]
fn a_new_key_is_recorded_and_announced() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1], &["k1"]);
    land(&mut c, T0_MS + DAY_MS, &[1], &["k1", "k2"]);
    assert!(logged("treasury_keys_changed"));
    let changes = c.get_key_changes(0, 10);
    assert_eq!(changes.len(), 1);
    assert_eq!(changes[0].before, vec!["k1"]);
    assert_eq!(changes[0].after, vec!["k1", "k2"]);
    assert_eq!(changes[0].timestamp_ms, T0_MS + DAY_MS);
    assert_eq!(c.get_keys(), vec!["k1", "k2"]);
}

#[test]
fn drop_bps_handles_the_edges() {
    assert_eq!(drop_bps(0, 0), 0);
    assert_eq!(drop_bps(0, 5), 0);
    assert_eq!(drop_bps(5, 5), 0);
    assert_eq!(drop_bps(5, 9), 0);
    assert_eq!(drop_bps(5, 0), 10_000);
    assert_eq!(drop_bps(10_000, 9_999), 1);
}

#[test]
fn drop_bps_survives_balances_that_would_overflow() {
    let huge = u128::MAX / 2;
    assert_eq!(drop_bps(huge, 0), 10_000);
    let half = drop_bps(huge, huge / 2);
    assert!((4_999..=5_001).contains(&half));
}

// ---- owner ----

#[test]
fn the_owner_can_append_a_token_and_old_readings_stay_short() {
    let mut c = fresh(&["a"]);
    land(&mut c, T0_MS, &[1], &["k"]);
    at(T0_MS + 1, "owner.near");
    c.add_token("b".to_string());
    assert!(land(&mut c, T0_MS + DAY_MS, &[1, 2], &["k"]));
    assert_eq!(c.get_reading(0).unwrap().balances.len(), 1);
    assert_eq!(c.get_reading(1).unwrap().balances.len(), 2);
    assert_eq!(c.get_balance("b".to_string()), Some(U128(2)));
}

#[test]
fn a_token_added_between_read_and_callback_cannot_misalign_a_reading() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "owner.near");
    c.add_token("b".to_string());
    assert!(!land(&mut c, T0_MS, &[1], &["k"]));
    assert_eq!(c.get_config().reading_count, 0);
}

#[test]
#[should_panic(expected = "only the owner can do this")]
fn strangers_cannot_add_tokens() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "attacker.near");
    c.add_token("b".to_string());
}

#[test]
#[should_panic(expected = "already tracked")]
fn a_token_cannot_be_added_twice() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "owner.near");
    c.add_token("a".to_string());
}

#[test]
fn the_owner_can_anchor_a_hash() {
    let mut c = fresh(&["a"]);
    let hash = "ab".repeat(32);
    at(T0_MS, "owner.near");
    c.anchor("manifest".into(), hash.clone(), "first snapshot".into());
    let a = c.get_anchors(0, 10);
    assert_eq!(a.len(), 1);
    assert_eq!(a[0].sha256, hash);
    assert_eq!(a[0].note, "first snapshot");
    assert!(logged("anchored"));
}

#[test]
#[should_panic(expected = "sha256: 64 lowercase hex characters")]
fn a_bad_hash_is_refused() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "owner.near");
    c.anchor("manifest".into(), "AB".repeat(32), String::new());
}

#[test]
#[should_panic(expected = "only the owner can do this")]
fn strangers_cannot_anchor() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "attacker.near");
    c.anchor("manifest".into(), "ab".repeat(32), String::new());
}

#[test]
#[should_panic(expected = "only the owner can do this")]
fn renouncing_is_final() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "owner.near");
    c.renounce_ownership();
    assert_eq!(c.get_config().owner, None);
    c.add_token("b".to_string());
}

#[test]
fn weighing_still_works_after_renouncing() {
    let mut c = fresh(&["a"]);
    at(T0_MS, "owner.near");
    c.renounce_ownership();
    assert!(land(&mut c, T0_MS, &[1], &["k"]));
}

// ---- views ----

#[test]
fn readings_page_and_cap() {
    let mut c = fresh(&["a"]);
    for day in 0..120u64 {
        assert!(land(&mut c, T0_MS + day * DAY_MS, &[u128::from(day) + 1], &["k"]));
    }
    assert_eq!(c.get_readings(0, 10).len(), 10);
    assert_eq!(c.get_readings(0, 1000).len(), 100);
    assert_eq!(c.get_readings(115, 100).len(), 5);
    assert_eq!(c.get_readings(500, 10).len(), 0);
    assert_eq!(c.get_readings(3, 1)[0].index, 3);
    assert_eq!(c.get_latest().unwrap().index, 119);
}

#[test]
fn unknown_lookups_are_empty_not_errors() {
    let c = fresh(&["a"]);
    assert_eq!(c.get_reading(9), None);
    assert_eq!(c.get_reading(u64::MAX), None);
    assert_eq!(c.get_balance("a".to_string()), None);
    assert_eq!(c.get_balance("nope".to_string()), None);
}
