/*

OAuthCallback.jsx

Function: To handle OAuth callback and set session data.

Inputs:

None.

Output:

None

Time complexity: O(n), where n is the number of characters in the URL query string.

Space complexity: O(n)

###################################################################################
# Date modified              Modifier             What was modified               #
# 01/10/2026                 Eram Kabir           Initial and final Development   #
###################################################################################

*/

/* Libraries and Functions */

import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router";
import exchangeService from "../services/exchange";
import { useAuth } from "../context/authContext";

/*
This function calls the exchange service to exchange
the OAuth code for a session ID, which is stored
and used for user validation.
It then sets the token and user in
the auth context and navigates to
the home page.

The main purpose of this function is
to finish logging the user in via OAuth,
upon which the user can access the
site and its functionality.
*/

export default function OAuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, setToken, setUser } = useAuth();
  const callbackStarted = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    const state = params.get("state");
    const oauthError = params.get("error");

    if (!code || !state) {
      if (oauthError) {
        try {
          sessionStorage.removeItem(exchangeService.stateStorageKey);
        } catch {
          console.error("OAuth state storage is unavailable");
        }
        window.history.replaceState({}, document.title, window.location.pathname);
      }
      return;
    }

    if (callbackStarted.current) {
      return;
    }
    callbackStarted.current = true;

    window.history.replaceState({}, document.title, window.location.pathname);

    let expectedState;
    try {
      expectedState = sessionStorage.getItem(exchangeService.stateStorageKey);
      sessionStorage.removeItem(exchangeService.stateStorageKey);
    } catch {
      console.error("OAuth state storage is unavailable");
      return;
    }
    if (!expectedState || state !== expectedState) {
      console.error("OAuth state validation failed");
      return;
    }

    if (token) {
      return;
    }

    const setSession = async () => {
      try {
        const session = await exchangeService.exchange(code, state);
        setToken(session.token);
        setUser(session.user);
        navigate('/');
      } catch {
        console.error("OAuth exchange failed");
      }
    };

    setSession();
  }, [location.search, navigate, setToken, setUser, token]);
  
  return null;
};
