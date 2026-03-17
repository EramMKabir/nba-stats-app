/*

booleanReducer.js

Function: To manage boolean values in Redux.

Inputs:

None

Output:

Boolean values stored in Redux.

Time complexity: O(1), since the component sets a boolean value in HTML.

Space complexity: O(1)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
#################################################################################

*/

/*
Library 
*/

import { createSlice } from "@reduxjs/toolkit";

/* This file stores states of boolean values in Redux. */

const booleanSlice = createSlice({
    name: "boolean",
    initialState: {
        playerStats: false,
        teamStats: false,
        noPlayersOrTeams: false,
        loadingLogout: false,
        swapInputsToPlayer: true,
        swapInputsToMatchup: false,
        helpDisplay: false,
        upcomingGamesStats: true
    },
    reducers: {
        setPlayerStats(state, action) {
            return {
                ...state,
                playerStats: action.payload
            }
        },
        setTeamStats(state, action) {
            return {
                ...state,
                teamStats: action.payload
            }
        },
        setNoPlayersOrTeams(state, action) {
            return {
                ...state,
                noPlayersOrTeams: action.payload
            }
        },
        setLoadingLogout(state, action) {
            return {
                ...state,
                loadingLogout: action.payload
            }
        },
        setSwapInputsToPlayer(state, action) {
            return {
                ...state,
                swapInputsToPlayer: action.payload
            }
        },
        setSwapInputsToMatchup(state, action) {
            return {
                ...state,
                swapInputsToMatchup: action.payload
            }
        },
        setHelpDisplay(state, action) {
            return {
                ...state,
                helpDisplay: action.payload
            }
        },
        setUpcomingGamesStats(state, action) {
            return {
                ...state,
                upcomingGamesStats: action.payload
            }
        }
    }
});

export const { setPlayerStats, setTeamStats, setNoPlayersOrTeams, setLoadingLogout, setSwapInputsToPlayer, setSwapInputsToMatchup, setHelpDisplay, setUpcomingGamesStats } = booleanSlice.actions;
export default booleanSlice.reducer;