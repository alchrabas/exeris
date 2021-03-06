import json
import logging
import logging.config

import hashlib
import os
import project_root
from Crypto.Cipher import AES
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
app = None
property_cache = None

logger = logging.getLogger(__name__)


class Errors:
    INVALID_TARGET_GENERIC = "error_invalid_target_generic"
    INVALID_TARGET = "error_invalid_target"
    ITEM_NOT_APPLICABLE_FOR_ACTIVITY = "error_item_not_applicable_for_activity"
    ONLY_SPECIFIC_TYPE_FOR_GROUP = "error_only_specific_type_for_group"
    INVALID_SHIP_TYPE_FOR_BOARDING = "error_invalid_ship_type_for_boarding"
    SHIP_NOT_BOARDED = "error_ship_not_boarded"
    CANNOT_UNBOARD_FROM_OWN_SHIP = "error_cannot_unboard_from_own_ship"
    ALREADY_BOARDED = "error_already_boarded"
    CANNOT_BOARD_OWN_SHIP = "error_cannot_board_own_ship"
    NOT_TRAVERSABLE_TERRAIN = "error_not_traversable_terrain"
    CANNOT_UNBIND_NOT_LEAF = "error_cannot_unbind_not_leaf"
    ENTITY_NOT_BINDABLE = "error_entity_not_bindable"
    ENTITY_NOT_BOUND = "error_entity_not_bound"
    ENTITY_ALREADY_BOUND = "error_entity_already_bound"
    INVALID_ACTIVITY_CONTAINER = "error_invalid_activity_container"
    LOCK_ALREADY_EXISTS = "error_lock_already_exists"
    NO_KEY_TO_LOCK = "error_no_key_to_lock"
    ENTITY_MISSING_PROPERTY = "error_entity_missing_property"
    CANNOT_ENTER_LOCATION = "error_cannot_enter_location"
    NOT_CONTROLLING_MOVEMENT = "error_not_controlling_movement"
    VEHICLE_ALREADY_CONTROLLED = "error_vehicle_already_controlled"
    CANNOT_CONTROL_MOVEMENT = "error_cannot_control_movement"
    CHARACTER_DEAD = "error_character_dead"
    TOO_CLOSE_TO_OTHER_PERMANENT_LOCATION = "error_too_close_to_other_permanent_location"
    ACTIVITY_ALREADY_EXISITS_ON_ENTITY = "error_activity_already_exists_on_entity"
    TOO_MANY_EXISTING_ENTITIES = "error_too_many_existing_entities"
    TOO_FEW_PARTICIPANTS_IN_ACTIVITY = "error_few_many_participants_in_activity"
    TOO_MANY_PARTICIPANTS_IN_ACTIVITY = "error_too_many_participants_in_activity"
    INVALID_TERRAIN_TYPE = "error_invalid_terrain_type"
    INVALID_LOCATION_TYPE = "error_invalid_location_type"
    CANNOT_ATTACK_YOURSELF = "error_cannot_attack_yourself"
    ENTITY_UNSUPPORTED_OPERATION = "error_entity_unsupported_operation"
    TOO_LOW_SKILL = "error_too_low_skill"
    NO_INPUT_MATERIALS = "error_no_input_materials"
    ENTITY_NOT_IN_INVENTORY = "error_entity_not_in_inventory"
    ENTITY_TOO_FAR_AWAY = "error_entity_too_far_away"
    ACTIVITY_TARGET_TOO_FAR_AWAY = "error_activity_target_too_far_away"
    TOO_FAR_FROM_ACTIVITY = "error_too_far_from_activity"
    NO_MACHINE_FOR_ACTIVITY = "error_no_machine_for_activity"
    NO_TOOL_FOR_ACTIVITY = "error_no_tool_for_activity"
    OWN_INVENTORY_CAPACITY_EXCEEDED = "error_own_inventory_capacity_exceeded"
    TARGET_INVENTORY_CAPACITY_EXCEEDED = "error_target_inventory_capacity_exceeded"
    ENTITY_CAPACITY_EXCEEDED = "error_entity_capacity_exceeded"
    INVALID_AMOUNT = "error_invalid_amount"
    TARGET_ALREADY_IN_COMBAT = "error_target_already_in_combat"
    ALREADY_BEING_IN_COMBAT = "error_already_being_in_combat"
    NO_RESOURCE_AVAILABLE = "error_no_resource_available"
    INVALID_OPTION_FOR_NOTIFICATION = "error_invalid_option_for_notification"
    ANIMAL_NOT_TAMABLE = "error_animal_not_tamable"


