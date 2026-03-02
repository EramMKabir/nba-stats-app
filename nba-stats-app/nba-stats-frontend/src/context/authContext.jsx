/*

authContext.jsx

Function: To provide context to all components.

Inputs:

children: The inner HTML tags in an instance of authContext.

Output:

None

Time complexity: O(1)

Space complexity: O(1)

###################################################################################
# Date modified              Modifier             What was modified               #
# 01/11/2026                 Eram Kabir           Initial and final Development   #
###################################################################################

*/

/* Libraries and Functions */

import { createContext, useContext } from "react";
import { useSelector, useDispatch } from "react-redux";
import { setToken as setTokenAction, setUser as setUserAction } from "../reducers/nullReducer";
import { setLoadingLogout as setLoadingLogoutAction } from "../reducers/booleanReducer";

/* 
   This file simply allows for universal 
   context variables to be used in all
   components. 

   The universal variables are token
   (allows user to use website),
   user, and loadingLogout (helps in
   letting user logout successfully).
*/

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const dispatch = useDispatch();

  const token = useSelector((state) => state.nullReducer.token);
  const user = useSelector((state) => state.nullReducer.user);
  const loadingLogout = useSelector((state) => state.booleanReducer.loadingLogout);

  const setToken = (value) => dispatch(setTokenAction(value));
  const setUser = (value) => dispatch(setUserAction(value));
  const setLoadingLogout = (value) => dispatch(setLoadingLogoutAction(value));

  return (
    <AuthContext.Provider value={{ token, setToken, user, setUser, loadingLogout, setLoadingLogout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);