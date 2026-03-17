/*

Help.jsx

Function: To display help for the website.

Inputs:

None

Output:

HTML text that is meant to help understand the website.

Time complexity: O(1)

Space complexity: O(1)

#################################################################################
# Date modified              Modifier             What was modified             #
# 01/12/2026                 Eram Kabir           Initial and final development #
#################################################################################

*/

/* Libraries */

import React from "react";

const Help = () => {

    return (
        <React.Fragment key="help">
        <p>
            The screen you were previously on was
            the input screen. That screen has an
            Upcoming Games link, and inputs. The
            Upcoming Games link shows 5 upcoming
            games, and the player stats for each
            team in the game.
        </p>
        <p>
            The inputs change depending on the
            button above them. If the button
            says 'Switch to Matchup Projections',
            then the inputs are for calculating
            player stats. If the button says
            'Switch to Player Projections', then
            the inputs are for calculating matchup
            stats and the winner of a matchup.
        </p>
        <p>
            The inputs are the following for 
            player stat calculations:
        </p>
        <p>
            <strong>Player Full Name</strong>: self-explanatory.
        </p>
        <p>
            <strong>Season Year</strong>: the year you want to see 
            the player stats for.
        </p>
        <p>
            <strong>Season Type</strong>: the season type you want
            to see the player stats for.
        </p>
        <p>
            <strong>Opposing Team (optional)</strong>: calculates
            a player's stats with respect to an
            opposing team. If blank, does nothing.
        </p>
        <p>
            <strong>Recent Games (optional)</strong>: calculates a
            player's stats while only considering
            the last x games, where x is the user's
            numerical input. If blank, considers all
            games.
        </p>
        <p>
            The inputs are the following for 
            matchup stat calculations:
        </p>
        <p>
            <strong>Team</strong>: self-explanatory.
        </p>
        <p>
            <strong>Season Year</strong>: the year you want to see 
            the matchup stats for.
        </p>
        <p>
            <strong>Season Type</strong>: the season type you want
            to see the matchup stats for.
        </p>
        <p>
            <strong>Opposing Team (optional)</strong>: The
            opposing team in the matchup.
            If blank, the stats of the team
            input are calculated without taking
            other teams into consideration.
        </p>
        <p>
            <strong>Recent Games (optional)</strong>: calculates 
            the matchup's stats while only
            considering the last x games in 
            the matchup. If blank, considers
            all games.
        </p>
        <p>
            Upon submitting either set of
            inputs, the corresponding stats
            are displayed. The matchup stats 
            are displayed in an HTML table, 
            that you can scroll through.
        </p>
        <p>
            If you wish to see the stats of an 
            entire team, use the matchup inputs
            and leave the opposing team blank.
            Alternatively, you could also look
            at the upcoming games and see if
            the team you want is there.
        </p>
        <p>
            <strong>NOTE:</strong> The site may
            lag heavily when calculating stats,
            due to data being updated every 30
            minutes. It should be very rare,
            but I am letting you know in case
            you experience it.
        </p>
        <p>
            Have fun using the site.
        </p>
        <p>
            -EramMKabir
        </p>
        </React.Fragment>
    );
};

export default Help;