CREATE TABLE IF NOT EXISTS arena_users (id TEXT PRIMARY KEY, display_name TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0, points INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS arena_challenges (id TEXT PRIMARY KEY, title TEXT NOT NULL, player_a TEXT NOT NULL, player_b TEXT NOT NULL, starts_at TEXT NOT NULL, closes_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', winner TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS arena_predictions (user_id TEXT NOT NULL, challenge_id TEXT NOT NULL, pick TEXT NOT NULL CHECK(pick IN ('a','b')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,challenge_id));
CREATE TABLE IF NOT EXISTS arena_rewards (id TEXT PRIMARY KEY, title TEXT NOT NULL, cost INTEGER NOT NULL CHECK(cost>=0), stock INTEGER NOT NULL CHECK(stock>=0), enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS arena_redemptions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, reward_id TEXT NOT NULL, cost INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS arena_settlements (challenge_id TEXT PRIMARY KEY, winner TEXT NOT NULL CHECK(winner IN ('a','b')), settled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS arena_point_events (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, delta INTEGER NOT NULL, xp_delta INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_arena_leaderboard ON arena_users(xp DESC);
CREATE INDEX IF NOT EXISTS idx_arena_challenges ON arena_challenges(starts_at);

-- Triggers run in the same SQLite transaction as each INSERT; rejected purchases cannot debit points.
CREATE TRIGGER IF NOT EXISTS arena_redeem_guard BEFORE INSERT ON arena_redemptions BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM arena_rewards WHERE id=NEW.reward_id AND enabled=1 AND stock>0 AND cost=NEW.cost) THEN RAISE(ABORT,'reward unavailable') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM arena_users WHERE id=NEW.user_id AND points>=NEW.cost) THEN RAISE(ABORT,'insufficient points') END;
END;
CREATE TRIGGER IF NOT EXISTS arena_redeem_apply AFTER INSERT ON arena_redemptions BEGIN
 UPDATE arena_users SET points=points-NEW.cost WHERE id=NEW.user_id;
 UPDATE arena_rewards SET stock=stock-1 WHERE id=NEW.reward_id;
END;
CREATE TRIGGER IF NOT EXISTS arena_settle_guard BEFORE INSERT ON arena_settlements BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM arena_challenges WHERE id=NEW.challenge_id AND closes_at<=datetime('now') AND status='open') THEN RAISE(ABORT,'challenge not ready') END;
END;
CREATE TRIGGER IF NOT EXISTS arena_settle_apply AFTER INSERT ON arena_settlements BEGIN
 UPDATE arena_challenges SET winner=NEW.winner,status='settled' WHERE id=NEW.challenge_id;
 INSERT INTO arena_point_events(id,user_id,delta,xp_delta,reason)
 SELECT NEW.challenge_id||':'||p.user_id,p.user_id,CASE WHEN p.pick=NEW.winner THEN 100 ELSE 10 END,CASE WHEN p.pick=NEW.winner THEN 120 ELSE 20 END,'challenge:'||NEW.challenge_id FROM arena_predictions p WHERE p.challenge_id=NEW.challenge_id;
 UPDATE arena_users SET points=points+COALESCE((SELECT SUM(delta) FROM arena_point_events WHERE reason='challenge:'||NEW.challenge_id AND user_id=arena_users.id),0),xp=xp+COALESCE((SELECT SUM(xp_delta) FROM arena_point_events WHERE reason='challenge:'||NEW.challenge_id AND user_id=arena_users.id),0)
 WHERE id IN (SELECT user_id FROM arena_predictions WHERE challenge_id=NEW.challenge_id);
END;
