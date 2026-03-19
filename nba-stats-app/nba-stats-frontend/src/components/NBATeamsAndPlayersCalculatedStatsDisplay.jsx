/*

NBATeamsAndPlayersCalculatedStatsDisplay.jsx

Function: To display stats calculated using raw stats from 
          the NBA API for NBA teams and players.

Inputs:

teamStatsDictionary: A dictionary containing calculated player stats from the backend.

lastGameStatsDictionary: A dictionary containing player stats from
last matchup game.

injuredPlayersDictionary: A dictionary containing the names of injured players.

Output:

HTML Tables of team player stats and opposing team player stats.

Time complexity: O(nlogn), where n is the number of components in the HTML Tree.

Space complexity: O(nlogn)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
# 01/10/2026                 Eram Kabir           Added more comments           #
#################################################################################

*/

/*
Libraries
*/

import { useMediaQuery } from "react-responsive";
import React from "react";

const NBATeamsAndPlayersCalculatedStatsDisplay = ({ teamStatsDictionary, lastGameStatsDictionary, injuredPlayersDictionary }) => {
    
    /* 
    Return if teamStatsDictionary is empty.
    This is needed since the
    component is loaded
    immediately upon going
    into the website, but
    teamStatsDictionary is not.
    */

    if (Object.keys(teamStatsDictionary).length === 0){
        return null;
    };

    /* 
    isDesktopOrLaptop is made
    to determine if the user
    is on a desktop/laptop
    or on a mobile device.

    dictKeys is made to access
    the two teams in the teamStatsDictionary
    dictionary.

    alteredData is made to
    filter out injured players
    from teamStatsDictionary,
    using the injuredPlayersDictionary
    passed as a prop.

    cssStyleString is meant to be
    the styling for the HTML table.

    orderedHeaders is made to
    order the NBA stat names
    in a specific order for
    display in the HTML tables.

    statNameToDisplayName is
    made to map NBA stat names
    to the keys used in the
    lastGameStatsDictionary.

    sortedDataFirstTeam and
    sortedDataSecondTeam are
    made to sort the players
    of each team based on points
    scored in descending order.

    orderedHeadersPlusFirstTeamStats
    and orderedHeadersPlusSecondTeamStats
    are made to create Lists of Lists,
    where each inner List contains
    the player name, stats, and
    changes from last game for
    each player, ordered by
    points scored.

    statsFromLastGameForFirstTeam
    and statsFromLastGameForSecondTeam
    are made to create Lists of Lists,
    where each inner List contains
    only the changes from last game
    for each player, ordered by
    points scored.
    */

    const isDesktopOrLaptop = useMediaQuery({ minWidth: 601 });

    const dictKeys = Object.keys(teamStatsDictionary);

    const alteredData = {...teamStatsDictionary, 
                            firstTeam: Object.fromEntries(Object.entries(teamStatsDictionary[dictKeys[0]]).filter(([player, stats]) => !injuredPlayersDictionary[player])), 
                            secondTeam: Object.fromEntries(Object.entries(teamStatsDictionary[dictKeys[1]]).filter(([player, stats]) => !injuredPlayersDictionary[player]))};

    const cssStyleString = "table { font-family: arial, sans-serif;border-collapse: collapse; width: 100%; } \
                            td, th { border: 1px solid #dddddd; text-align: left; padding: 8px; }";

    const orderedHeaders = ["MIN", 
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
    
    const statNameToDisplayName = {
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
        "PLUS_MINUS": "plus_minus"
    };
    
    const sortedDataFirstTeam = Object.entries(alteredData.firstTeam).sort(([, stats], [, secondStats]) => secondStats.PTS - stats.PTS);
    
    const sortedDataSecondTeam = Object.entries(alteredData.secondTeam).sort(([, stats], [, secondStats]) => secondStats.PTS - stats.PTS);
    
    const getOrderedHeadersPlusTeamStats = (sortedData) => {
        return sortedData.map(([player, stats]) => {
            const orderedStats = [`NAME: ${player}`];
            
            orderedHeaders.forEach((statName) => {
              
              const playerInLastGame = lastGameStatsDictionary[player];
              const stat = stats[statName];
              const lastGameStat = playerInLastGame ? lastGameStatsDictionary[player][statNameToDisplayName[statName]] : 0;
              
              orderedStats.push(`${statName}: ${stat}`);
              if (playerInLastGame && (stat === 0 || stat === 0.0)){
                  orderedStats.push(`${statName} Absolute Change from Last Recent Game: ${(lastGameStat > stat) ? '-' : (lastGameStat < stat ? '+' : '')}${lastGameStat}`);
              } else if (playerInLastGame && lastGameStat > stat){
                  orderedStats.push(`${statName} % Change from Last Recent Game: ${`-${(Math.abs(((lastGameStat - stat) / stat) * 100)).toFixed(1)}%`}`);
              } else if (playerInLastGame && lastGameStat < stat){
                  orderedStats.push(`${statName} % Change from Last Recent Game: ${`+${(Math.abs(((lastGameStat - stat) / stat) * 100)).toFixed(1)}%`}`);
              } else if (playerInLastGame && lastGameStat === stat){
                  orderedStats.push(`${statName} % Change from Last Recent Game: 0.0%`);
              } else {
                  orderedStats.push(`${statName} % Change from Last Recent Game: N/A`);
              };
            }
          );
            return orderedStats;
        });
    };

    const orderedHeadersPlusFirstTeamStats = getOrderedHeadersPlusTeamStats(sortedDataFirstTeam);

    const orderedHeadersPlusSecondTeamStats = getOrderedHeadersPlusTeamStats(sortedDataSecondTeam);

    const getStatsFromLastGameForTeam = (sortedData) => {
        return sortedData.map(([player, stats]) => {
            const lastGameStats = [];
            
            orderedHeaders.forEach((statName) => {
            
              const playerInLastGame = lastGameStatsDictionary[player];
              const stat = stats[statName];
              const lastGameStat = playerInLastGame ? lastGameStatsDictionary[player][statNameToDisplayName[statName]] : 0;
            
              if (playerInLastGame && (stat === 0 || stat === 0.0)){
                  lastGameStats.push(`${(lastGameStat > stat) ? '-' : (lastGameStat < stat ? '+' : '')}${lastGameStat}`);
              } else if (playerInLastGame && lastGameStat > stat){
                  lastGameStats.push(`-${(Math.abs(((lastGameStat - stat) / stat) * 100)).toFixed(1)}%`);
              } else if (playerInLastGame && lastGameStat < stat){
                  lastGameStats.push(`+${(Math.abs(((lastGameStat - stat) / stat) * 100)).toFixed(1)}%`);
              } else if (playerInLastGame && lastGameStat === stat){
                  lastGameStats.push("0.0%");
              } else {
                  lastGameStats.push("N/A");
              };
            }
          );
            return lastGameStats;
        });
    };

    const statsFromLastGameForFirstTeam = getStatsFromLastGameForTeam(sortedDataFirstTeam);

    const statsFromLastGameForSecondTeam = getStatsFromLastGameForTeam(sortedDataSecondTeam);

    /* 
    For the following views,
    here are the steps:

    1. Style the HTML tables to be made
       with the cssStyleString defined
       earlier.

    2. Display the first team name
       as a header.

    3. If the user is on a mobile
       device, display each player's
       stats in their own table,
       with the stats listed vertically.

    4. If the user is on a desktop
       or laptop, display all players'
       stats in one table, with the
       stats listed horizontally.

    5. Repeat steps 2-4 for the second
       team.

    The CSS styling for the td and th 
    elements of the tables is made to
    display positive stat increases from 
    last game in green, and negative 
    stat increases from last game in red.

    */

    const mobileCalculatedStatsView = () => {
        return (
              <div className="tableStats">
              <style>
                {cssStyleString}
              </style>
              <h1 className="header">{dictKeys[0]}</h1>
                {orderedHeadersPlusFirstTeamStats.map((playerStats, index) => (
                  <React.Fragment key={playerStats[0]}>
                    <table className="table">
                      <tbody>
                      {playerStats.map((stat, statIndex) => (
                        <tr key={`${playerStats[0]}-${stat}`}>
                          <th className={`${stat.includes('+') && 
                                            (stat.includes('%') || stat.includes("Absolute Change")) 
                                            ? "greenText" 
                                            : (stat.includes('-') && 
                                            (stat.includes('%') || stat.includes("Absolute Change")) 
                                            ? "redText" 
                                            : '')}`}>{stat}</th>
                        </tr>
                      ))}
                      </tbody>
                    </table>
                    <br/>
                    <br/>
                  </React.Fragment>
                ))}
              <h1 className="header">{dictKeys[1]}</h1>
                {orderedHeadersPlusSecondTeamStats.map((playerStats, index) => (
                  <React.Fragment key={playerStats[0]}>
                    <table className="table">
                      <tbody>
                      {playerStats.map((stat, statIndex) => (
                        <tr key={`${playerStats[0]}-${stat}`}>
                          <th className={`${stat.includes('+') && 
                                            (stat.includes('%') || stat.includes("Absolute Change")) 
                                            ? "greenText" 
                                            : (stat.includes('-') && 
                                            (stat.includes('%') || stat.includes("Absolute Change")) 
                                            ? "redText" 
                                            : '')}`}>{stat}</th>
                        </tr>
                      ))}
                      </tbody>
                    </table>
                    <br/>
                    <br/>
                  </React.Fragment>
                ))}
            </div> 
        );
    };

    const desktopCalculatedStatsView = () => {
        return (<div className="tableStats">
                <style>
                  {cssStyleString}
                </style>
                <h1 className="header">{dictKeys[0]}</h1>
                <table className="table">
                  <tbody>
                    <tr>
                      <th>NAME</th>
                      {
                        orderedHeaders.map((statNames, index) => (
                          <th key = {statNames}>{statNames}</th>
                        ))
                      }
                    </tr>
                    {
                      sortedDataFirstTeam.map(([player, stats], index) => (
                        <React.Fragment key={player}>
                          <tr key = {player}>
                            <td key = {player}>{player}</td>
                            {orderedHeaders.map((statNames, index) => (
                            <td key = {`${player}-${statNames}`}>{stats[statNames]}</td>
                            ))}
                          </tr>
                          <tr key = {`lastGame-${player}`}>
                            <td key = {`lastGame-${player}`}>Stat Changes from Last Recent Game</td>
                            {statsFromLastGameForFirstTeam[index].map((statChange, statChangeIndex) => (
                            <td key = {`${player}-${statChange}-${statChangeIndex}`} className={`${statChange.includes('+') 
                                                                            ? "greenText" 
                                                                            : (statChange.includes('-') 
                                                                            ? "redText" 
                                                                            : '')}`}>{statChange}</td>
                            ))}
                          </tr>
                        </React.Fragment>
                      ))
                    }
                  </tbody>
                </table>
                <h1 className="header">{dictKeys[1]}</h1>
                <table className="table">
                  <tbody>
                    <tr>
                      <th>NAME</th>
                      {
                        orderedHeaders.map((statNames, index) => (
                          <th key={statNames}>{statNames}</th>
                        ))
                      }
                    </tr>
                    {
                      sortedDataSecondTeam.map(([player, stats], index) => (
                        <React.Fragment key={player}>
                          <tr key = {player}>
                            <td key = {player}>{player}</td>
                            {orderedHeaders.map((statNames, index) => (
                            <td key = {`${player}-${statNames}`}>{stats[statNames]}</td>
                            ))}
                          </tr>
                          <tr key = {`lastGame-${player}`}>
                            <td key = {`lastGame-${player}`}>Stat Changes from Last Recent Game</td>
                            {statsFromLastGameForSecondTeam[index].map((statChange, statChangeIndex) => (
                            <td key = {`${player}-${statChange}-${statChangeIndex}`} className={`${statChange.includes('+') 
                                                                            ? "greenText" 
                                                                            : (statChange.includes('-') 
                                                                            ? "redText" 
                                                                            : '')}`}>{statChange}</td>
                            ))}
                          </tr>
                        </React.Fragment>
                      ))
                    }
                  </tbody>
                </table>
              </div>);
    };

    return (!isDesktopOrLaptop 
            ?
            mobileCalculatedStatsView()
            : 
            desktopCalculatedStatsView()
    );
};

export default NBATeamsAndPlayersCalculatedStatsDisplay;