from exeris.core.deferred import expected_types
from exeris.core.main import db
from exeris.core import models

from exeris.core.general import SameLocationRange, EventCreator

__author__ = 'alek'


class AbstractAction:  # top level, we don't assume anything

    def perform(self):
        self.perform_action()


class Action(AbstractAction):  # top level character action, where we only know that it's done by a character

    def __init__(self, executor):
        self.executor = executor


# rich collection of pre-configured actions
class ActionOnSelf(Action):
    def __init__(self, executor):
        super().__init__(executor)


class ActionOnItem(Action):

    def __init__(self, executor, item, rng=SameLocationRange):
        super().__init__(executor)
        self.item = item
        self.rng = rng


class ActionOnLocation(Action):
    def __init__(self, executor, location, rng=SameLocationRange):
        super().__init__(executor)
        self.location = location
        self.rng = rng


class ActionOnActivity(Action):
    def __init__(self, executor, activity, rng=SameLocationRange):
        super().__init__(executor)
        self.activity = activity
        self.rng = rng


class ActionOnItemAndActivity(Action):
    def __init__(self, executor, item, activity, rng=SameLocationRange):
        super().__init__(executor)
        self.item = item
        self.activity = activity
        self.rng = rng


class ActionOnItemAndCharacter(Action):
    def __init__(self, executor, item, character, rng=SameLocationRange):
        super().__init__(executor)
        self.item = item
        self.character = character
        self.rng = rng


####################
# ABSTRACT ACTIONS #
####################

class CreateItemAction(AbstractAction):

    @expected_types(models.ItemType, models.Activity, None)
    def __init__(self, item_type, source_activity, properties):
        print(item_type.id)
        print(source_activity)
        print(properties)
        self.item_type = item_type
        self.source_activity = source_activity
        self.properties = properties

    def perform_action(self):
        item = models.Item(self.item_type, self.source_activity.being_in.being_in, self.item_type.unit_weight)

        db.session.add(item)

        for property_name in self.properties:
            db.session.add(models.EntityProperty(item, property_name, self.properties[property_name]))


class RemoveItemAction(AbstractAction):

    @expected_types(models.Item, None)
    def __init__(self, item, gracefully=True):
        self.item = item
        self.gracefully = gracefully

    def perform_action(self):
        self.item.remove(self.gracefully)


##############################
# CHARACTER-SPECIFIC ACTIONS #
##############################


class DropItemAction(ActionOnItem):

    def __init__(self, executor, item):
        super().__init__(executor, item)

    def perform_action(self):
        self.item.being_in = self.executor.being_in

        EventCreator.base("event_drop_item", self.rng, {"item_name": self.item.type.name}, self.executor)