class Types:
    GANGWAY = "gangway"
    KEY = "key"
    COMBAT = "combat"
    BURIED_HOLE = "buried_hole"
    LAND_TERRAIN = "group_land_terrain"
    WATER_TERRAIN = "group_water_terrain"
    ANY_TERRAIN = "group_any_terrain"
    ACTIVITY = "activity"
    ITEM = "item"  # generic item
    SEA = "sea"
    DOOR = "door"
    INVISIBLE_PASSAGE = "invisible_passage"
    OUTSIDE = "outside"
    ALIVE_CHARACTER = "alive_character"
    DEAD_CHARACTER = "dead_character"
    DEAD_ANIMAL = "dead_animal"
    PORTABLE_ITEM_IN_CONSTRUCTION = "portable_item_in_constr"
    FIXED_ITEM_IN_CONSTRUCTION = "fixed_item_in_constr"


class Events:
    START_UNBOARDING_SHIP = "event_start_unboarding_ship"
    START_BOARDING_SHIP = "event_start_boarding_ship"
    UNBIND_ENTITY_FROM_VEHICLE = "event_unbind_entity_from_vehicle"
    BIND_ENTITY_TO_VEHICLE = "event_bind_entity_to_vehicle"
    PUT_ITEM_INTO_STORAGE = "event_put_item_into_storage"
    TAKE_ITEM_FROM_STORAGE_IN_LOCATION = "event_take_item_from_storage_in_location"
    TAKE_ITEM_FROM_LOCATION = "event_take_item_from_location"
    TAKE_ITEM_FROM_STORAGE = "event_take_item_from_storage"
    STOP_MOVEMENT = "event_stop_movement"
    CHANGE_MOVEMENT_DIRECTION = "event_change_movement_direction"
    START_CONTROLLING_MOVEMENT = "event_start_controlling_movement"
    CHARACTER_DEATH = "event_character_death"
    JOIN_COMBAT = "event_join_combat"
    ATTACK_ENTITY = "event_attack_character"
    OPEN_ENTITY = "event_open_entity"
    CLOSE_ENTITY = "event_close_entity"
    MOVE = "event_move"
    EAT = "event_eat"
    SAY_ALOUD = "event_say_aloud"
    SPEAK_TO_SOMEBODY = "event_speak_to_somebody"
    WHISPER = "event_whisper"
    ADD_TO_ACTIVITY = "event_add_to_activity"
    DROP_ITEM = "event_drop_item"
    TAKE_ITEM = "event_take_item"
    GIVE_ITEM = "event_give_item"
    HIT_TARGET_IN_COMBAT = "event_hit_target_in_combat"
    RETREAT_FROM_COMBAT = "event_retreat_from_combat"
    END_OF_COMBAT = "event_end_of_combat"
    START_TAMING = "event_start_taming"


class PartialEvents:
    """
    List of exact event types which aren't used in standard doer-observer way.
    """
    UNBOARDING_SHIP_OBSERVER = "event_unboarding_ship_observer"
    TAKE_ITEM_FROM_OTHER_LOCATION_OBSERVER = "event_take_item_from_other_location_observer"
    TAKE_ITEM_FROM_STORAGE_FROM_OTHER_LOCATION_OBSERVER = "event_take_item_from_storage_from_other_location_observer"
    BOARDING_SHIP_OBSERVER = "event_boarding_ship_observer"


class Hooks:
    ITEM_DROPPED = "item_dropped"
    LOCATION_ENTERED = "location_entered"
    SPOKEN_ALOUD = "spoken_aloud"
    WHISPERED = "whispered"
    EATEN = "eaten"
    NEW_EVENT = "new_event"
    NEW_CHARACTER_NOTIFICATION = "new_character_notification"
    POSITION_CHANGED = "position_changed"
    NEW_PLAYER_NOTIFICATION = "new_player_notification"
    ENTITY_CONTENTS_COUNT_DECREASED = "entity_contents_count_decreased"
    DAMAGE_EXCEEDED = "damage_exceeded"


class Intents:
    WORK = "work"  # activities and travel
    COMBAT_AUXILIARY_ACTION = "combat_auxiliary_action"
    COMBAT = "combat"


class EqParts:
    SHIELD = "shield"
    HEAD = "head"
    BODY = "body"
    WEAPON = "weapon"


