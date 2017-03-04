import {
  getDynamicName,
  fromDynamicNamesState,
  updateDynamicName,
  dynamicNamesReducer
} from "../../src/modules/dynamicNames";
import * as Immutable from "immutable";


describe('(dynamicNames) dynamicNames reducer', () => {

  it('Should initialize with initial state.', () => {
    expect(dynamicNamesReducer(undefined, {})).to.equal(Immutable.Map());
  });

  it('Should return the previous state if an action was not matched.', () => {
    const previousState = Immutable.fromJS({
      "ABC": "John",
      "DEF": "Emma",
    });
    let state = dynamicNamesReducer(previousState, {});
    expect(state).to.equal(previousState);
  });

  it('Should add or update the dynamic name when a new one is supplied.', () => {
    const previousState = Immutable.fromJS({
      "ABC": "John",
    });
    let state = dynamicNamesReducer(previousState, updateDynamicName(0, "ZET", "Tommy"));
    expect(state).to.equal(state.set("ZET", "Tommy"));
    state = dynamicNamesReducer(state, updateDynamicName(0, "ZET", "Jimmy"));
    expect(state).to.equal(state.set("ZET", "Jimmy"));
  });
});
