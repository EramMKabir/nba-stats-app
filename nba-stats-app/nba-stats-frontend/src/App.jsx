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

import { BrowserRouter as Router, Routes, Route, Link } from "react-router";
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
import arrayReducer, { setTeamsArray, setPlayersArray, setPlayerNamesArray, setTeamAbbreviationsArray } from "./reducers/arrayReducer";
import numberReducer, { setSeed, setTeamPoints, setOppTeamPoints } from "./reducers/numberReducer";
import { AuthProvider } from "./context/authContext";
import { useEffect } from "react";
import { useAuth } from "./context/authContext";
import playersStatsService from "./services/playerstats";
import upcomingGameTeamsService from "./services/upcominggameteams";
import playerNamesService from "./services/playernames";
import teamAbbreviationsService from "./services/teamabbreviations";
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
  const playerNamesArray = useSelector((state) => state.arrayReducer.playerNamesArray);
  const teamAbbreviationsArray = useSelector((state) => state.arrayReducer.teamAbbreviationsArray);
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
      const playerNames = await playerNamesService.playerNames(token);
      const teamAbbreviations = await teamAbbreviationsService.teamAbbreviations(token);
      dispatch(setTeamsArray(teamsArr));
      dispatch(setPlayersArray(playersArr));
      dispatch(setPlayerNamesArray(playerNames));
      dispatch(setTeamAbbreviationsArray(teamAbbreviations));
    };
    if (token) {
      setPlayersAndTeams(); /* Run function to get teams and players (or lack thereof). */
    };
  }, [token, dispatch]);

  const { setToken } = useAuth(); /* Context variable for setting token */

  /*
  Conditional display variables for displaying components during different states  
  */

  const titleDisplay = !helpDisplay && !loadingLogout && !playerStats && !teamStats && upcomingGamesStats;
  const mainPageDisplay = !helpDisplay && user && !playerStats && !teamStats && upcomingGamesStats;
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
    window.scrollTo(0, 0)
  };

  /* Remove Stat functions */

  const removePlayerStats = () => {
    dispatch(setPlayerStats(false));
    const emptyDictionary = {};
    dispatch(setPlayerStatsDictionary(emptyDictionary));
    dispatch(setPlayerName(''));
    window.scrollTo(0, 0);
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
    window.scrollTo(0, 0);
  };

  /*
  This function switches between the
  main page and the Help tab. 
  */

  const switchBetweenMainAndHelp = (value) => {
    window.scrollTo(0, 0);
    dispatch(setHelpDisplay(value));
  }

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
    if (!opposingTeam) {
      opposingTeam = "";
    }
    const newDictionary = await calculatedPlayerStatsService.calculatedPlayerStats({
      playerFullName,
      season,
      seasonType,
      opposingTeam,
      recentGames
    }, token);
    const timeoutDuration = 2000;
    window.scrollTo(0, 0);
    if (typeof newDictionary === "object") {
      dispatch(setSuccessMessage("Data collected successfully!"));
      setTimeout(() => {
        dispatch(setSuccessMessage(null));
      }, timeoutDuration);
      dispatch(setPlayerStats(true));
      dispatch(setPlayerStatsDictionary(newDictionary));
      dispatch(setPlayerName(playerFullName));
    } else if (newDictionary === 2) {
      dispatch(setErrorMessage("This player currently does not have any game data."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    } else if (newDictionary === 3) {
      dispatch(setErrorMessage("Please enter a valid season for the player."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    } else if (newDictionary === 4) {
      dispatch(setErrorMessage("This player has not played against the entered team. \
                                Change either team or leave the field blank for no opposing team projections."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    };
  };

  const getMatchupStats = async (team, season, seasonType, opposingTeam, recentGames, context = {}) => {
    if (!opposingTeam) {
      opposingTeam = "";
    }
    const newDictionary = await calculatedMatchupStatsService.calculatedMatchupStats({
      team,
      season,
      seasonType,
      opposingTeam,
      recentGames,
      ...(context.gameDate ? { gameDate: context.gameDate } : {}),
      venue: context.venue || "auto"
    }, token);
    const timeoutDuration = 2000;
    window.scrollTo(0, 0);
    if (typeof newDictionary.matchup_stats === "object" && typeof newDictionary.ratio_stats === "object") {
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
    } else if (newDictionary.matchup_stats === 2) {
      dispatch(setErrorMessage("This team currently does not have any game data."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    } else if (newDictionary.matchup_stats === 3 || newDictionary.ratio_stats === 3) {
      dispatch(setErrorMessage("Please enter a valid season."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    } else if (newDictionary.matchup_stats === 4 || newDictionary.ratio_stats === 4) {
      dispatch(setErrorMessage("This team has not played against the entered team. \
                                  Change either team or leave the field blank for no opposing team projections."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    } else if (newDictionary.matchup_stats === 5 || newDictionary.ratio_stats === 5) {
      dispatch(setErrorMessage("Please enter a year for the game date matching the season year."));
      setTimeout(() => {
        dispatch(setErrorMessage(null));
      }, timeoutDuration);
    };
  };

  /* Entire app is described below */
  /* 
     Return a stable element tree; defining a component here remounts the form
     whenever App updates (including when a notification expires). 
  */
  const renderHome = () => {
    return (
      <div className="home-content">
        {titleDisplay && (
          <section className="hero-panel" aria-labelledby="hero-title">
            <div className="hero-copy">
              <div className="eyebrow"><span className="live-dot" /> NBA projection engine</div>
              <h1 id="hero-title">See the game<br /><span>before the whistle.</span></h1>
              <p>
                Turn historical performance, recent form, and matchup context
                into a sharper view of what happens next.
              </p>
              <div className="signal-row" aria-label="Available analysis modes">
                <span>Player form</span>
                <span>Matchup model</span>
                <span>Upcoming slate</span>
              </div>
            </div>
            <div className="hero-visual" aria-hidden="true">
              <div className="court-orbit court-orbit-one" />
              <div className="court-orbit court-orbit-two" />
              <div className="court-core">
                <span>CV</span>
                <small>PROJECTION<br />SYSTEM</small>
              </div>
              <div className="metric-float metric-float-one"><b>+8.4</b><span>FORM</span></div>
              <div className="metric-float metric-float-two"><b>62%</b><span>EDGE</span></div>
            </div>
          </section>
        )}

        {mainPageDisplay && (
          <section className="workspace-shell">
            <Inputs
              getPlayerStats={getPlayerStats}
              getMatchupStats={getMatchupStats}
              playerNamesArray={playerNamesArray}
              teamAbbreviationsArray={teamAbbreviationsArray}
            />
            <div className="workspace-footer">
              <button className="text-action" onClick={() => switchBetweenMainAndHelp(true)}>
                How it works <span aria-hidden="true">↗</span>
              </button>
              <button onClick={removeUser} className="text-action logout">
                Log out
              </button>
            </div>
          </section>
        )}

        {helpPageDisplay && (
          <section className="content-panel help-panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Field guide</div>
                <h1>How CourtVision works</h1>
              </div>
              <button className="secondary-action" onClick={() => switchBetweenMainAndHelp(false)}>
                ← Return to projections
              </button>
            </div>
            <Help />
          </section>
        )}

        {statsPageDisplay && (
          <section className="content-panel results-panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Player projection</div>
                <h1>{playerName}</h1>
              </div>
              <button className="secondary-action" onClick={removePlayerStats}>
                ← New projection
              </button>
            </div>
            <IndividualPlayerStatsDictionaryDisplay statsDictionary={playerStatsDictionary} />
          </section>
        )}

        {OAuthDisplay && (
          <section className="login-panel">
            <div>
              <div className="eyebrow">Your private workspace</div>
              <h2>Enter the control room.</h2>
              <p>Sign in to access live player data and matchup projections.</p>
            </div>
            <OAuthLogin />
            <OAuthCallback />
            <small>Secure access · Session protected</small>
          </section>
        )}

        {teamStatsPageDisplay && (
          <section className="content-panel results-panel matchup-results">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Matchup projection</div>
                <h1>Game intelligence</h1>
              </div>
              <button className="secondary-action" onClick={removeTeamStats}>
                ← New projection
              </button>
            </div>
            <RatioDictionaryDisplay
              ratioDict={ratioDict}
              teamStatsDictionary={teamStatsDictionary}
              teamPoints={teamPoints}
              oppTeamPoints={oppTeamPoints}
            />
            <NBATeamsAndPlayersCalculatedStatsDisplay
              teamStatsDictionary={teamStatsDictionary}
              lastGameStatsDictionary={lastGameStatsDictionary}
              injuredPlayersDictionary={injuredPlayersDictionary}
            />
          </section>
        )}
      </div>
    );
  };

  return (
    <div className="main-container">
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="scan-grid" aria-hidden="true" />
      <Router>
        <header className="app-header">
          <Link className="brand" to="/" aria-label="CourtVision home">
            <span className="brand-mark"><i /></span>
            <span className="brand-name">COURT<span>VISION</span></span>
          </Link>
          <nav className="app-nav" aria-label="Primary navigation">
            {mainPageDisplay && (
              <Link className="nav-link" to="/upcoming-games" onClick={goToUpcomingGames}>
                Upcoming games <span aria-hidden="true">↗</span>
              </Link>
            )}
            <div className="system-status"><span /> System live</div>
          </nav>
        </header>
        <main className="app-main">
          <div className="toast-region" aria-live="polite">
            <Success message={successMessage} />
            <Error message={errorMessage} />
          </div>
          <Routes>
            <Route path='/' element={renderHome()}></Route>
            <Route path="/upcoming-games" element={<NBATeamsAndPlayersStatsDisplay seed={seed} teamsArray={teamsArray} playersArray={playersArray} />}></Route>
          </Routes>
        </main>
        <footer className="app-footer">
          <span>COURTVISION / PROJECTION SYSTEM</span>
          <span>Data-driven. Game ready.</span>
        </footer>
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