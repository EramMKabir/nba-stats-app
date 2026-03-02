/*

stringReducer.js

Function: To manage strings in Redux.

Inputs:

None

Output:

Strings stored in Redux.

Time complexity: O(n), where n is the length of the string being set.

Space complexity: O(n)

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

/* This file stores states of strings in Redux. */

const stringSlice = createSlice({
    name: "string",
    initialState: {
        playerName: '',
        username: '',
        password: '',
        newUsername: '',
        newPassword: '',
        playerFullName: '',
        season: '',
        seasonType: '',
        opposingTeam: '',
        recentGames: '',
        team: '',
        seasonM: '',
        seasonTypeM: '',
        opposingTeamM: '',
        recentGamesM: '',
        playerFullNameInput: '',
        seasonInput: '',
        seasonTypeInput: '',
        opposingTeamInput: '',
        teamInput: '',
        seasonMInput: '',
        seasonTypeMInput: '',
        opposingTeamMInput: '',
    },
    reducers: {
        setPlayerName(state, action) {
            return {
                ...state,
                playerName: action.payload
            }
        },
        setUsername(state, action) {
            return {
                ...state,
                username: action.payload
            }
        },
        setPassword(state, action) {
            return {
                ...state,
                password: action.payload
            }
        },
        setNewUsername(state, action) {
            return {
                ...state,
                newUsername: action.payload
            }
        },
        setNewPassword(state, action) {
            return {
                ...state,
                newPassword: action.payload
            }
        },
        setPlayerFullName(state, action) {
            return {
                ...state,
                playerFullName: action.payload
            }
        },
        setSeason(state, action) {
            return {
                ...state,
                season: action.payload
            }
        },
        setSeasonType(state, action) {
            return {
                ...state,
                seasonType: action.payload
            }
        },
        setOpposingTeam(state, action) {
            return {
                ...state,
                opposingTeam: action.payload
            }
        },
        setRecentGames(state, action) {
            return {
                ...state,
                recentGames: action.payload
            }
        },
        setTeam(state, action) {
            return {
                ...state,
                team: action.payload
            }
        },
        setSeasonM(state, action) {
            return {
                ...state,
                seasonM: action.payload
            }
        },
        setSeasonTypeM(state, action) {
            return {
                ...state,
                seasonTypeM: action.payload
            }
        },
        setOpposingTeamM(state, action) {
            return {
                ...state,
                opposingTeamM: action.payload
            }
        },
        setRecentGamesM(state, action) {
            return {
                ...state,
                recentGamesM: action.payload
            }
        },
        setPlayerFullNameInput(state, action) {
            return {
                ...state,
                playerFullNameInput: action.payload
            }
        },
        setSeasonInput(state, action) {
            return {
                ...state,
                seasonInput: action.payload
            }
        },
        setSeasonTypeInput(state, action) {
            return {
                ...state,
                seasonTypeInput: action.payload
            }
        },
        setOpposingTeamInput(state, action) {
            return {
                ...state,
                opposingTeamInput: action.payload
            }
        },
        setTeamInput(state, action) {
            return {
                ...state,
                teamInput: action.payload
            }
        },
        setSeasonMInput(state, action) {
            return {
                ...state,
                seasonMInput: action.payload
            }
        },
        setSeasonTypeMInput(state, action) {
            return {
                ...state,
                seasonTypeMInput: action.payload
            }
        },
        setOpposingTeamMInput(state, action) {
            return {
                ...state,
                opposingTeamMInput: action.payload
            }
        }
    }
});

export const { setPlayerName, 
               setUsername, 
               setPassword, 
               setNewUsername, 
               setNewPassword,
               setPlayerFullName,
               setSeason,
               setSeasonType,
               setOpposingTeam,
               setRecentGames,
               setTeam, 
               setSeasonM,
               setSeasonTypeM,
               setOpposingTeamM,
               setRecentGamesM,
               setPlayerFullNameInput,
               setSeasonInput,
               setSeasonTypeInput,
               setOpposingTeamInput,
               setTeamInput,
               setSeasonMInput,
               setSeasonTypeMInput,
               setOpposingTeamMInput,
            } = stringSlice.actions;
export default stringSlice.reducer;