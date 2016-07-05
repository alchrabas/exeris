from unittest.mock import patch

import sqlalchemy as sql
from flask.ext.testing import TestCase
from shapely.geometry import Point, Polygon

from exeris.core import deferred
from exeris.core import main, models
from exeris.core.actions import CreateItemAction, RemoveItemAction, DropItemAction, AddEntityToActivityAction, \
    SayAloudAction, MoveToLocationAction, CreateLocationAction, EatAction, ToggleCloseableAction, CreateCharacterAction, \
    GiveItemAction, JoinActivityAction, SpeakToSomebodyAction, WhisperToSomebodyAction, \
    AbstractAction, Action, TakeItemAction, DeathAction, StartControllingMovementAction, ChangeVehicleDirectionAction
from exeris.core.deferred import convert
from exeris.core.general import GameDate
from exeris.core.main import db, Events
from exeris.core.models import ItemType, Activity, Item, RootLocation, EntityProperty, TypeGroup, Event, Location, \
    LocationType, Passage, EntityTypeProperty, PassageType, Character, TerrainType, PropertyArea, TerrainArea, \
    Intent
from exeris.core.properties import P
from tests import util


class ExampleAction(AbstractAction):
    pass


class ActionsSerializationTest(TestCase):
    create_app = util.set_up_app_with_database
    tearDown = util.tear_down_rollback

    def test_parameterless_serialization(self):
        action = ExampleAction()

        serialized = deferred.serialize(action)  # serialized into two-element list: [qualname, dict with args]

        self.assertEqual("tests.test_actions.ExampleAction", serialized[0])
        self.assertEqual({}, serialized[1])

    def test_entity_parameter_serialization(self):
        hammer_type = ItemType("hammer", 30)
        hammer = Item(hammer_type, None)
        db.session.add_all([hammer_type, hammer])
        db.session.flush()

        action = RemoveItemAction(hammer)

        serialized = deferred.serialize(action)  # serialized into two-element list: [qualname, dict with args]

        self.assertEqual("exeris.core.actions.RemoveItemAction", serialized[0])
        self.assertEqual({"item": hammer.id, "gracefully": True}, serialized[1])

    def test_nested_action_serialization(self):
        class GoAndPerformAction(Action):
            @convert(executor=Character, action=Action)
            def __init__(self, executor, direction, action):
                super().__init__(executor)
                self.direction = direction
                self.action = action

        rl = RootLocation(Point(1, 1), 35)
        character = util.create_character("abc", rl, util.create_player("AHA"))
        hammer_type = ItemType("hammer", 30)
        hammer = Item(hammer_type, character)
        db.session.add_all([hammer_type, hammer, rl])
        db.session.flush()

        action = GoAndPerformAction(character, 130, RemoveItemAction(hammer, False))

        serialized = deferred.serialize(action)  # serialized into two-element list: [qualname, dict with args]

        self.assertEqual(
            "tests.test_actions.ActionsSerializationTest.test_nested_action_serialization.<locals>.GoAndPerformAction",
            serialized[0])
        self.assertEqual({
            "executor": character.id,
            "direction": 130,
            "action": [
                "exeris.core.actions.RemoveItemAction",
                {"item": hammer.id, "gracefully": False}
            ]}, serialized[1])


