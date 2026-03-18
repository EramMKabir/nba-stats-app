/*

App.jsx

Function: It is the entire website.

Inputs:

None.

Output:

None.

Time complexity: O(n), where n is the number of nodes in the DOM.

Space complexity: O(n)

###################################################################################
# Date modified              Modifier             What was modified               #
# 03/16/2025                 Eram Kabir           Initial Development             #
# 01/11/2026                 Eram Kabir           Final Development               #
###################################################################################

*/

/* Libraries and Functions */

import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import { configureStore } from "@reduxjs/toolkit";
import { useSelector, useDispatch, Provider } from "react-redux";
import Inputs from "./components/Inputs";
import OAuthLogin from "./components/OAuthLogin";
import OAuthCallback from "./components/OAuthCallback";
import Error from "./components/Error";
import Success from "./components/Success";
import IndividualPlayerStatsDictionaryDisplay from "./components/IndividualPlayerStatsDictionaryDisplay";
import NBATeamsAndPlayersStatsDisplay from "./components/NBATeamsAndPlayersStatsDisplay";
import NBATeamsAndPlayersCalculatedStatsDisplay from "./components/NBATeamsAndPlayersCalculatedStatsDisplay";
import RatioDictionaryDisplay from "./components/RatioDictionaryDisplay";
import Help from "./components/Help";
import calculatedPlayerStatsService from "./services/calculatedplayerstats";
import calculatedMatchupStatsService from "./services/calculatedmatchupstats";
import booleanReducer, { setPlayerStats, setTeamStats, setHelpDisplay, setUpcomingGamesStats } from "./reducers/booleanReducer";
import dictReducer, { setPlayerStatsDictionary, setTeamStatsDictionary, setRatioDictionary, setLastGameStatsDictionary, setInjuredPlayersDictionary } from "./reducers/dictReducer";
import nullReducer, { setUser, setSuccessMessage, setErrorMessage } from "./reducers/nullReducer";
import stringReducer, { setPlayerName } from "./reducers/stringReducer";
import arrayReducer, { setTeamsArray, setPlayersArray } from "./reducers/arrayReducer";
import numberReducer, { setSeed, setTeamPoints, setOppTeamPoints } from "./reducers/numberReducer";
import { AuthProvider } from "./context/authContext";
import React, { useEffect } from "react";
import { useAuth } from "./context/authContext";
import playersStatsService from "./services/playerstats";
import upcomingGameTeamsService from "./services/upcominggameteams";
import "./App.css";