class Modifiers:
    STARVATION = "starvation"
    SCRATCH = "scratch"
    BRUISE = "bruise"


class States:
    MODIFIERS = "modifiers"
    DAMAGE = "damage"
    TIREDNESS = "tiredness"
    HUNGER = "hunger"
    SATIATION = "satiation"
    STRENGTH = "strength"
    DURABILITY = "durability"
    FITNESS = "fitness"
    PERCEPTION = "perception"


NORMALIZED_STATES = (States.DAMAGE, States.TIREDNESS, States.HUNGER, States.SATIATION)


def create_app(database=db, own_config_file_path=""):
    global app

    app = Flask("exeris")
    app.config.from_object("exeris.config.default_config.Config")
    app.config.from_pyfile(own_config_file_path, silent=True)

    logger_config_path = os.path.join(project_root.ROOT_PATH, app.config["LOGGER_CONFIG_PATH"])
    with open(logger_config_path, "r") as config_file:
        logging.config.dictConfig(json.load(config_file))

    database.init_app(app)
    return app


def _cipher(character_id):
    h = hashlib.sha256()
    h.update(app.config['SECRET_KEY'].encode())
    if character_id is None and hasattr(g, "character"):
        character_id = g.character.id
    assert character_id is not None, "encryption key cannot be None"
    h.update(character_id.to_bytes(8, 'big'))
    return AES.new(h.digest(), AES.MODE_ECB)


_encode_token = b'f' * 8


def encode(uid, character_id=None):
    pt = uid.to_bytes(8, 'big') + _encode_token
    return str(int.from_bytes(_cipher(character_id).encrypt(pt), 'big'))


def decode(encoded_id, character_id=None):
    pt = _cipher(character_id).decrypt(int(encoded_id).to_bytes(16, 'big'))
    if pt[8:] != _encode_token:
        raise ValueError('Could not decode ID')
    return int.from_bytes(pt[:8], 'big')


_hooks = {}


def add_hook(name, func):
    if name not in _hooks:
        _hooks[name] = []
    _hooks[name].append(func)


def call_hook(name, **kwargs):
    logger.info("Hook %s for arguments: %s", name, str(kwargs))
    for func in _hooks.get(name, []):
        logger.debug("Calling hook function: %s", func.__name__)
        func(**kwargs)


def hook(name):
    def inner_hook(f):
        add_hook(name, f)  # register hook

    return inner_hook


class GameException(Exception):
    """
    General game exception which can be shown to the user
    """

    def __init__(self, error_tag, **kwargs):
        self.error_tag = error_tag
        self.error_kwargs = kwargs

    def __str__(self):
        return "{}: {} ({})".format(str(self.__class__), self.error_tag, str(self.error_kwargs))


class ItemException(GameException):
    pass


class MalformedInputErrorMixin:
    """Marker class for errors which are most likely caused by a cracking attempt"""


class CharacterException(GameException):
    pass


class PlayerException(GameException):
    pass


class TurningIntoIntentExceptionMixin(Exception):
    """
    This class guarantees that exception class has turn_into_intent method, which creates instance of Intent
        of correct type for a correct (possibly exception-specific) action
    """

    def turn_into_intent(self, entity, action, priority=1):
        raise NotImplementedError("should be implemented in subclass")


class InvalidAmountException(ItemException):
    def __init__(self, *, amount):
        super().__init__(Errors.INVALID_AMOUNT, amount=amount)


class OwnInventoryCapacityExceededException(GameException):
    def __init__(self):
        super().__init__(Errors.OWN_INVENTORY_CAPACITY_EXCEEDED)


class TargetInventoryCapacityExceededException(GameException):
    def __init__(self, target):
        super().__init__(Errors.TARGET_INVENTORY_CAPACITY_EXCEEDED, target=target)


class EntityCapacityExceeded(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_CAPACITY_EXCEEDED, entity=entity)


class CannotAttackYourselfException(GameException):
    def __init__(self):
        super().__init__(Errors.CANNOT_ATTACK_YOURSELF)


class AlreadyBeingInCombat(GameException):
    def __init__(self):
        super().__init__(Errors.ALREADY_BEING_IN_COMBAT)


class TargetAlreadyInCombat(CharacterException):
    def __init__(self, *, entity):
        super().__init__(Errors.TARGET_ALREADY_IN_COMBAT, **entity.pyslatize())


