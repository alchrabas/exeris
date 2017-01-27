import {playerReducer} from "../modules/player";
import {combineReducers} from "redux-immutable";
import {decoratedEventsReducer} from "../modules/events";
import {decoratedCharactersAroundReducer} from "../modules/charactersAround";
import {decoratedSpeechReducer} from "../modules/speech";
import {decoratedTopPanelReducer} from "../modules/topPanel";
import {decoratedEntitiesReducer} from "../modules/entities";
import {notificationsReducer} from "../modules/notifications";
import {decoratedRecipesReducer} from "../modules/recipes";
import {reducer as formReducer} from "redux-form/immutable";


const mainReducer = combineReducers({
  player: playerReducer,
  events: decoratedEventsReducer,
  charactersAround: decoratedCharactersAroundReducer,
  speech: decoratedSpeechReducer,
  topPanel: decoratedTopPanelReducer,
  entities: decoratedEntitiesReducer,
  notifications: notificationsReducer,
  recipes: decoratedRecipesReducer,
  form: formReducer,
});

export default mainReducer;
