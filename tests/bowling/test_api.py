"""Integration tests for Bowling JSON API."""

import os
import unittest

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from app import db
from app.projects.bowling.models import BowlingGame, BowlingPlayer, BowlingRoll
from app.projects.bowling.routes import bowling_bp

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _create_test_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, "app", "templates"),
    )
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test-secret"
    db.init_app(app)
    CSRFProtect(app)
    app.register_blueprint(bowling_bp)
    return app


class BowlingApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_game_with_players(self, names=("Alice", "Bob")):
        with self.app.app_context():
            game = BowlingGame(code="123456")
            db.session.add(game)
            db.session.flush()
            for index, name in enumerate(names):
                db.session.add(
                    BowlingPlayer(game_id=game.id, name=name, order_index=index)
                )
            db.session.commit()
            player_ids = [
                player.id
                for player in BowlingPlayer.query.filter_by(game_id=game.id)
                .order_by(BowlingPlayer.order_index)
                .all()
            ]
            return game.code, player_ids

    def test_create_game(self):
        response = self.client.post("/bowling/api/games")
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("code", data)
        self.assertEqual(len(data["code"]), 6)
        self.assertTrue(data["code"].isdigit())
        self.assertEqual(data["url"], f"/bowling/{data['code']}")

    def test_get_game_not_found(self):
        response = self.client.get("/bowling/api/games/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "No game found with that code.",
        )

    def test_setup_flow(self):
        create = self.client.post("/bowling/api/games")
        code = create.get_json()["code"]

        add_alice = self.client.post(
            f"/bowling/api/games/{code}/players",
            json={"name": "Alice"},
        )
        self.assertEqual(add_alice.status_code, 200)
        alice_id = add_alice.get_json()["players"][0]["id"]

        add_bob = self.client.post(
            f"/bowling/api/games/{code}/players",
            json={"name": "Bob"},
        )
        bob_id = add_bob.get_json()["players"][1]["id"]

        reorder = self.client.put(
            f"/bowling/api/games/{code}/players/order",
            json={"player_ids": [bob_id, alice_id]},
        )
        self.assertEqual(reorder.status_code, 200)
        players = reorder.get_json()["players"]
        self.assertEqual(players[0]["name"], "Bob")
        self.assertEqual(players[1]["name"], "Alice")

        start = self.client.post(f"/bowling/api/games/{code}/start")
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.get_json()["status"], "active")

    def test_rename_blocked_after_start(self):
        code, player_ids = self._create_game_with_players()
        self.client.post(f"/bowling/api/games/{code}/start")

        response = self.client.put(
            f"/bowling/api/games/{code}/players/{player_ids[0]}",
            json={"name": "Alicia"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be changed", response.get_json()["error"])

    def test_submit_roll_and_scorecard(self):
        code, player_ids = self._create_game_with_players(("Alice",))
        self.client.post(f"/bowling/api/games/{code}/start")

        roll = self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 1, "pins": 10},
        )
        self.assertEqual(roll.status_code, 200)
        player = roll.get_json()["players"][0]
        self.assertEqual(player["scorecard"]["frames"][0]["rolls"][0]["display"], "X")
        self.assertIsNone(player["scorecard"]["frames"][0]["frame_score"])

        roll2 = self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 2, "roll": 1, "pins": 7},
        )
        self.assertEqual(roll2.status_code, 200)
        self.assertTrue(roll2.get_json()["players"][0]["scorecard"]["frames"][0]["pending"])

        roll3 = self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 2, "roll": 2, "pins": 2},
        )
        self.assertEqual(roll3.status_code, 200)
        self.assertEqual(
            roll3.get_json()["players"][0]["scorecard"]["frames"][0]["frame_score"],
            19,
        )

    def test_invalid_roll_rejected(self):
        code, player_ids = self._create_game_with_players(("Alice",))
        self.client.post(f"/bowling/api/games/{code}/start")
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 1, "pins": 7},
        )

        response = self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 2, "pins": 5},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Maximum", response.get_json()["error"])

    def test_clear_frame(self):
        code, player_ids = self._create_game_with_players(("Alice",))
        self.client.post(f"/bowling/api/games/{code}/start")
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 1, "pins": 7},
        )
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 2, "pins": 2},
        )

        cleared = self.client.post(
            f"/bowling/api/games/{code}/clear",
            json={"player_id": player_ids[0], "frame": 1},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json()["players"][0]["scorecard"]["total"], None)

    def test_mark_complete_and_read_only(self):
        code, player_ids = self._create_game_with_players(("Alice",))
        self.client.post(f"/bowling/api/games/{code}/start")

        for frame in range(1, 10):
            self.client.post(
                f"/bowling/api/games/{code}/rolls",
                json={"player_id": player_ids[0], "frame": frame, "roll": 1, "pins": 10},
            )
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 10, "roll": 1, "pins": 10},
        )
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 10, "roll": 2, "pins": 10},
        )
        self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 10, "roll": 3, "pins": 10},
        )

        complete = self.client.post(f"/bowling/api/games/{code}/complete")
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.get_json()["status"], "complete")

        blocked = self.client.post(
            f"/bowling/api/games/{code}/rolls",
            json={"player_id": player_ids[0], "frame": 1, "roll": 1, "pins": 0},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("complete", blocked.get_json()["error"])

    def test_add_player_mid_active_before_lock(self):
        code, player_ids = self._create_game_with_players(("Alice",))
        self.client.post(f"/bowling/api/games/{code}/start")

        added = self.client.post(
            f"/bowling/api/games/{code}/players",
            json={"name": "Charlie"},
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(len(added.get_json()["players"]), 2)
        charlie = added.get_json()["players"][1]
        self.assertEqual(charlie["actionable_frame"], 1)
        self.assertEqual(charlie["scorecard"]["total"], None)


if __name__ == "__main__":
    unittest.main()