class CharacterActionsTest(TestCase):
    create_app = util.set_up_app_with_database
    tearDown = util.tear_down_rollback

    def test_simple_create_item_action(self):
        hammer_type = ItemType("hammer", 200)
        schema_type = ItemType("schema", 0)
        rl = RootLocation(Point(1, 2), 123)
        db.session.add_all([hammer_type, schema_type, rl])

        container = Item(schema_type, rl, weight=111)
        db.session.add(container)

        initiator = util.create_character("ABC", rl, util.create_player("janko"))

        hammer_activity = Activity(container, "dummy_activity_name", {}, {"input": "potatoes"}, 100, initiator)
        db.session.add(hammer_activity)

        action = CreateItemAction(item_type=hammer_type, properties={"Edible": {"hunger": 5}},
                                  activity=hammer_activity, initiator=initiator, used_materials="all")
        action.perform()

        items = Item.query.filter_by(type=hammer_type).all()
        self.assertEqual(1, len(items))
        self.assertEqual(hammer_type, items[0].type)
        self.assertTrue(items[0].has_property("Edible"))

        with patch("exeris.core.general.GameDate._get_timestamp", new=lambda: 1100):  # stop the time!
            util.initialize_date()
            remove_action = RemoveItemAction(items[0], True)
            remove_action.perform()

            items_count = Item.query.filter_by(type=hammer_type).count()
            self.assertEqual(0, items_count)

    def test_deferred_create_item_action(self):
        util.initialize_date()

        item_type = ItemType("hammer", 200)
        schema_type = ItemType("schema", 0)
        rl = RootLocation(Point(1, 2), 123)
        db.session.add_all([item_type, schema_type, rl])

        container = Item(schema_type, rl, weight=111)
        db.session.add(container)

        initiator = util.create_character("ABC", rl, util.create_player("janko"))

        hammer_activity = Activity(rl, "dummy_activity_name", {}, {}, 100, initiator)
        db.session.add(hammer_activity)

        db.session.flush()
        d = ["exeris.core.actions.CreateItemAction",
             {"item_type": item_type.name, "properties": {"Edible": {"strength": 5.0}},
              "used_materials": "all"}]

        # dump it, then read and run the deferred function
        action = deferred.call(d, activity=hammer_activity, initiator=initiator)

        action.perform()

        # the same tests as in simple test
        items = Item.query.filter_by(type=item_type).all()
        self.assertEqual(1, len(items))
        self.assertEqual(item_type, items[0].type)
        self.assertTrue(items[0].has_property("Edible"))

    def test_create_item_action_considering_input_material_group(self):
        """
        Create a lock and a key in an activity made of iron (for lock) and hard metal group (for key - we use steel)
        For key 'steel' should be "main" in visible_material property
        :return:
        """
        util.initialize_date()

        iron_type = ItemType("iron", 4, stackable=True)
        hard_metal_group = TypeGroup("group_hard_metal", stackable=True)
        steel_type = ItemType("steel", 5, stackable=True)

        hard_metal_group.add_to_group(steel_type, efficiency=0.5)

        lock_type = ItemType("iron_lock", 200, portable=False)
        key_type = ItemType("key", 10)

        rl = RootLocation(Point(1, 1), 213)

        initiator = util.create_character("ABC", rl, util.create_player("janko"))

        db.session.add_all([iron_type, steel_type, hard_metal_group, lock_type, key_type, rl, initiator])
        db.session.flush()

        activity = Activity(rl, "dummy_activity_name", {}, {"input": {
            iron_type.name: {
                "needed": 50, "left": 0, "used_type": iron_type.name,
            },
            hard_metal_group.name: {
                "needed": 1, "left": 0, "used_type": steel_type.name,
            }}}, 1, initiator)
        create_lock_action_args = {"item_type": lock_type.name, "properties": {},
                                   "used_materials": {iron_type.name: 50}}
        create_lock_action = ["exeris.core.actions.CreateItemAction", create_lock_action_args]

        create_key_action_args = {"item_type": key_type.name, "properties": {},
                                  "used_materials": {hard_metal_group.name: 1},
                                  "visible_material": {"main": hard_metal_group.name}}
        create_key_action = ["exeris.core.actions.CreateItemAction", create_key_action_args]
        activity.result_actions = [create_lock_action, create_key_action]

        iron = Item(iron_type, activity, amount=50, role_being_in=False)
        steel = Item(steel_type, activity, amount=20, role_being_in=False)

        db.session.add_all([iron, steel])
        db.session.flush()

        for serialized_action in activity.result_actions:
            action = deferred.call(serialized_action, activity=activity, initiator=initiator)
            action.perform()

        new_lock = Item.query.filter_by(type=lock_type).one()
        used_iron = Item.query.filter(Item.is_used_for(new_lock)).one()
        self.assertEqual(50, used_iron.amount)
        self.assertEqual(200, used_iron.weight)

        iron_piles_left = Item.query.filter_by(type=iron_type).filter(Item.is_in(rl)).count()
        self.assertEqual(0, iron_piles_left)  # no pile of iron, everything was used

        new_key = Item.query.filter_by(type=key_type).one()
        used_steel = Item.query.filter(Item.is_used_for(new_key)).one()
        self.assertEqual(2, used_steel.amount)
        self.assertEqual(10, used_steel.weight)
        self.assertEqual(18, steel.amount)

        visible_material_prop = EntityProperty.query.filter_by(entity=new_key, name=P.VISIBLE_MATERIAL).one()
        self.assertEqual({"main": steel_type.name}, visible_material_prop.data)  # steel is visible

    def test_create_location_action(self):
        rl = RootLocation(Point(1, 1), 33)
        building_type = LocationType("building", 500)
        scaffolding_type = ItemType("scaffolding", 200, portable=False)
        scaffolding = Item(scaffolding_type, rl)
        stone_type = ItemType("stone", 10, stackable=True)

        initiator = util.create_character("char", rl, util.create_player("Hyhy"))
        input_requirements = {stone_type.name: {"needed": 5, "left": 0, "used_type": stone_type.name}}
        activity = Activity(scaffolding, "building_building", {}, {"input": input_requirements}, 1, initiator)
        stone = Item(stone_type, activity, amount=20, role_being_in=False)

        db.session.add_all([building_type, scaffolding_type, scaffolding, rl, initiator, activity, stone_type, stone])

        action = CreateLocationAction(location_type=building_type, used_materials="all", properties={P.ENTERABLE: {}},
                                      visible_material={"main": stone_type.name}, activity=activity,
                                      initiator=initiator)
        action.perform()

        new_building = Location.query.filter_by(type=building_type).one()
        Passage.query.filter(Passage.between(rl, new_building)).one()
        self.assertTrue(new_building.has_property(P.ENTERABLE))
        self.assertTrue(new_building.has_property(P.VISIBLE_MATERIAL, main=stone_type.name))

        used_stone = Item.query.filter(Item.is_used_for(new_building)).one()
        self.assertEqual(20, used_stone.amount)

    def test_drop_item_action_on_hammer(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)

        plr = util.create_player("aaa")
        doer = util.create_character("John", rl, plr)
        obs = util.create_character("obs", rl, plr)

        hammer_type = ItemType("stone_hammer", 200)
        hammer = Item(hammer_type, doer, weight=200)

        db.session.add_all([rl, hammer_type, hammer])
        db.session.flush()

        action = DropItemAction(doer, hammer)

        action.perform()

        self.assertEqual(rl, doer.being_in)
        self.assertEqual(rl, hammer.being_in)

        # test events
        event_drop_doer = Event.query.filter_by(type_name=Events.DROP_ITEM + "_doer").one()

        self.assertEqual(hammer.pyslatize(), event_drop_doer.params)
        event_drop_obs = Event.query.filter_by(type_name=Events.DROP_ITEM + "_observer").one()
        self.assertEqual(dict(hammer.pyslatize(), groups={"doer": doer.pyslatize()}), event_drop_obs.params)

    def test_drop_item_action_drop_stackable(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)

        plr = util.create_player("aaa")
        doer = util.create_character("John", rl, plr)
        obs = util.create_character("obs", rl, plr)

        potatoes_type = ItemType("potatoes", 1, stackable=True)
        potatoes = Item(potatoes_type, doer, amount=200)

        db.session.add_all([rl, potatoes_type, potatoes])

        amount = 50
        action = DropItemAction(doer, potatoes, amount)
        action.perform()

        # test events
        event_drop_doer = Event.query.filter_by(type_name=Events.DROP_ITEM + "_doer").one()
        self.assertEqual(potatoes.pyslatize(item_amount=amount), event_drop_doer.params)
        event_drop_obs = Event.query.filter_by(type_name=Events.DROP_ITEM + "_observer").one()
        self.assertEqual(dict(potatoes.pyslatize(item_amount=amount), groups={"doer": doer.pyslatize()}),
                         event_drop_obs.params)
        Event.query.delete()

        self.assertEqual(150, potatoes.weight)  # 50 of 200 was dropped
        potatoes_on_ground = Item.query.filter(Item.is_in(rl)).filter_by(type=potatoes_type).one()
        self.assertEqual(50, potatoes_on_ground.weight)

        action = DropItemAction(doer, potatoes, 150)
        action.perform()
        db.session.flush()  # to correctly check deletion

        self.assertIsNone(potatoes.being_in)  # check whether the object is deleted
        self.assertIsNone(potatoes.used_for)
        self.assertTrue(sql.inspect(potatoes).deleted)

        self.assertEqual(200, potatoes_on_ground.weight)

    def test_drop_item_action_on_stackable_with_parts(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)
        plr = util.create_player("aaa")
        doer = util.create_character("John", rl, plr)
        obs = util.create_character("obs", rl, plr)

        potatoes_type = ItemType("potatoes", 1, stackable=True)
        strawberries_type = ItemType("strawberries", 5, stackable=True)
        grapes_type = ItemType("grapes", 3, stackable=True)
        cake_type = ItemType("cake", 100, stackable=True)

        # check multipart resources
        cake_in_inv = Item(cake_type, doer, weight=300)
        cake_ground = Item(cake_type, rl, weight=300)
        other_cake_ground = Item(cake_type, rl, weight=300)

        db.session.add_all([rl, strawberries_type, grapes_type, cake_type, cake_in_inv, cake_ground, other_cake_ground])
        db.session.flush()

        cake_in_inv.visible_parts = [grapes_type.name, strawberries_type.name]
        cake_ground.visible_parts = [grapes_type.name, strawberries_type.name]

        other_cake_ground.visible_parts = [strawberries_type.name, potatoes_type.name]

        db.session.flush()

        action = DropItemAction(doer, cake_in_inv, 1)
        action.perform()

        self.assertEqual(200, cake_in_inv.weight)
        self.assertEqual(400, cake_ground.weight)
        self.assertEqual(300, other_cake_ground.weight)  # it isn't merged with different cake

        db.session.delete(cake_ground)  # remove cake with the same parts

        action = DropItemAction(doer, cake_in_inv, 1)
        action.perform()

        self.assertEqual(100, cake_in_inv.weight)
        self.assertEqual(300, other_cake_ground.weight)

        new_ground_cake = Item.query.filter(Item.is_in(rl)).filter_by(type=cake_type). \
            filter_by(visible_parts=[grapes_type.name, strawberries_type.name]).one()
        self.assertEqual(100, new_ground_cake.weight)
        self.assertEqual([grapes_type.name, strawberries_type.name], new_ground_cake.visible_parts)

    def test_drop_action_failure_not_in_inv(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)
        char = util.create_character("John", rl, util.create_player("aaa"))

        hammer_type = ItemType("stone_hammer", 200)

        # hammer is already on the ground
        hammer = Item(hammer_type, rl, weight=200)

        db.session.add_all([rl, hammer_type, hammer])

        action = DropItemAction(char, hammer)
        self.assertRaises(main.EntityNotInInventoryException, action.perform)

    def test_drop_action_failure_too_little_potatoes(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)
        char = util.create_character("John", rl, util.create_player("aaa"))

        # there are too little potatoes
        potatoes_type = ItemType("potatoes", 20, stackable=True)

        potatoes = Item(potatoes_type, char, amount=10)

        db.session.add_all([potatoes_type, potatoes])
        db.session.flush()

        action = DropItemAction(char, potatoes, 201)
        self.assertRaises(main.InvalidAmountException, action.perform)

    def test_add_item_to_activity_action(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)
        initiator = util.create_character("John", rl, util.create_player("aaa"))
        observer = util.create_character("obs", rl, util.create_player("abc"))

        anvil_type = ItemType("anvil", 400, portable=False)
        anvil = Item(anvil_type, rl)
        metal_group = TypeGroup("group_metal", stackable=True)
        iron_type = ItemType("iron", 10, stackable=True)
        metal_group.add_to_group(iron_type, efficiency=0.5)

        iron = Item(iron_type, initiator, amount=20)

        db.session.add_all([rl, initiator, anvil_type, anvil, metal_group, iron_type, iron])
        db.session.flush()

        activity = Activity(anvil, "dummy_activity_name", {}, {
            "input": {
                metal_group.name: {"needed": 10, "left": 10}
            }
        }, 1, initiator)

        action = AddEntityToActivityAction(initiator, iron, activity, 4)
        action.perform()

        self.assertEqual({metal_group.name: {"needed": 10, "left": 8, "used_type": iron_type.name}},
                         activity.requirements["input"])
        self.assertEqual(16, iron.amount)

        action = AddEntityToActivityAction(initiator, iron, activity, 16)
        action.perform()

        self.assertEqual({metal_group.name: {"needed": 10, "left": 0, "used_type": iron_type.name}},
                         activity.requirements["input"])
        self.assertIsNone(iron.parent_entity)
        self.assertTrue(sql.inspect(iron).deleted)
        Event.query.delete()

        # TEST TYPE MATCHING MULTIPLE REQUIREMENT GROUPS

        wood_group = TypeGroup("group_wood", stackable=True)
        fuel_group = TypeGroup("group_fuel", stackable=True)
        oak_type = ItemType("oak", 50, stackable=True)
        wood_group.add_to_group(oak_type)
        fuel_group.add_to_group(oak_type)

        oak = Item(oak_type, initiator, amount=20)
        db.session.add_all([wood_group, oak_type, fuel_group, oak])

        activity = Activity(anvil, "dummy_activity_name", {}, {
            "input": {
                metal_group.name: {"needed": 10, "left": 10},
                fuel_group.name: {"needed": 10, "left": 10},
                wood_group.name: {"needed": 10, "left": 10},
            }
        }, 1, initiator)
        db.session.add(activity)

        action = AddEntityToActivityAction(initiator, oak, activity, 20)  # added as the first material from the list
        action.perform()

        # in this case oak should be added as fuel, because material groups are sorted and applied alphabetically
        # always exactly one group can be fulfilled at once
        self.assertEqual({
            metal_group.name: {"needed": 10, "left": 10},
            fuel_group.name: {"needed": 10, "left": 0, "used_type": oak_type.name},
            wood_group.name: {"needed": 10, "left": 10},
        }, activity.requirements["input"])

        self.maxDiff = None
        event_add_doer = Event.query.filter_by(type_name=Events.ADD_TO_ACTIVITY + "_doer").one()
        self.assertEqual({"groups": {
            "item": oak.pyslatize(item_amount=10),
            "activity": activity.pyslatize(),
        }}, event_add_doer.params)

        event_add_obs = Event.query.filter_by(type_name=Events.ADD_TO_ACTIVITY + "_observer").one()
        self.assertEqual({
            "groups": {
                "item": oak.pyslatize(item_amount=10),
                "activity": activity.pyslatize(),
                "doer": initiator.pyslatize(),
            }
        }, event_add_obs.params)
        Event.query.delete()

        action = AddEntityToActivityAction(initiator, oak, activity, 10)
        action.perform()  # add materials to another group

        self.assertEqual({
            metal_group.name: {"needed": 10, "left": 10},
            fuel_group.name: {"needed": 10, "left": 0, "used_type": oak_type.name},
            wood_group.name: {"needed": 10, "left": 0, "used_type": oak_type.name},
        }, activity.requirements["input"])
        self.assertTrue(sql.inspect(oak).deleted)

    def test_add_nonstackable_item_to_activity(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 111)
        initiator = util.create_character("John", rl, util.create_player("aaa"))

        anvil_type = ItemType("anvil", 400, portable=False)
        anvil = Item(anvil_type, rl)
        tools_group = TypeGroup("group_tools", stackable=False)
        hammer_type = ItemType("hammer", 10, stackable=False)
        tools_group.add_to_group(hammer_type, efficiency=5.0)

        hammer = Item(hammer_type, initiator, quality=1.5)

        db.session.add_all([rl, initiator, anvil_type, anvil, tools_group, hammer_type, hammer])
        db.session.flush()

        activity = Activity(anvil, "dummy_activity_name", {}, {
            "input": {
                tools_group.name: {"needed": 10, "left": 10}
            }
        }, 1, initiator)

        action = AddEntityToActivityAction(initiator, hammer, activity, 1)
        action.perform()

        self.assertEqual({tools_group.name: {"needed": 10, "left": 9, "used_type": hammer_type.name, "quality": 0.75}},
                         activity.requirements["input"])
        self.assertEqual(activity, hammer.used_for)

    def test_say_aloud_action(self):
        util.initialize_date()

        grass_type = TerrainType("grass")
        TypeGroup.by_name(main.Types.LAND_TERRAIN).add_to_group(grass_type)
        grass_poly = Polygon([(0, 0), (0, 30), (30, 30), (30, 0)])
        grass_terrain = TerrainArea(grass_poly, grass_type)
        grass_visibility_area = PropertyArea(models.AREA_KIND_VISIBILITY, 1, 1, grass_poly, grass_terrain)

        db.session.add_all([grass_type, grass_terrain, grass_visibility_area])

        rl1 = RootLocation(Point(0, 0), 123)
        rl2 = RootLocation(Point(0, 11), 123)
        rl3 = RootLocation(Point(0, 21), 123)
        building_type = LocationType("building", 200)
        building = Location(rl1, building_type)
        plr = util.create_player("eee")
        doer = util.create_character("doer", building, plr)
        obs_same_loc = util.create_character("obs_same_loc", building, plr)
        obs_near_loc = util.create_character("obs_near_loc", rl2, plr)

        door_to_building = Passage.query.filter(Passage.between(rl1, building)).one()
        closeable_property = EntityProperty(P.CLOSEABLE, {"closed": True})
        door_to_building.properties.append(closeable_property)

        db.session.add_all([rl1, rl2, rl3, building_type, building, doer])

        # no window in building -> nobody but obs_same_loc can hear it
        message_text = "Hello!"
        action = SayAloudAction(doer, message_text)
        action.perform()

        event_say_doer = Event.query.filter_by(type_name=Events.SAY_ALOUD + "_doer").one()
        self.assertEqual({"message": message_text}, event_say_doer.params)
        self.assertCountEqual([doer], event_say_doer.observers)

        event_say_observer = Event.query.filter_by(type_name=Events.SAY_ALOUD + "_observer").one()
        self.assertEqual({"groups": {"doer": doer.pyslatize()}, "message": message_text}, event_say_observer.params)
        self.assertCountEqual([obs_same_loc], event_say_observer.observers)

        closeable_property.data = {"closed": False}

        # now there will be open connection between rl1 and building

        # clean up the events
        Event.query.delete()

        action = SayAloudAction(doer, message_text)
        action.perform()

        event_say_doer = Event.query.filter_by(type_name=Events.SAY_ALOUD + "_doer").one()
        self.assertEqual({"message": message_text}, event_say_doer.params)
        self.assertCountEqual([doer], event_say_doer.observers)

        event_say_observer = Event.query.filter_by(type_name=Events.SAY_ALOUD + "_observer").one()
        self.assertEqual({"groups": {"doer": doer.pyslatize()}, "message": message_text}, event_say_observer.params)
        self.assertCountEqual([obs_same_loc, obs_near_loc], event_say_observer.observers)

    def test_speak_to_somebody_action(self):
        util.initialize_date()

        rl = RootLocation(Point(13, 15), 123)

        doer = util.create_character("doer", rl, util.create_player("eee1"))
        listener = util.create_character("listener", rl, util.create_player("eee2"))
        observer = util.create_character("obs_same_loc", rl, util.create_player("eee3"))
        db.session.add(rl)

        speak_to_somebody = SpeakToSomebodyAction(doer, listener, "ABC")
        speak_to_somebody.perform()

        event_doer = Event.query.filter_by(type_name=Events.SPEAK_TO_SOMEBODY + "_doer").one()
        event_observer = Event.query.filter_by(type_name=Events.SPEAK_TO_SOMEBODY + "_observer").one()

        self.assertEqual({"message": "ABC", "groups": {"target": listener.pyslatize()}}, event_doer.params)
        self.assertEqual({"message": "ABC", "groups": {"doer": doer.pyslatize(), "target": listener.pyslatize()}},
                         event_observer.params)

    def test_whisper_to_somebody_action(self):
        util.initialize_date()

        rl = RootLocation(Point(13, 15), 123)

        doer = util.create_character("doer", rl, util.create_player("eee1"))
        listener = util.create_character("listener", rl, util.create_player("eee2"))
        observer = util.create_character("obs_same_loc", rl, util.create_player("eee3"))
        db.session.add(rl)
        db.session.flush()

        whisper_to_somebody = WhisperToSomebodyAction(doer, listener, "ABC")
        whisper_to_somebody.perform()

        event_doer = Event.query.filter_by(type_name=Events.WHISPER + "_doer").one()
        event_observer = Event.query.filter_by(type_name=Events.WHISPER + "_observer").one()

        self.assertEqual({"message": "ABC", "groups": {"target": listener.pyslatize()}}, event_doer.params)
        self.assertEqual({"message": "ABC", "groups": {"doer": doer.pyslatize(), "target": listener.pyslatize()}},
                         event_observer.params)

    def test_enter_building_there_and_back_again_success(self):
        util.initialize_date()

        building_type = LocationType("building", 200)
        rl = RootLocation(Point(1, 1), 222)
        building = Location(rl, building_type, title="Small hut")

        char = util.create_character("John", rl, util.create_player("Eddy"))

        db.session.add_all([rl, building])

        passage = Passage.query.filter(Passage.between(rl, building)).one()
        enter_loc_action = MoveToLocationAction(char, passage)
        enter_loc_action.perform()

        self.assertEqual(building, char.being_in)

        enter_loc_action = MoveToLocationAction(char, passage)
        enter_loc_action.perform()
        self.assertEqual(rl, char.being_in)

    def test_eat_action_success(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 222)
        char = util.create_character("John", rl, util.create_player("Eddy"))

        potatoes_type = ItemType("potatoes", 10, stackable=True)
        potatoes = Item(potatoes_type, char, amount=30)

        potatoes_type.properties.append(
            EntityTypeProperty(P.EDIBLE, data={"satiation": 0.01, "hunger": 0.2, "strength": 0.3}))

        db.session.add_all([rl, potatoes_type, potatoes])

        action = EatAction(char, potatoes, 3)
        action.perform()

        self.assertAlmostEqual(0.03, char.satiation)
        self.assertAlmostEqual(0.6, char.eating_queue["hunger"])
        self.assertAlmostEqual(0.9, char.eating_queue["strength"])

    def test_create_open_then_close_then_open_action(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 222)
        strange_passage_type = PassageType("strange_passage", False)
        building_type = LocationType("building", 100)
        building = Location(rl, building_type, passage_type=strange_passage_type)
        char = util.create_character("John", rl, util.create_player("Eddy"))

        closeable_passage = Passage.query.filter(Passage.between(rl, building)).one()

        # it's open by default
        strange_passage_type.properties.append(EntityTypeProperty(P.CLOSEABLE, {"closed": False}))

        db.session.add_all([rl, strange_passage_type, building_type, building])

        self.assertEqual(True, closeable_passage.is_open())

        closeable_action = ToggleCloseableAction(char, closeable_passage)  # toggle to closed
        closeable_action.perform()

        self.assertEqual(False, closeable_passage.is_open())

        closeable_action = ToggleCloseableAction(char, closeable_passage)  # toggle to open
        closeable_action.perform()

        self.assertEqual(True, closeable_passage.is_open())

    def test_give_stackable_item_action_give_6_and_then_try_to_give_too_much(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)

        plr = util.create_player("ala123")
        giver = util.create_character("postac", rl, plr)
        receiver = util.create_character("postac", rl, plr)
        potatoes_type = ItemType("potatoes", 5, stackable=True)
        potatoes = Item(potatoes_type, giver, amount=10)

        db.session.add_all([rl, potatoes_type, potatoes])

        give_action = GiveItemAction(giver, potatoes, receiver, amount=4)
        give_action.perform()

        potatoes_of_giver = Item.query.filter_by(type=potatoes_type).filter(Item.is_in(giver)).one()
        potatoes_of_receiver = Item.query.filter_by(type=potatoes_type).filter(Item.is_in(receiver)).one()

        self.assertEqual(6, potatoes_of_giver.amount)
        self.assertEqual(4, potatoes_of_receiver.amount)

        give_action = GiveItemAction(giver, potatoes, receiver, amount=8)
        self.assertRaises(main.InvalidAmountException, give_action.perform)

    def test_join_activity_action_try_join_too_far_away_and_then_success(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)
        worker = util.create_character("postac", rl, util.create_player("ala123"))
        anvil_type = ItemType("anvil", 300, portable=False)
        anvil = Item(anvil_type, rl)
        activity = Activity(None, "activity", {"data": True}, {}, 11, worker)

        db.session.add_all([rl, anvil_type, anvil, activity])

        join_activity_action = JoinActivityAction(worker, activity)
        self.assertRaises(main.TooFarFromActivityException, join_activity_action.perform)

        activity.being_in = anvil

        join_activity_action = JoinActivityAction(worker, activity)
        join_activity_action.perform()

    def test_death_action(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)
        char = util.create_character("postac", rl, util.create_player("ala123"))

        db.session.add(rl)

        action = DeathAction(char)
        action.perform()

        self.assertEqual(main.Types.DEAD_CHARACTER, char.type.name)
        self.assertEqual(GameDate.now().game_timestamp, char.get_property(P.DEATH_INFO)["date"])
        self.assertAlmostEqual(GameDate.now().game_timestamp, char.get_property(P.DEATH_INFO)["date"], delta=3)


