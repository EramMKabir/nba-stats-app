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

const exchange = async (code, state) => {
  try{
  const response = await axios.post(`${baseUrl}/oauth/exchange`, { code: code, state: state }, { withCredentials: true });
  return response;
  } catch (error) {
    return { token: null, error };
  };
};

export default { exchange };