import unittest
from unittest.mock import patch
from flask import Flask

from app.projects.recipes.routes import recipes_bp


def _create_test_app():
    app = Flask(__name__, template_folder="../../templates")
    app.config["TESTING"] = True
    app.register_blueprint(recipes_bp)
    return app


class TestRecipesRoutes(unittest.TestCase):
    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    @patch("app.projects.recipes.routes.log_project_visit")
    def test_recipes_index(self, mock_log):
        response = self.client.get("/recipes/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pumpkin Banana Muffins", response.data)
        self.assertIn(b"Pancakes", response.data)
        self.assertIn(b"/recipes/pancakes", response.data)

    @patch("app.projects.recipes.routes.log_project_visit")
    def test_pumpkin_banana_muffins_route(self, mock_log):
        response = self.client.get("/recipes/pumpkin-banana-muffins")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pumpkin Banana Muffins", response.data)
        self.assertIn(b"All-purpose flour", response.data)

    @patch("app.projects.recipes.routes.log_project_visit")
    def test_pancakes_route(self, mock_log):
        response = self.client.get("/recipes/pancakes")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pancakes", response.data)
        self.assertIn(b"Baking powder", response.data)
        self.assertIn(b"All-purpose flour", response.data)
        self.assertIn(b"No buttermilk?", response.data)
