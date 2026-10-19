/*

StatsDictionaryDisplay.jsx

Function: To display an NBA stats Dictionary's keys and values as HTML.

Inputs:

statsDictionary: An NBA stats dictionary.

Output:

HTML Lines that each display a key and its value from an NBA stats dictionary.

Time complexity: O(n), where n is the number of elements in the dictionary.

Space complexity: O(n)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
# 01/11/2026                 Eram Kabir           Added more comments           #
#################################################################################

*/

const IndividualPlayerStatsDictionaryDisplay = ({ statsDictionary }) => {

    /* 
    Return if there is no statsDictionary.
    This is needed since the
    component is loaded
    immediately upon going
    into the website, but
    the statsDictionary is not.
    */

    if (statsDictionary === null){
      return null;
    };

    /* 
    Array used to map stats with respective stat names 
    */

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


    /* 
    map is used to put each key
    and value pair on an HTML line.

    className for the second div
    varies depending on whether or
    not the displayed stat is PTS.
    
    Underscores are removed for
    all stat names.

    The plus_minus stat is the only
    stat that is allowed to be less
    than 0.

    All other stats must be 0 or
    higher.
    */

    return (
      <div className="stat-grid">
        {orderedHeaders.map((statNames, index) => (
          <div className={`stat-card ${statNames === "PTS" ? "featured-stat" : ""}`} key={index}>
            <span>{statNames.replaceAll("_", " ")}</span>
            <strong>{statNames === "PLUS_MINUS" ? statsDictionary[statNames] : Math.max(0, statsDictionary[statNames])}</strong>
          </div>
        ))}
      </div>
    );
  };

export default IndividualPlayerStatsDictionaryDisplay;
