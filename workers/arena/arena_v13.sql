
-- Idempotent migration: award a collectible for correct predictions on all non-demo matches.
CREATE TRIGGER IF NOT EXISTS arena_real_cards_award AFTER INSERT ON arena_settlements
WHEN NEW.challenge_id NOT LIKE 'arena-demo-%'
BEGIN
 INSERT OR IGNORE INTO arena_cards(user_id,card_id,player_name)
 SELECT p.user_id,NEW.challenge_id||':'||NEW.winner,
 CASE WHEN NEW.winner='a' THEN c.player_a ELSE c.player_b END
 FROM arena_predictions p JOIN arena_challenges c ON c.id=p.challenge_id
 WHERE p.challenge_id=NEW.challenge_id AND p.pick=NEW.winner;
END;
