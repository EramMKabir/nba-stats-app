/*

exchange.js

Function: To call the OAuth exchange microservice in the backend.

Inputs:

code: The authorization code received from the OAuth provider.

state: The state parameter to prevent CSRF attacks.

Output:

JSON response from the backend containing the access token or an error code.

Time complexity: O(1), since the function makes a single HTTP request.

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

import axios from "axios";

const baseUrl = import.meta.env.VITE_PYTHON_API_BASE_URL;
const stateStorageKey = "oauth_state";

const start = async () => (await axios.get(`${baseUrl}/oauth/login`, {
  params: { response_mode: "json" },
})).data;

const exchange = async (code, state) =>
  (await axios.post(`${baseUrl}/oauth/exchange`, { code, state })).data;

export default { exchange, start, stateStorageKey };
