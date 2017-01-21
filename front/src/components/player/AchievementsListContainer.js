import {connect} from "react-redux";
import {requestAchievementsList, getAchievementsList, fromPlayerState} from "../../modules/player";
import AchievementsList from "./AchievementsList";

const mapStateToProps = (state) => {
  return {achievements: getAchievementsList(fromPlayerState(state))};
};

const mapDispatchToProps = (dispatch) => {
  return {
    onMount: () => dispatch(requestAchievementsList()),
  }
};

const AchievementsListContainer = connect(
  mapStateToProps,
  mapDispatchToProps
)(AchievementsList);

export default AchievementsListContainer;