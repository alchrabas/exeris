from flask.ext.testing import TestCase
from shapely.geometry import Point
from exeris.core import deferred
from exeris.core.actions import CreateItemAction
from exeris.core.main import db
from exeris.core.models import Activity, ItemType, RootLocation, Item, Entity, ScheduledTask
from exeris.core.scheduler import ActivityProcess, Scheduler
from tests import util

__author__ = 'alek'


class SchedulerTest(TestCase):

    create_app = util.set_up_app_with_database

    def test_serializable(self):
        pass

    def test_travel_process(self):
        pass

    # kind of integration test
    def test_activity_process(self):

        self._before_activity_process()
        process = ActivityProcess()

        process.run()

        result_type = ItemType.query.filter_by(name="result").one()

        result_item = Item.query.filter_by(type=result_type).one()
        rt = RootLocation.query.one()

        self.assertEqual(rt, result_item.being_in)
        self.assertEqual("result", result_item.type.name)

    def test_scheduler(self):
        util.initialize_date()
        self._before_activity_process()

        task = ScheduledTask((ActivityProcess,), 0)
        db.session.add(task)

        db.session.flush()

        scheduler = Scheduler()
        scheduler.run_iteration()

    def _before_activity_process(self):
        hammer_type = ItemType("hammer", 300)
        result_type = ItemType("result", 200)
        db.session.add_all([hammer_type, result_type])

        rt = RootLocation(Point(1, 1), False, 134)
        db.session.add(rt)
        hammer_worked_on = Item(hammer_type, rt, 100)
        db.session.add(hammer_worked_on)

        worker = util.create_character("John", rt, util.create_player("ABC"))

        hammer = Item(hammer_type, worker, 111)
        db.session.add(hammer)
        db.session.flush()

        activity = Activity(hammer_worked_on, {"tools": [hammer_type.id]}, 1)
        db.session.add(activity)
        db.session.flush()
        result = deferred.dumps(CreateItemAction, result_type.id, activity.id, {"Edible": True})
        activity.result_actions = [result]

        worker.activity = activity

    tearDown = util.tear_down_rollback