class InvalidTargetException(GameException):
    def __init__(self, *, entity=None):
        if entity:
            super().__init__(Errors.INVALID_TARGET, **entity.pyslatize())
        else:
            super().__init__(Errors.INVALID_TARGET_GENERIC)


class EntityTooFarAwayException(GameException, TurningIntoIntentExceptionMixin):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_TOO_FAR_AWAY, **entity.pyslatize())
        self.entity = entity

    def turn_into_intent(self, executor, action, priority=1):
        from exeris.core import actions
        start_controlling_movement_action = actions.StartControllingMovementAction(executor)
        control_movement_intent = start_controlling_movement_action.perform()
        with control_movement_intent as control_movement_action:
            control_movement_action.travel_action = actions.TravelToEntityAction(control_movement_intent.target,
                                                                                 self.entity)
            control_movement_action.target_action = action

        return control_movement_intent


class EntityNotInInventoryException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_NOT_IN_INVENTORY, **entity.pyslatize())


class EntityUnsupportedOperationException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_UNSUPPORTED_OPERATION, **entity.pyslatize())


class OnlySpecificTypeForGroupException(GameException):
    def __init__(self, *, type_name, group_name):
        params = dict(item_name=type_name, group_name=group_name)  # TODO? PYSLATIZE GROUP?
        super().__init__(Errors.ONLY_SPECIFIC_TYPE_FOR_GROUP, **params)


class ItemNotApplicableForActivityException(GameException):
    def __init__(self, *, item, activity):
        params = dict(item.pyslatize(), **activity.pyslatize())
        super().__init__(Errors.ITEM_NOT_APPLICABLE_FOR_ACTIVITY, **params)


class CannotControlMovementException(GameException):
    def __init__(self):
        super().__init__(Errors.CANNOT_CONTROL_MOVEMENT)


class VehicleAlreadyControlledException(GameException):
    def __init__(self, *, executor):
        super().__init__(Errors.VEHICLE_ALREADY_CONTROLLED, **executor.pyslatize())


class NotControllingMovementException(GameException):
    def __init__(self):
        super().__init__(Errors.NOT_CONTROLLING_MOVEMENT)


class InvalidInitialLocationException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_TOO_FAR_AWAY, **entity.pyslatize())


class ActivityException(GameException):
    pass


class NoInputMaterialException(ActivityException):
    def __init__(self, *, item_type):
        super().__init__(Errors.NO_INPUT_MATERIALS, item_name=item_type.name)


class NoToolForActivityException(ActivityException):
    def __init__(self, *, tool_name):
        super().__init__(Errors.NO_TOOL_FOR_ACTIVITY, tool_name=tool_name)


class NoMachineForActivityException(ActivityException):
    def __init__(self, *, machine_name):
        super().__init__(Errors.NO_MACHINE_FOR_ACTIVITY, machine_name=machine_name)


class NoResourceAvailableException(ActivityException):
    def __init__(self, *, resource_name):
        super().__init__(Errors.NO_RESOURCE_AVAILABLE, resource_name=resource_name)


class TooFarFromActivityException(ActivityException, TurningIntoIntentExceptionMixin):
    def __init__(self, *, activity):
        super().__init__(Errors.TOO_FAR_FROM_ACTIVITY, name_tag=activity.name_tag, name_params=activity.name_params)
        self.activity = activity

    def turn_into_intent(self, executor, action, priority=1):
        from exeris.core import actions
        start_controlling_movement_action = actions.StartControllingMovementAction(executor)
        control_movement_intent = start_controlling_movement_action.perform()
        with control_movement_intent as control_movement_action:
            control_movement_action.travel_action = actions.TravelToEntityAction(control_movement_intent.target,
                                                                                 self.activity)
            control_movement_action.target_action = action

        return control_movement_intent


class ActivityTargetTooFarAwayException(ActivityException):
    def __init__(self, *, entity):
        super().__init__(Errors.ACTIVITY_TARGET_TOO_FAR_AWAY, **entity.pyslatize())


class ActivityAlreadyExistsOnEntity(ActivityException):
    def __init__(self, *, entity):
        super().__init__(Errors.ACTIVITY_ALREADY_EXISITS_ON_ENTITY, **entity.pyslatize())


class TooLowSkillException(ActivityException):
    def __init__(self, *, skill_name, required_level):
        super().__init__(Errors.TOO_LOW_SKILL, skill_name=skill_name, required_level=required_level)