function App() {

  /* 
  All state variables
  */
  const user = useSelector((state) => state.nullReducer.user);
  const successMessage = useSelector((state) => state.nullReducer.successMessage);
  const errorMessage = useSelector((state) => state.nullReducer.errorMessage);
  const playerStats = useSelector((state) => state.booleanReducer.playerStats);
  const playerStatsDictionary = useSelector((state) => state.dictReducer.playerStatsDictionary);
  const teamStats = useSelector((state) => state.booleanReducer.teamStats);
  const teamStatsDictionary = useSelector((state) => state.dictReducer.teamStatsDictionary);
  const playerName = useSelector((state) => state.stringReducer.playerName);
  const ratioDict = useSelector((state) => state.dictReducer.ratioDictionary);
  const seed = useSelector((state) => state.numberReducer.seed);
  const loadingLogout = useSelector((state) => state.booleanReducer.loadingLogout);
  const teamsArray = useSelector((state) => state.arrayReducer.teamsArray);
  const playersArray = useSelector((state) => state.arrayReducer.playersArray);
  const token = useSelector((state) => state.nullReducer.token);
  const lastGameStatsDictionary = useSelector((state) => state.dictReducer.lastGameStatsDictionary);
  const injuredPlayersDictionary = useSelector((state) => state.dictReducer.injuredPlayersDictionary);
  const helpDisplay = useSelector((state) => state.booleanReducer.helpDisplay);
  const teamPoints = useSelector((state) => state.numberReducer.teamPoints);
  const oppTeamPoints = useSelector((state) => state.numberReducer.oppTeamPoints);
  const upcomingGamesStats = useSelector((state) => state.booleanReducer.upcomingGamesStats)

  const dispatch = useDispatch(); /* State changer from Redux */

  /* Load players and teams for Inputs component */
  useEffect(() => {
    const setPlayersAndTeams = async () => {
      const teamsArr = await upcomingGameTeamsService.upcomingGameTeams(token);
      const playersArr = await playersStatsService.playerStats(token);
      dispatch(setTeamsArray(teamsArr));
      dispatch(setPlayersArray(playersArr));
    };
    if (token){
      setPlayersAndTeams(); /* Run function to get teams and players (or lack thereof). */
    };
  }, [token]);

  const { setToken } = useAuth(); /* Context variable for setting token */

  /*
  Conditional display variables for displaying components during different states  
  */

  const titleDisplay = !helpDisplay && !loadingLogout && !playerStats && !teamStats;
  const mainPageDisplay = !helpDisplay && user && !playerStats && !teamStats;
  const upcomingGamesStatsDisplay = !helpDisplay && user && !playerStats && !teamStats && upcomingGamesStats;
  const helpPageDisplay = helpDisplay && user && !playerStats && !teamStats;
  const statsPageDisplay = !helpDisplay && user && playerStats;
  const teamStatsPageDisplay = !helpDisplay && user && teamStats;
  const OAuthDisplay = !helpDisplay && !user && !loadingLogout;

  /* 
  RemoveUser removes the user and sets all
  relevant states to default values 
  */

  const removeUser = async () => {
    setToken(null);
    dispatch(setUser(null));
    dispatch(setPlayerStats(false));
    const emptyDictionary = {};
    dispatch(setPlayerStatsDictionary(emptyDictionary));
    dispatch(setPlayerName(''));
    dispatch(setTeamStats(false));
    dispatch(setTeamStatsDictionary(emptyDictionary));
    dispatch(setRatioDictionary(emptyDictionary));
    dispatch(setLastGameStatsDictionary(emptyDictionary));
    dispatch(setInjuredPlayersDictionary(emptyDictionary));
    dispatch(setTeamPoints(0));
    dispatch(setOppTeamPoints(0));
    dispatch(setHelpDisplay(false));
  };

  /* Remove Stat functions */

  const removePlayerStats = () => {
    dispatch(setPlayerStats(false));
    const emptyDictionary = {};
    dispatch(setPlayerStatsDictionary(emptyDictionary));
    dispatch(setPlayerName(''));
  };

  const removeTeamStats = () => {
    dispatch(setTeamStats(false));
    const emptyDictionary = {};
    dispatch(setTeamStatsDictionary(emptyDictionary));
    dispatch(setRatioDictionary(emptyDictionary));
    dispatch(setLastGameStatsDictionary(emptyDictionary));
    dispatch(setInjuredPlayersDictionary(emptyDictionary));
    dispatch(setTeamPoints(0));
    dispatch(setOppTeamPoints(0));
  };

  /* 
  The following function sets the screen
  focus to the top and refreshes the seed
  for the upcoming games page when the user clicks
  the link to the page. This is done for
  better user experience and to ensure that the
  upcoming games page is not stuck on old data.
  */

  const goToUpcomingGames = () => {
    window.scrollTo(0, 0);
    dispatch(setSeed(Math.random()));
    dispatch(setUpcomingGamesStats(false))
  };

  /* The following two functions get stats and populate them into the DOM */

  const getPlayerStats = async (playerFullName, season, seasonType, opposingTeam, recentGames) => {
    const newDictionary = await calculatedPlayerStatsService.calculatedPlayerStats({playerFullName, 
                                             season, 
                                             seasonType, 
                                             opposingTeam, 
                                             recentGames}, token);
    const timeoutDuration = 2000;
    window.scrollTo(0, 0)
    if (typeof newDictionary === "object"){
      dispatch(setSuccessMessage("Data collected successfully!"));
      setTimeout(() => {
        dispatch(setSuccessMessage(null));
        }, timeoutDuration);
      dispatch(setPlayerStats(true));
      dispatch(setPlayerStatsDictionary(newDictionary));
      dispatch(setPlayerName(playerFullName));
    } else if (newDictionary === 2){
      dispatch(setErrorMessage("This player currently does not have any game data."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
        }, timeoutDuration);
    } else if (newDictionary === 3){
      dispatch(setErrorMessage("Please enter a valid season for the player."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
        }, timeoutDuration);
    } else if (newDictionary === 4){
      dispatch(setErrorMessage("This player has not played against the entered team.\
                                Change either team or leave the field blank for no opposing team projections."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
          }, timeoutDuration);
      };
  };

  const getMatchupStats = async (team, season, seasonType, opposingTeam, recentGames) => {
      const newDictionary = await calculatedMatchupStatsService.calculatedMatchupStats({team,
                                                                                season,
                                                                                seasonType, 
                                                                                opposingTeam,
                                                                                recentGames}, token);
      const timeoutDuration = 2000;
      window.scrollTo(0, 0)
      if (typeof newDictionary.matchup_stats === "object" && typeof newDictionary.ratio_stats === "object"){
        dispatch(setSuccessMessage("Data collected successfully!"));
        setTimeout(() => {
          dispatch(setSuccessMessage(null));
          }, timeoutDuration);
        dispatch(setTeamStats(true));
        dispatch(setTeamStatsDictionary(newDictionary.matchup_stats));
        dispatch(setRatioDictionary(newDictionary.ratio_stats));
        dispatch(setLastGameStatsDictionary(newDictionary.last_game_stats));
        dispatch(setInjuredPlayersDictionary(newDictionary.injured_nba_players));
        dispatch(setTeamPoints(newDictionary.team_points));
        dispatch(setOppTeamPoints(newDictionary.opposing_team_points));
      } else if (newDictionary.matchup_stats === 2){
        dispatch(setErrorMessage("This player currently does not have any game data."));
        setTimeout(() => {
          dispatch(setErrorMessage(null));
          }, timeoutDuration);
      } else if (newDictionary.matchup_stats === 3 || newDictionary.ratio_stats === 3){
        dispatch(setErrorMessage("Please enter a valid season."));
        setTimeout(() => {
          dispatch(setErrorMessage(null));
          }, timeoutDuration);
      } else if (newDictionary.matchup_stats === 4 || newDictionary.ratio_stats === 4){
        dispatch(setErrorMessage("This team has not played against the entered team.\
                                  Change either team or leave the field blank for no opposing team projections."));
        setTimeout(() => {
          dispatch(setErrorMessage(null));
          }, timeoutDuration);
      };
  };
  
  /* Entire app is described below */
  const Home = () => {
    return (
      <div>
        {titleDisplay && <h1>
                          <span>
                            NBA Projected Stat Calculator
                          </span>
                        </h1>}
        
        {mainPageDisplay && <Inputs 
                            getPlayerStats={getPlayerStats} 
                            getMatchupStats={getMatchupStats}
                            />}
        
        {mainPageDisplay && <React.Fragment>
                              <br />
                                <button onClick={() => dispatch(setHelpDisplay(true))}>
                                  Help
                                </button>
                              <br />
                            </React.Fragment>}
        
        {mainPageDisplay && <React.Fragment>
                              <br/>
                                <button 
                                onClick={removeUser} 
                                className="logout">
                                  Log Out
                                </button>
                            </React.Fragment>}
        
        {helpPageDisplay && <Help />}
        
        {helpPageDisplay && <button 
                            onClick={() => dispatch(setHelpDisplay(false))}>
                              Return to Inputs
                            </button>}
        
        {statsPageDisplay && <h1>{playerName}</h1>}
        
        {statsPageDisplay && <IndividualPlayerStatsDictionaryDisplay 
                              statsDictionary = {playerStatsDictionary} 
                              />}
        
        {statsPageDisplay && <React.Fragment>
                               <br/>
                                 <button 
                                 onClick={removePlayerStats}>
                                  Return to Inputs
                                 </button>
                             </React.Fragment>}
        
        {OAuthDisplay && <React.Fragment>
                           <OAuthLogin />
                           <OAuthCallback />
                         </React.Fragment>}
        
        {teamStatsPageDisplay && <RatioDictionaryDisplay 
                                  ratioDict={ratioDict} 
                                  teamStatsDictionary={teamStatsDictionary} 
                                  teamPoints={teamPoints} 
                                  oppTeamPoints={oppTeamPoints}/>}
        
        {teamStatsPageDisplay && <NBATeamsAndPlayersCalculatedStatsDisplay 
                                  teamStatsDictionary={teamStatsDictionary} 
                                  lastGameStatsDictionary={lastGameStatsDictionary} 
                                  injuredPlayersDictionary={injuredPlayersDictionary}/>}
        
        {teamStatsPageDisplay && <React.Fragment>
                                   <br/>
                                     <button 
                                     onClick={removeTeamStats}>
                                       Return to Inputs
                                     </button>
                                 </React.Fragment>}
      </div>
    );
  };

  return (
    <div className="main-container">
      <Router>
        {upcomingGamesStatsDisplay && <nav className="topleft">
                              <Link 
                              to="/upcoming-games" 
                              onClick={goToUpcomingGames}>
                                Upcoming Games
                              </Link>
                            </nav>}
        <Success message={successMessage} />
        <Error message={errorMessage} />
        <Routes>
          <Route path='/' element = {<Home />}></Route>
          <Route path="/upcoming-games" element={<NBATeamsAndPlayersStatsDisplay seed={seed} teamsArray={teamsArray} playersArray={playersArray} />}></Route>
        </Routes>
      </Router>
    </div>
  );
};

const store = configureStore({
    reducer: {
      booleanReducer: booleanReducer,
      dictReducer: dictReducer,
      nullReducer: nullReducer,
      stringReducer: stringReducer,
      arrayReducer: arrayReducer,
      numberReducer: numberReducer
    }
  });

const AppWrapper = () => {

  return (
    <Provider store={store}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </Provider>
  );
};

export default AppWrapper;