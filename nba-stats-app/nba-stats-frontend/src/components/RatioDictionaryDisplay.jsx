/*

RatioDictionaryDisplay.jsx

Function: To display Dictionary values from a ratio dictionary as HTML.

Inputs:

ratioDict: A Dictionary containing a string with who won a matchup as key,
      and a List containing wins for both teams in a matchup.

teamStatsDictionary: A Dictionary containing team abbreviations as keys, and
            player stats dictionaries as values.

teamPoints: An integer representing the points for a team in a matchup.

oppTeamPoints: An integer representing the points for the opposing team in a matchup.

Output:

Lines of HTML displaying who won the matchup,
the points for each team in the matchup, and
historical wins and losses for the matchup

Time complexity: O(n), where n is the number of players on a team

Space complexity: O(n)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
# 01/10/2026                 Eram Kabir           Added more comments           #
#################################################################################

*/

import React from "react";

const RatioDictionaryDisplay = ({ ratioDict, teamStatsDictionary, teamPoints, oppTeamPoints }) => {

    /* 
    Return if ratioDict or 
    teamStatsDictionary is null.
    This is needed since the
    component is loaded
    immediately upon going
    into the website, but
    the data dictionaries are not.
    */

    if (ratioDict === null || teamStatsDictionary === null){
      return null;
    };

    const key = Object.keys(ratioDict);
    /* 
    If the key is an empty string,
    return null. This is needed
    since the dictionary may
    have an empty string key
    if there is no matchup
    data to display.

    The case where there is no matchup data
    is if the opposing team input field
    is left blank by the user.
    */

    if (key.length > 0 && key[0] === ''){
      return null;
    };

    /* 
    teamDataKeys is an array of the 
    team abbreviations in the 
    teamStatsDictionary. This is 
    used to determine the 
    winning team and to 
    display the points 
    for each team in 
    the matchup.
    */

    const teamStatsDictionaryKeys = Object.keys(teamStatsDictionary);
    const team = teamStatsDictionaryKeys[0];
    const oppTeam = teamStatsDictionaryKeys[1];

    /* 
    Winning team is calculated 
    based on point totals for
    each team. If the points are
    the same, then it is a tie.
    */

    let winningTeam = '';
    if (teamPoints > oppTeamPoints){
        winningTeam = team;
    } else if (oppTeamPoints > teamPoints){
        winningTeam = oppTeam;
    } else {
        winningTeam = "Tie";
    };

    /*
    ptsString is a string that displays 
    the points for each team in the matchup.
    */

    const ptsString = `${team}:${teamPoints} PTS, ${oppTeam}:${oppTeamPoints} PTS`;
    
    /*
    We just index into the RatioDict,
    and set dictionary's key and value
    into the HTML. toString is used
    with the dash to create a Win-Win
    string (ex. 52-49).

    The key of the ratioDict is a string
    that displays who won the matchup based
    on historical data, and the value of
    the ratioDict is a list of two integers
    that display the wins for each team in
    the matchup based on historical data.
    */

    return (
      <React.Fragment key="ratio-dict-display">
        <h1>Projected Winning Team: {winningTeam}</h1>
        <h2>{ptsString}</h2>
        <div>
          {Object.entries(ratioDict).map(([key, value]) => (
            <div key={key}>
              <strong>{key}, {(value[0]).toString() + '-' + (value[1]).toString()}</strong>
            </div>
          ))}
        </div>
      </React.Fragment>
    );
  };

export default RatioDictionaryDisplay;