class TooFewParticipantsException(ActivityException):
    def __init__(self, *, min_number):
        super().__init__(Errors.TOO_FEW_PARTICIPANTS_IN_ACTIVITY, min_number=min_number)


class TooManyParticipantsException(ActivityException):
    def __init__(self, *, max_number):
        super().__init__(Errors.TOO_MANY_PARTICIPANTS_IN_ACTIVITY, max_number=max_number)


class InvalidLocationTypeException(ActivityException):
    def __init__(self, *, allowed_types):
        super().__init__(Errors.INVALID_LOCATION_TYPE, allowed_types=allowed_types)


class InvalidTerrainTypeException(ActivityException):
    def __init__(self, *, required_types):
        super().__init__(Errors.INVALID_TERRAIN_TYPE, required_types=required_types)


class TooManyExistingEntitiesException(GameException):
    def __init__(self, *, entity_type):
        super().__init__(Errors.TOO_MANY_EXISTING_ENTITIES, entity_type=entity_type)


class TooCloseToPermanentLocation(GameException):
    def __init__(self):
        super().__init__(Errors.TOO_CLOSE_TO_OTHER_PERMANENT_LOCATION)


class CharacterDeadException(CharacterException):
    def __init__(self, *, character):
        super().__init__(Errors.CHARACTER_DEAD, name=character.name)


class InvalidOptionForNotification(PlayerException, MalformedInputErrorMixin):
    def __init__(self, *, player, option_name):
        super().__init__(Errors.INVALID_OPTION_FOR_NOTIFICATION, player=player, option_name=option_name)


class AnimalNotTamableException(GameException):
    def __init__(self, *, animal):
        super().__init__(Errors.ANIMAL_NOT_TAMABLE, animal=animal)


class CannotEnterLocationException(GameException):
    def __init__(self, *, location):
        super().__init__(Errors.CANNOT_ENTER_LOCATION, location=location)


class EntityMissingPropertyException(GameException):
    def __init__(self, *, entity, property):
        super().__init__(Errors.ENTITY_MISSING_PROPERTY, entity=entity, property=property)


class NoKeyToLockException(GameException):
    def __init__(self, *, entity, lock_id):
        super().__init__(Errors.NO_KEY_TO_LOCK, entity=entity, lock_id=lock_id)


class LockAlreadyExistsException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.LOCK_ALREADY_EXISTS, entity=entity)


class InvalidActivityContainerException(GameException):
    def __init__(self, *, recipe_name_tag, recipe_name_params, activity_container):
        super().__init__(Errors.INVALID_ACTIVITY_CONTAINER, recipe_name_tag=recipe_name_tag,
                         recipe_name_params=recipe_name_params, activity_container=activity_container)


class EntityAlreadyBound(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_ALREADY_BOUND, entity=entity)


class EntityNotBoundException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_NOT_BOUND, entity=entity)


class EntityNotBindableException(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.ENTITY_NOT_BINDABLE, entity=entity)


class CannotUnbindNotLeaf(GameException):
    def __init__(self, *, entity):
        super().__init__(Errors.CANNOT_UNBIND_NOT_LEAF, entity=entity)


class NotTraversableTerrainException(GameException):
    def __init__(self):
        super().__init__(Errors.NOT_TRAVERSABLE_TERRAIN)


class CannotBoardOwnShipException(GameException):
    def __init__(self):
        super().__init__(Errors.CANNOT_BOARD_OWN_SHIP)


class AlreadyBoardedException(GameException):
    def __init__(self, *, ship, boarded_ship):
        super().__init__(Errors.ALREADY_BOARDED, ship=ship.pyslatize(), boarded_ship=boarded_ship.pyslatize())


class CannotUnboardFromOwnShipException(GameException):
    def __init__(self):
        super().__init__(Errors.CANNOT_UNBOARD_FROM_OWN_SHIP)


class ShipNotBoardedException(GameException):
    def __init__(self, *, ship, ship_to_unboard):
        super().__init__(Errors.SHIP_NOT_BOARDED, ship=ship.pyslatize(), ship_to_unboard=ship_to_unboard.pyslatize())


class InvalidShipTypeForBoardingException(GameException):
    def __init__(self, *, own_ship, boarded_type_name):
        super().__init__(Errors.INVALID_SHIP_TYPE_FOR_BOARDING, own_ship=own_ship.pyslatize(),
                         boarded_type=boarded_type_name)
