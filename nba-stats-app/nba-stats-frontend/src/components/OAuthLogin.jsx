/*

OAuthLogin.jsx

Function: To initiate OAuth login.

Inputs:

None.

Output:

None

Time complexity: O(1)

Space complexity: O(1)

###################################################################################
# Date modified              Modifier             What was modified               #
# 01/10/2026                 Eram Kabir           Initial and final Development   #
###################################################################################

*/

import exchangeService from "../services/exchange";

/* 
All this component does is 
redirect the user to the OAuth 
login page on the backend, if
they click on the component's
button.
*/

export default function OAuthLogin() {
  const startLogin = async () => {
    try {
      const { authorization_url: url, state } = await exchangeService.start();
      if (!url || !state) throw new Error("Invalid OAuth response");
      sessionStorage.setItem(exchangeService.stateStorageKey, state);
      window.location.assign(url);
    } catch {
      console.error("Unable to start OAuth login");
    }
  };

  return (
    <button className="google-login" onClick={startLogin}>
      <span className="google-g" aria-hidden="true">G</span>
      Continue with Google
      <span className="login-arrow" aria-hidden="true">→</span>
    </button>
  );
};
