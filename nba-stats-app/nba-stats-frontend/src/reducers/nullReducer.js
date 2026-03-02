/*

nullReducer.js

Function: To manage null values in Redux.

Inputs:

None

Output:

Null values stored in Redux.

Time complexity: O(1), since setting a null value is a constant-time operation.

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

/* This file stores states of null values in Redux. */

const nullSlice = createSlice({
    name: "null",
    initialState: {
        user: null,
        successMessage: null,
        errorMessage: null,
        token: null
    },
    reducers: {
        setUser(state, action) {
            return {
                ...state,
                user: action.payload
            }
        },
        setSuccessMessage(state, action) {
            return {
                ...state,
                successMessage: action.payload
            }
        },
        setErrorMessage(state, action) {
            return {
                ...state,
                errorMessage: action.payload
            }
        },
        setToken(state, action) {
            return {
                ...state,
                token: action.payload
            }
        }
    }
});

export const { setUser, setSuccessMessage, setErrorMessage, setToken } = nullSlice.actions;
export default nullSlice.reducer;