import unittest

from flask import Flask
from sqlalchemy.pool import StaticPool

from app import db
from app.models import User
from app.projects.been.models import BeenPlace, BeenVisit
from app.projects.been.parsing import VisitInputError
from app.projects.been.places import normalize_feature
from app.projects.been.records import add_visit, delete_visit, update_visit
from tests.been.test_parsing import LISBON


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask("been-records-test")
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        User.__table__.create(db.engine)
        BeenPlace.__table__.create(db.engine)
        BeenVisit.__table__.create(db.engine)
        user = User(email="been@example.com", full_name="Been Tester", short_name="Been")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def test_repeat_place_reuses_the_row_and_delete_removes_it(self):
        place = normalize_feature(LISBON)
        first = add_visit(
            self.user_id,
            place=place,
            activity="swam",
            when="2019-05",
            notes="first",
        )
        second = add_visit(
            self.user_id,
            place=place,
            activity=None,
            when="2022",
            notes=None,
        )
        db.session.commit()
        self.assertEqual(BeenPlace.query.count(), 1)
        self.assertEqual(first.place_id, second.place_id)
        self.assertEqual(first.date_precision, "month")
        self.assertEqual(second.date_precision, "year")

        delete_visit(second)
        db.session.commit()
        self.assertEqual(BeenPlace.query.count(), 1)

        delete_visit(first)
        db.session.commit()
        self.assertEqual(BeenPlace.query.count(), 0)
        self.assertEqual(BeenVisit.query.count(), 0)

    def test_activity_can_change_and_a_visit_needs_a_place(self):
        visit = add_visit(
            self.user_id,
            place=normalize_feature(LISBON),
            activity="sailed",
            when="",
            notes=None,
        )
        db.session.commit()
        self.assertEqual(visit.activity, "sailed")
        self.assertIsNone(visit.visited_on)
        update_visit(visit, activity="ferry", when="2018-06-02", notes="overnight")
        db.session.commit()
        self.assertEqual(visit.activity, "ferry")
        self.assertEqual(visit.date_precision, "day")
        with self.assertRaises(VisitInputError):
            add_visit(
                self.user_id,
                place=None,
                activity="swam",
                when="2019",
                notes=None,
            )
