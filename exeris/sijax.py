from flask import g, render_template
from shapely.geometry import Point
import time
from exeris.core import models, general, actions
from exeris.core.main import db

__author__ = 'alek'


class GlobalMixin:
        @staticmethod
        def rename_entity(obj_response, character_id, new_name):
            entity_to_rename = models.Entity.by_id(character_id)
            entity_to_rename.set_dynamic_name(g.character, new_name)
            db.session.commit()

            obj_response.call("$.publish", ["refresh_entity", character_id])

        @staticmethod
        def get_entity_tag(obj_response, entity_id):
            entity = models.Entity.by_id(entity_id)
            text = g.pyslate.t("entity_info", html=True, **entity.pyslatize())

            obj_response.call("FRAGMENTS.global.after_get_entity_tag", [entity_id, text])


class PlayerPage:

        @staticmethod
        def create_character(obj_response, char_name):

            loc = models.RootLocation.query.one()
            new_char = models.Character(char_name, models.Character.SEX_FEMALE, g.player, "en",
                                        general.GameDate.now(), Point(1, 1), loc)
            db.session.add(new_char)
            db.session.commit()

            obj_response.call("FRAGMENTS.player.after_create_character", [])


class EventsPage(GlobalMixin):

        @staticmethod
        def get_new_events(obj_response, last_event):
            start = time.time()
            events = db.session.query(models.Event).join(models.EventObserver).filter_by(observer=g.character)\
                .filter(models.Event.id > last_event).order_by(models.Event.id.asc()).all()

            queried = time.time()
            print("query: ", queried - start)
            last_event_id = events[-1].id if len(events) else last_event
            events_texts = [g.pyslate.t(event.type_name, html=True, **event.params) for event in events]

            tran = time.time()
            print("translations:", tran - queried)
            events_texts = [event for event in events_texts]
            all = time.time()
            print("esc: ", all - tran)
            obj_response.call("FRAGMENTS.events.update_list", [events_texts, last_event_id])

        @staticmethod
        def say_aloud(obj_response, message):

            action = actions.SayAloudAction(g.character, message)
            action.perform()

            db.session.commit()
            obj_response.call("FRAGMENTS.speaking.after_say_aloud", [])

        @staticmethod
        def say_to_somebody(obj_response, receiver_id, message):
            receiver = models.Character.by_id(receiver_id)

            action = actions.SpeakToSomebody(g.character, receiver, message)
            action.perform()

            db.session.commit()
            obj_response.call("FRAGMENTS.speaking.after_say_to_somebody", [])

        @staticmethod
        def whisper(obj_response, receiver_id, message):
            receiver = models.Character.by_id(receiver_id)

            action = actions.WhisperToSomebody(g.character, receiver, message)
            action.perform()

            db.session.commit()
            obj_response.call("FRAGMENTS.speaking.after_whisper", [])

        @staticmethod
        def people_short_refresh_list(obj_response):
            chars = models.Character.query.all()
            rendered = render_template("events/people_short.html", chars=chars)

            obj_response.call("FRAGMENTS.people_short.after_refresh_list", [rendered])

        @staticmethod
        def speaking_form_refresh(obj_response, message_type, receiver=None):

            if receiver:
                receiver = models.Character.by_id(receiver)

            rendered = render_template("events/speaking.html", message_type=message_type, receiver=receiver)

            obj_response.call("FRAGMENTS.speaking.after_speaking_form_refresh", [rendered])