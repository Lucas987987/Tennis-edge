CREATE TABLE IF NOT EXISTS arena_cards (
 user_id TEXT NOT NULL, card_id TEXT NOT NULL, player_name TEXT NOT NULL,
 earned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id,card_id)
);
CREATE INDEX IF NOT EXISTS idx_arena_cards_user ON arena_cards(user_id);
CREATE TRIGGER IF NOT EXISTS arena_demo_cards_award AFTER INSERT ON arena_settlements
WHEN NEW.challenge_id IN ('arena-demo-1','arena-demo-2','arena-demo-3')
BEGIN
 INSERT OR IGNORE INTO arena_cards(user_id,card_id,player_name)
 SELECT p.user_id, NEW.challenge_id||':'||NEW.winner,
 CASE WHEN NEW.challenge_id='arena-demo-1' THEN CASE WHEN NEW.winner='a' THEN 'Joueur Alpha' ELSE 'Joueur Bêta' END
      WHEN NEW.challenge_id='arena-demo-2' THEN CASE WHEN NEW.winner='a' THEN 'Joueur Gamma' ELSE 'Joueur Delta' END
      ELSE CASE WHEN NEW.winner='a' THEN 'Joueur Epsilon' ELSE 'Joueur Zêta' END END
 FROM arena_predictions p WHERE p.challenge_id=NEW.challenge_id AND p.pick=NEW.winner;
END;