class IntentTest(TestCase):
    create_app = util.set_up_app_with_database
    tearDown = util.tear_down_rollback

    def test_perform_deferrable_action(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)
        rl_very_far_away = RootLocation(Point(200, 200), 11)
        char = util.create_character("postac", rl, util.create_player("ala123"))

        hammer_type = ItemType("stone_hammer", 200)

        # hammer is already on the ground
        hammer = Item(hammer_type, rl_very_far_away)
        db.session.add_all([rl, rl_very_far_away, hammer_type, hammer])

        take_action = TakeItemAction(char, hammer)
        deferred.perform_or_turn_into_intent(char, take_action)

        # check if intent parameters were correctly guessed
        self.assertEqual(1, Intent.query.count())

        self.assertEqual(
            ["exeris.core.actions.ControlMovementAction", {"executor": char.id,
                                                           "moving_entity": char.id,
                                                           "travel_action": ["exeris.core.actions.TravelToEntityAction",
                                                                             {"entity": hammer.id,
                                                                              "executor": char.id}],
                                                           "target_action": ["exeris.core.actions.TakeItemAction",
                                                                             {"executor": char.id,
                                                                              "item": hammer.id, "amount": 1}]
                                                           }],
            Intent.query.one().serialized_action)
        self.assertEqual(main.Intents.WORK, Intent.query.one().type)

        hammer.being_in = rl
        take_action = TakeItemAction(char, hammer, amount=-1)

        # InvalidAmountException cannot be turned into intent
        self.assertRaises(main.InvalidAmountException,
                          lambda: deferred.perform_or_turn_into_intent(char, take_action))

    def test_start_controlling_vehicle_movement_and_change_direction(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)
        vehicle_type = LocationType("cart", 500)
        vehicle_type.properties.append(EntityTypeProperty(P.MOBILE, {"speed": 10}))
        vehicle = Location(rl, vehicle_type)

        steering_room_type = LocationType("steering_room", 400)
        steering_room = Location(vehicle, steering_room_type)
        db.session.add_all([rl, vehicle_type, vehicle, steering_room_type, steering_room])
        db.session.flush()
        steering_room.properties.append(EntityProperty(P.CONTROLLING_MOVEMENT, data={"moving_entity_id": vehicle.id}))
        # create a single-location vehicle

        char = util.create_character("postac", steering_room, util.create_player("ala123"))

        start_controlling_movmeent_action = StartControllingMovementAction(char)
        start_controlling_movmeent_action.perform()

        controlling_movement_intent = Intent.query.one()
        self.assertEqual(char, controlling_movement_intent.executor)
        self.assertEqual(vehicle, controlling_movement_intent.target)
        action = controlling_movement_intent.serialized_action
        self.assertEqual("exeris.core.actions.ControlMovementAction", action[0])
        self.assertEqual(11, action[1]["travel_action"][1]["direction"])

        change_direction_action = ChangeVehicleDirectionAction(char, 30)
        change_direction_action.perform()

        action = controlling_movement_intent.serialized_action
        self.assertEqual("exeris.core.actions.ControlMovementAction", action[0])
        self.assertEqual(30, action[1]["travel_action"][1]["direction"])

        lazy_char = util.create_character("postac2", steering_room, util.create_player("ala1234"))

        change_direction_action = ChangeVehicleDirectionAction(lazy_char, 70)
        self.assertRaises(main.NotControllingMovementException, change_direction_action.perform)

    def test_start_walking_and_change_direction(self):
        util.initialize_date()

        rl = RootLocation(Point(1, 1), 11)

        db.session.add(rl)

        char = util.create_character("postac", rl, util.create_player("ala123"))
        db.session.flush()

        start_controlling_movmeent_action = StartControllingMovementAction(char)
        start_controlling_movmeent_action.perform()

        control_movement_intent = Intent.query.one()
        control_movement_action = control_movement_intent.serialized_action
        self.assertEqual("exeris.core.actions.ControlMovementAction", control_movement_action[0])
        self.assertEqual(11, control_movement_action[1]["travel_action"][1]["direction"])

        change_direction_action = ChangeVehicleDirectionAction(char, 30)
        change_direction_action.perform()

        control_movement_intent = Intent.query.one()
        control_movement_action = control_movement_intent.serialized_action
        self.assertEqual(30, control_movement_action[1]["travel_action"][1]["direction"])


class PlayerActionsTest(TestCase):
    create_app = util.set_up_app_with_database
    tearDown = util.tear_down_rollback

    def test_create_character_action(self):
        util.initialize_date()
        rl = RootLocation(Point(2, 3), 112)
        plr = util.create_player("ala123")

        db.session.add(rl)

        create_character1_action = CreateCharacterAction(plr, "postac", Character.SEX_MALE, "en")
        create_character1_action.perform()

        create_character2_action = CreateCharacterAction(plr, "postacka", Character.SEX_FEMALE, "en")
        create_character2_action.perform()

        char1 = Character.query.filter_by(sex=Character.SEX_MALE).one()
        char2 = Character.query.filter_by(sex=Character.SEX_FEMALE).one()
        self.assertCountEqual([char1, char2], plr.alive_characters)
