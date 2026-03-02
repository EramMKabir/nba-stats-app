/*

Main.jsx

Function: It is the entire website.

Inputs:

None.

Output:

None.

Time complexity: O(n), where n is the number of nodes in the DOM.

Space complexity: O(n)

###################################################################################
# Date modified              Modifier             What was modified               #
# 03/16/2025                 Eram Kabir           Initial Development             #
# 01/11/2026                 Eram Kabir           Final Development               #
###################################################################################

*/

/* Libraries and Functions */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import AppWrapper from "./App.jsx";

/* This simply loads the entire website into the index.html file. */
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AppWrapper />
  </StrictMode>,
);