/*

NBATeamsAndPlayersStatsDisplay.jsx

Function: To display NBA Teams and Players Stats from the NBA API.

Inputs:

seed: A variable with a random value, used to refresh component upon
navigation to it.

teamsArray: An array of team abbreviations.

playersArray: An array of players and their stats.

Output:

HTML Text that displays Team Names and Player Stats of upcoming NBA games.

Time complexity: O(n*m), where n and m are the total players on a team 
                 and the number of stats, respectively.

Space complexity: O(n*m)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 06/18/2025                 Eram Kabir           Finalized V1.0                #
# 01/10/2026                 Eram Kabir           Added more comments           #
#################################################################################

*/

/* Libraries and Functions */

import { setNoPlayersOrTeams, setPlayerStats } from "../reducers/booleanReducer";
import { useSelector, useDispatch } from "react-redux";
import { useNavigate } from "react-router-dom";
import { useMediaQuery } from "react-responsive";
import React from "react";

const NBATeamsAndPlayersStatsDisplay = ({seed, teamsArray, playersArray}) => {

    /* 

       seed: A variable used to refresh this component. Seed will be
             changed in the App.jsx file upon clicking of the
             "Upcoming Games" link, thereby refreshing this
             component. Occurs every time the link is clicked.

       Set state variables:

       teamsArray: An array of dictionaries containing matchups for upcoming 
                   NBA games. Default value is null.

       Ex: [
             {first_team_abbreviation: 'IND', second_team_abbreviation: 'OKC'}
           ]

       playersArray: An array of dictionaries containing data for players in 
                     upcoming NBA games. Default value is null.

       Ex: [
             {assists: "1.2", blocks: "0.4", defensive_rebounds: "3.1", 
             field_goal_threes_attempted: "4.3", field_goal_threes_made: "1.9",
             field_goal_threes_percentage: "0.0", field_goals_attempted: "8.4",
             field_goals_made: "4.3", field_goals_percentage: "0.0",
             free_throws_attempted: "1.8", free_throws_made: "1.6",
             free_throws_percentage: "0.0", minutes: "24.9",
             offensive_rebounds: "0.8", personal_fouls: "2.5",
             player_name: "Aaron Nesmith", plus_minus: "4.4", points: "12.0",
             rebounds: "4.0", steals: "0.8", team_abbreviation: "IND",
             turnovers: "0.8"},

             {assists: "5.0", blocks: "0.2", defensive_rebounds: "2.8", 
             field_goal_threes_attempted: "2.7", field_goal_threes_made: "0.8",
             field_goal_threes_percentage: "0.0", field_goals_attempted: "8.3",
             field_goals_made: "3.8", field_goals_percentage: "0.0",
             free_throws_attempted: "2.1", free_throws_made: "1.7",
             free_throws_percentage: "0.0", minutes: "28.9",
             offensive_rebounds: "0.5", personal_fouls: "2.3",
             player_name: "Andrew Nembhard", plus_minus: "2.6", points: "10.0",
             rebounds: "3.3", steals: "1.2", team_abbreviation: "IND",
             turnovers: "1.7"}
           ]

       noPlayersOrTeams: A boolean variable used display upcoming game info OR 
                         the "No teams were found" HTML Text and the Go Back 
                         HTML Button, based on whether or not upcoming games 
                         were found.

       isDesktopOrLaptop: A boolean variable used to determine if the
                          screen size is desktop/laptop or mobile, to
                          display the HTML Table accordingly.
    */

    /*
    All states are managed using
    Redux, and all the reducers
    for the states are managed in
    the reducers directory.
    */

    const noPlayersOrTeams = useSelector((state) => state.booleanReducer.noPlayersOrTeams);

    const dispatch = useDispatch(); /* Used to change state to specified value. */

    const navigate = useNavigate(); /* Navigation hook. */

    const isDesktopOrLaptop = useMediaQuery({ minWidth: 601 });

    /* Function to navigate to home tab. */
    const navToHome = () => {
      dispatch(setPlayerStats(false))
      navigate('/');
    };

    /* 
       If there are no teams or players, return an HTML 
       element stating no games were found, and include a Go Back HTML button,
       by changing the noPlayersOrTeams state variable.
    */

    if (teamsArray.length === 0 || playersArray.length === 0){
      dispatch(setNoPlayersOrTeams(true));
    };
        
    /* Return null if teamsArray has no data or playersArray has no data. */

    /* CSS styles for the stats table */
    const cssStyleString = "table { font-family: arial, sans-serif;border-collapse: collapse; width: 100%; } \
                            td, th { border: 1px solid #dddddd; text-align: left; padding: 8px; }";
    
    /* Ordered list of headers for the stats display */
    const orderedHeaders = ["TEAM", 
                            "PLAYER", 
                            "MIN", 
                            "PTS", 
                            "FGM", 
                            "FGA", 
                            "FG_PCT", 
                            "FG3M", 
                            "FG3A", 
                            "FG3_PCT", 
                            "FTM", 
                            "FTA", 
                            "FT_PCT", 
                            "OREB", 
                            "DREB", 
                            "REB", 
                            "AST", 
                            "TOV", 
                            "STL", 
                            "BLK", 
                            "PF", 
                            "PLUS_MINUS"];

    /* Mapping from display headers to player object properties */
    const mappedHeaders = {"TEAM": "team_abbreviation", 
                           "PLAYER": "player_name", 
                           "MIN": "minutes", 
                           "PTS": "points", 
                           "FGM": "field_goals_made", 
                           "FGA": "field_goals_attempted", 
                           "FG_PCT": "field_goals_percentage", 
                           "FG3M": "field_goal_threes_made", 
                           "FG3A": "field_goal_threes_attempted", 
                           "FG3_PCT": "field_goal_threes_percentage", 
                           "FTM": "free_throws_made", 
                           "FTA": "free_throws_attempted", 
                           "FT_PCT": "free_throws_percentage", 
                           "OREB": "offensive_rebounds", 
                           "DREB": "defensive_rebounds", 
                           "REB": "rebounds", 
                           "AST": "assists", 
                           "TOV": "turnovers", 
                           "STL": "steals", 
                           "BLK": "blocks", 
                           "PF": "personal_fouls", 
                           "PLUS_MINUS": "plus_minus"};

    /* Prepare array of players with headers for mobile display, sorted by points descending */
    /* Headers are stat name, followed by stat value */
    const headersPlusPlayersArray = playersArray ? [...playersArray].sort((player, secondPlayer) => secondPlayer.points - player.points).map((player) => {
      const playerWithHeaders = [];
      orderedHeaders.forEach((header) => {
        playerWithHeaders.push(`${header}: ${player[mappedHeaders[header]]}`);
      });
      return playerWithHeaders;
    }) : [];

    /*
    Basically, the following code
    creates two different views for 
    the stats display: one for mobile 
    and one for desktop/laptop. 

    Both views display the same stats, 
    but the mobile view displays them 
    in a more vertical format within an
    HTML table, while the desktop/laptop 
    view displays more horizontally within
    an HTML table.

    The code simply sets up the HTML tables.
    */

    const mobileStatsView = () => {
      return teamsArray.map((team, index) => {
          const firstTeamPlayers = [...headersPlusPlayersArray].filter(player => player[0].slice(-3) === team.first_team_abbreviation);
          const secondTeamPlayers = [...headersPlusPlayersArray].filter(player => player[0].slice(-3) === team.second_team_abbreviation);
          return (<div key = {`${team.first_team_abbreviation}-${team.second_team_abbreviation}-${index}`}>
            <style> 
              {cssStyleString}
            </style>
            <h2>{team.first_team_abbreviation} vs. {team.second_team_abbreviation}</h2>
            <h2>{team.first_team_abbreviation}</h2>
            {firstTeamPlayers.map((player, index) => (
            <React.Fragment key={player[1]}>  
              <table key = {player[1]}>
                <tbody>
                  <tr>
                    {player.map((header, index) => (
                      <th key = {header}>{header}</th>
                    ))}
                  </tr>
                </tbody>
              </table>
              <br />
              <br />
            </React.Fragment>
            ))}
            <h2>{team.second_team_abbreviation}</h2>
            {secondTeamPlayers.map((player, index) => (
            <React.Fragment key={player[1]}>  
              <table key = {player[1]}>
                <tbody>
                  <tr>
                    {player.map((header, index) => (
                      <th key = {header}>{header}</th>
                    ))}
                  </tr>
                </tbody>
              </table>
              <br />
              <br />
            </React.Fragment>
            ))}
          </div>);
      });
    };

    const desktopStatsView = () => {
      return teamsArray.map((team, index) => {
          const firstTeamPlayers = playersArray.filter(player => player.team_abbreviation === team.first_team_abbreviation);
          const secondTeamPlayers = playersArray.filter(player => player.team_abbreviation === team.second_team_abbreviation);
          return (<div key = {`${team.first_team_abbreviation}-${team.second_team_abbreviation}-${index}`}>
            <h2>{team.first_team_abbreviation} vs. {team.second_team_abbreviation}</h2>
            <h2>{team.first_team_abbreviation}</h2>
            <table>
            <tbody>
            <tr>
            <style> 
              {cssStyleString}
            </style>
            {orderedHeaders.map((header, index) => (
              <th key = {header}>{header}</th>
            ))}
            </tr>
            {
              [...firstTeamPlayers].sort((player, secondPlayer) => secondPlayer.points - player.points).map((player, index) => (
                <tr key = {player[1]}>
                {orderedHeaders.map((header, index) => (
                    <td key = {header}>{player[mappedHeaders[header]]}</td>
                ))}
                </tr>
              ))
            }
            </tbody>
            </table>
            <br />
            <h2>{team.second_team_abbreviation}</h2>
            <table>
            <tbody>
            <tr>
            {orderedHeaders.map((header, index) => (
              <th key = {header}>{header}</th>
            ))}
            </tr>
            {
              [...secondTeamPlayers].sort((player, secondPlayer) => secondPlayer.points - player.points).map((player, index) => (
                <tr key = {player[1]}>
                {orderedHeaders.map((header, index) => (
                    <td key = {header}>{player[mappedHeaders[header]]}</td>
                ))}
                </tr>
              ))
            }
            </tbody>
            </table>
          </div>);
      });
    };

    return (
    <div className="tableStats">
      {/* Button to go back, shown when there are players or teams */}
      {!noPlayersOrTeams && <button onClick={navToHome}>Go Back</button>}
      {/* Message when no games found */}
      {noPlayersOrTeams &&
      (
        <div>
          <h2>No games were found.</h2>
        </div>
      ) }
      {/* Mobile view: display for non-desktop/laptop */}
      {!noPlayersOrTeams && !isDesktopOrLaptop && mobileStatsView()}
      {/* Desktop view: table format */}
      {!noPlayersOrTeams && isDesktopOrLaptop && desktopStatsView()}
      <br />
      <button onClick={navToHome}>Go Back</button>
    </div>
    );
  };

export default NBATeamsAndPlayersStatsDisplay; /* Export component. */