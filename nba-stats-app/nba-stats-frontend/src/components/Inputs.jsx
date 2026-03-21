/*

Inputs.jsx

Function: To accept user inputs for the NBA matchup the user wants to view.

Inputs:

getPlayerStats: A function that calculates NBA player stats by using
                a microservice on the backend.

getMatchupStats: A function that calculates NBA matchup stats by using
                a microservice on the backend.

Output:

A form component that accepts a player's full name, season, season type,
opposing team, recent game amount, and option type for projection
calculations.

Time complexity: O(n), where n is the number of components in the HTML Tree.

Space complexity: O(n)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/14/2025                 Eram Kabir           Finalized V1.0                #
# 01/10/2026                 Eram Kabir           Added more default values     #
#################################################################################

*/

/* Libraries and Functions */

import { setPlayerFullName, setSeason, setSeasonType, setOpposingTeam, setRecentGames, setTeam, setSeasonM, setSeasonTypeM, setOpposingTeamM, setRecentGamesM, setPlayerFullNameInput, setSeasonInput, setSeasonTypeInput, setOpposingTeamInput, setTeamInput, setSeasonMInput, setSeasonTypeMInput, setOpposingTeamMInput } from "../reducers/stringReducer";
import { setSwapInputsToPlayer, setSwapInputsToMatchup } from "../reducers/booleanReducer";
import { useSelector, useDispatch } from "react-redux";
import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import { useMediaQuery } from "react-responsive";

const Inputs = ({ getPlayerStats, getMatchupStats, playerNamesArray, teamAbbreviationsArray }) => {

  /*
  The state variables below are
  for managing the states of the user
  inputs.

  playerFullName: The full name of the player
  season: The season year
  seasonType: The type of the season
  opposingTeam: The opposing team abbreviation
  recentGames: The number of recent games to consider
  playerNamesArray: An array of all possible player names
  teamAbbreviationsArray: An array of all possible team abbreviations
  swapInputsToPlayer: A boolean to swap inputs to player projections
  swapInputsToMatchup: A boolean to swap inputs to matchup projections
  team: The team abbreviation
  seasonM: The season year for matchup calcs
  seasonTypeM: The type of season for matchup calcs
  opposingTeamM: The opposing team abbreviation for matchup calcs
  recentGamesM: The number of recent games to consider for matchup calcs
  teamInput: The input value for the team field
  seasonMInput: The input value for the seasonM field
  seasonTypeMInput: The input value for the seasonTypeM field
  opposingTeamMInput: The input value for the opposingTeamM field

  For the player projections, the inputs are:
  playerFullName, season, seasonType,
  opposingTeam (to see performance against a certain team), 
  recentGames (to see recent performance).

  For the matchup projections, the inputs are:
  team, seasonM, seasonTypeM, 
  opposingTeamM, recentGamesM.

  All states are managed using
  Redux, and all the reducers
  for the states are managed in
  the reducers directory.
  */

  const playerFullName = useSelector((state) => state.stringReducer.playerFullName);
  const season = useSelector((state) => state.stringReducer.season);
  const seasonType = useSelector((state) => state.stringReducer.seasonType);
  const opposingTeam = useSelector((state) => state.stringReducer.opposingTeam);
  const recentGames = useSelector((state) => state.stringReducer.recentGames);
  const playerFullNameInput = useSelector((state) => state.stringReducer.playerFullNameInput);
  const seasonInput = useSelector((state) => state.stringReducer.seasonInput);
  const seasonTypeInput = useSelector((state) => state.stringReducer.seasonTypeInput);
  const opposingTeamInput = useSelector((state) => state.stringReducer.opposingTeamInput);
  const swapInputsToPlayer = useSelector((state) => state.booleanReducer.swapInputsToPlayer);
  const swapInputsToMatchup = useSelector((state) => state.booleanReducer.swapInputsToMatchup);
  const team = useSelector((state) => state.stringReducer.team);
  const seasonM = useSelector((state) => state.stringReducer.seasonM);
  const seasonTypeM = useSelector((state) => state.stringReducer.seasonTypeM);
  const opposingTeamM = useSelector((state) => state.stringReducer.opposingTeamM);
  const recentGamesM = useSelector((state) => state.stringReducer.recentGamesM);
  const teamInput = useSelector((state) => state.stringReducer.teamInput);
  const seasonMInput = useSelector((state) => state.stringReducer.seasonMInput);
  const seasonTypeMInput = useSelector((state) => state.stringReducer.seasonTypeMInput);
  const opposingTeamMInput = useSelector((state) => state.stringReducer.opposingTeamMInput);

  const dispatch = useDispatch(); /* Used to change state */
  /* 
  Used to determine device type. 
  Needed for adjusting size of inputs
  based on device type.
  */
  const isDesktopOrLaptop = useMediaQuery({ minWidth: 601 });

  /* 
     Functions to swap
     inputs between player
     projections and matchup
     projections. All inputs
     are cleared when swapping.
  */

  const resetPlayerInputs = () => {
    dispatch(setPlayerFullName(''));
    dispatch(setPlayerFullNameInput(''));
    dispatch(setSeason(''));
    dispatch(setSeasonInput(''));
    dispatch(setSeasonType(''));
    dispatch(setSeasonTypeInput(''));
    dispatch(setOpposingTeam(''));
    dispatch(setOpposingTeamInput(''));
    dispatch(setRecentGames(''));
  };

  const resetMatchupInputs = () => {
    dispatch(setTeam(''));
    dispatch(setTeamInput(''));
    dispatch(setSeasonM(''));
    dispatch(setSeasonMInput(''));
    dispatch(setSeasonTypeM(''));
    dispatch(setSeasonTypeMInput(''));
    dispatch(setOpposingTeamM(''));
    dispatch(setOpposingTeamMInput(''));
    dispatch(setRecentGamesM(''));
  };

  const setInputsToPlayer = () => {
    dispatch(setSwapInputsToPlayer(true));
    dispatch(setSwapInputsToMatchup(false));
    resetMatchupInputs();
  };

  const setInputsToMatchup = () => {
    dispatch(setSwapInputsToPlayer(false));
    dispatch(setSwapInputsToMatchup(true));
    resetPlayerInputs();
  };

  /* Generating an array of
     seasons from 1946 to
     the current year for
     the season input field.
     Each element has the
     format YYYY-YY
     (ex. 2025-26)
  */
  const currentYear = new Date().getFullYear();
  const nbaStartingYear = 1946;

  const years = Array.from(
    { length: currentYear - nbaStartingYear + 1 },
    (_, i) => {
      const year = currentYear - i;
      const nextShort = String((year + 1) % 100).padStart(2, '0');
      return `${year}-${nextShort}`;
    }
  );

  /* Array for each type of season, used for autocomplete input */
  const seasonTypes = ["Pre Season", "Regular Season", "Playoffs"];

  /* 
     Checks if entries are present
     for playerNamesArray and 
     teamAbbreviationsArray. If not,
     then corresponding inputs will
     have empty string values instead 
     of undefined values
  */
  const playerNamesArrayHasEntries = playerNamesArray.length > 0;
  const teamAbbreviationsArrayHasEntries = teamAbbreviationsArray.length > 0;

  /*
  The following functions take the inputs a user
  made, and sends them to the backend
  microservices as a request for matchup
  information or as a request for player
  information. If any input is not valid, then
  the inputs are cleared and no response is given.

  The function also defaults the fields of the inputs
  after sending the request.
  */

  const getPlayerInputs = async (event) => {
    event.preventDefault();
    const playerFullNameInPlayerNamesArray = playerNamesArray.some(entry => {
      return entry.player_name === playerFullName.player_name;
    });
    const opposingTeamInTeamAbbreviationsArray = teamAbbreviationsArray.some(entry => {
      return entry.team_abbreviation === opposingTeam.team_abbreviation;
    });
    if (!playerFullNameInPlayerNamesArray
      || !years.includes(season)
      || !seasonTypes.includes(seasonType)
      || ((!opposingTeamInTeamAbbreviationsArray) && (opposingTeam.team_abbreviation))) {
      resetPlayerInputs();
      return;
    };
    await getPlayerStats(playerFullName.player_name,
      season,
      seasonType,
      opposingTeam.team_abbreviation,
      recentGames);
    resetPlayerInputs();
  };

  const getMatchupInputs = async (event) => {
    event.preventDefault();
    const teamInTeamAbbreviationsArray = teamAbbreviationsArray.some(entry => {
      return entry.team_abbreviation === team.team_abbreviation;
    });
    const opposingTeamInTeamAbbreviationsArray = teamAbbreviationsArray.some(entry => {
      return entry.team_abbreviation === opposingTeamM.team_abbreviation;
    });
    if (!teamInTeamAbbreviationsArray
      || !years.includes(seasonM)
      || !seasonTypes.includes(seasonTypeM)
      || ((!opposingTeamInTeamAbbreviationsArray) && (opposingTeamM.team_abbreviation))) {
      resetMatchupInputs();
      return;
    };
    await getMatchupStats(team.team_abbreviation,
      seasonM,
      seasonTypeM,
      opposingTeamM.team_abbreviation,
      recentGamesM);
    resetMatchupInputs();
  };

  /*
  handleNonNumberKeys is meant to only allow
  numbers and control keys to be input.
  Everything else is denied with 
  preventDefault when pressing a key.
  */

  const handleNonNumberKeys = (event) => {
    const allowedKeys = [
      "Backspace",
      "Delete",
      "ArrowLeft",
      "ArrowRight",
      "Tab",
      "Home",
      "End",
    ];

    if (allowedKeys.includes(event.key)) return;

    if (/^\d$/.test(event.key)) return;

    event.preventDefault();
  };

  /*
  handleNonNumberPastes is meant to only allow
  numbers to be pasted. Everything else is 
  denied with preventDefault when pasting.
  */

  const handleNonNumberPastes = (event) => {
    const paste = event.clipboardData.getData("text");
    if (!/^\d+$/.test(paste)) {
      event.preventDefault();
    };
  };

  /*
  sanitizeRecentGamesInput is meant to
  ensure that the input is only numeric.
  It removes all non-numeric inputs as 
  a last ditch effort, if all other 
  number checks have failed. 

  sanitizeRecentGamesInput is meant 
  for the player inputs.

  sanitizeRecentGamesInputM is meant
  for the matchup inputs.
  */

  const sanitizeRecentGamesInput = (event) => {
    const recentGames = event.target.value.replace(/\D/g, '');
    dispatch(setRecentGames(recentGames));
  };

  const sanitizeRecentGamesInputM = (event) => {
    const recentGamesM = event.target.value.replace(/\D/g, '');
    dispatch(setRecentGamesM(recentGamesM));
  };

  /*
  Set up team abbreviations array with empty input,
  to allow for either matchup or singular team projections
  when calculating projections. 
  */
  const emptyStringArray = [{ team_abbreviation: '' }];
  const finalTeamAbbreviations = [...emptyStringArray, ...teamAbbreviationsArray];

  /*
  Sizes of the autocomplete inputs. 
  */
  const autoCompleteSize = isDesktopOrLaptop ? "medium" : "small";

  /*
  The following functions are for rendering the
  Autocomplete components of the stat projection 
  inputs.
  */

  /*
  
  For the playerFullName, team, and 
  opposingTeam fields, the
  data obtained from useEffect
  is used to fill the fields.

  seasonType has 3 fields filled
  in to cover most of the NBA season.

  recentGames can only be a numerical
  value as a string, or an empty string.
  The user can only enter numbers in
  this field.

  There is also a button to swap
  between player projections
  and matchup projections.

  The values for the first 
  and fourth inputs of players
  and matchups have conditional
  statements to prevent undefined
  values from populating the 
  inputs.

  The getOptionLabel and 
  isOptionEqualToValue fields
  are used to prevent undefined
  values from populating the inputs
  after the user selects a value.

  Input state variables are used to
  manage the current value of the TextFields 
  in the Autocomplete components, while the 
  main state variables are used to manage the 
  selected value from the dropdown options. 
  
  This is necessary to prevent errors from occurring 
  when a user types in the TextField and then clicks 
  away without selecting an option from the dropdown, 
  which would cause the main state variable to be set 
  to an undefined value that is not present in the 
  dropdown options. 
  
  By using separate state variables for the input 
  value and the selected value, the main state 
  variable only gets set to valid options from the 
  dropdown, while still allowing the user to type 
  freely in the TextField without causing errors.

  Finally, there is a submit button
  to send the inputs to the backend
  microservices for calculation.

  */

  const playerNameComponent = () => {
    return (
      <Autocomplete
        disablePortal
        freeSolo
        size={autoCompleteSize}
        options={playerNamesArray}
        getOptionLabel={(option) =>
          typeof option === "object" && option !== null
            ? option.player_name
            : ''}
        isOptionEqualToValue={(option, value) =>
          option.player_name === value?.player_name
        }
        renderInput={(params) => <TextField {...params} label="Player Full Name" className="whiteAutoComplete" />}
        name="playerFullName"
        title="Enter the name of the player you wish to calculate projected stats for."
        className="whiteAutoComplete"
        value={playerNamesArrayHasEntries ? playerFullName : null}
        inputValue={playerFullNameInput}
        onChange={(event, newValue) => dispatch(setPlayerFullName(newValue))}
        onInputChange={(event, newInputValue) => dispatch(setPlayerFullNameInput(newInputValue))}
      />
    );
  };

  const teamComponent = () => {
    return (<Autocomplete
      disablePortal
      freeSolo
      size={autoCompleteSize}
      options={teamAbbreviationsArray}
      getOptionLabel={(option) =>
        typeof option === "object" && option !== null
          ? option.team_abbreviation
          : ''}
      isOptionEqualToValue={(option, value) =>
        option.team_abbreviation === value?.team_abbreviation
      }
      renderInput={(params) => <TextField {...params} label="Team" className="whiteAutoComplete" />}
      name="team"
      title="Enter the team abbreviation you wish to calculate projected stats for."
      className="whiteAutoComplete"
      value={teamAbbreviationsArrayHasEntries ? team : null}
      inputValue={teamInput}
      onChange={(event, newValue) => dispatch(setTeam(newValue))}
      onInputChange={(event, newInputValue) => dispatch(setTeamInput(newInputValue))}
    />);
  };

  const seasonYearComponent = (season, seasonInput, { setSeason, setSeasonInput }) => {
    return (
      <Autocomplete
        disablePortal
        freeSolo
        size={autoCompleteSize}
        options={years}
        renderInput={(params) => <TextField {...params} label="Season Year" className="whiteAutoComplete" />}
        name="season"
        title="Enter the season year you wish to calculate projected stats for."
        className="whiteAutoComplete"
        value={season}
        inputValue={seasonInput}
        onChange={(event, newValue) => setSeason(newValue)}
        onInputChange={(event, newInputValue) => setSeasonInput(newInputValue)}
      />
    );
  };

  const seasonTypeComponent = (seasonType, seasonTypeInput, { setSeasonType, setSeasonTypeInput }) => {
    return (
      <Autocomplete
        disablePortal
        freeSolo
        size={autoCompleteSize}
        options={seasonTypes}
        renderInput={(params) => <TextField {...params} label="Season Type" className="whiteAutoComplete" />}
        name="seasonType"
        title="Enter the season type you wish to calculate projected stats for."
        className="whiteAutoComplete"
        value={seasonType}
        inputValue={seasonTypeInput}
        onChange={(event, newValue) => setSeasonType(newValue)}
        onInputChange={(event, newInputValue) => setSeasonTypeInput(newInputValue)}
      />
    );
  };

  const opposingTeamComponent = (opposingTeam, opposingTeamInput, { setOpposingTeam, setOpposingTeamInput }) => {
    return (
      <Autocomplete
        disablePortal
        freeSolo
        size={autoCompleteSize}
        options={finalTeamAbbreviations}
        getOptionLabel={(option) =>
          typeof option === "object" && option !== null
            ? option.team_abbreviation
            : ''}
        renderOption={({ key, ...props }, option) => (
          <li
            key={key}
            {...props}
            style={{
              minHeight: option.team_abbreviation === '' ? 36 : undefined,
            }}
          >
            {option.team_abbreviation}
          </li>
        )}
        isOptionEqualToValue={(option, value) =>
          option.team_abbreviation === value?.team_abbreviation
        }
        renderInput={(params) => <TextField {...params} label="Opposing Team" className="whiteAutoComplete" />}
        name="opposingTeam"
        title="Enter the opposing team abbreviation you wish to calculate projected stats against."
        className="whiteAutoComplete"
        value={teamAbbreviationsArrayHasEntries ? opposingTeam : null}
        inputValue={opposingTeamInput}
        onChange={(event, newValue) => setOpposingTeam(newValue)}
        onInputChange={(event, newInputValue) => setOpposingTeamInput(newInputValue)}
      />
    );
  };

  const recentGamesComponent = (recentGames, { sanitizeRecentGamesInput }) => {
    return (
      <Autocomplete
        disablePortal
        freeSolo
        size={autoCompleteSize}
        options={[]}
        inputValue={recentGames ? recentGames : ''}
        onInputChange={(event, newInputValue) => {
          sanitizeRecentGamesInput({
            target: { value: newInputValue }
          })
        }}
        renderInput={(params) =>
          <TextField {...params}
            label="Recent Games"
            type="number"
            className="whiteAutoComplete"
            title="Enter the number of recent games to consider for projections."
            name="recentGames"
            onKeyDown={handleNonNumberKeys}
            onPaste={handleNonNumberPastes} />}
      />
    );
  };
  /*
  The following return makes the input
  fields for the user to fill.
  */

  return (
    <div>
      <h2><span className="NBAInputsStatSpan">Find NBA Projected Stats</span></h2>
      {!swapInputsToPlayer && <button title="Click this to enter inputs for calculating stats of a player." onClick={setInputsToPlayer}>Switch to Player Projections</button>}
      {!swapInputsToMatchup && <button title="Click this to enter inputs for calculating stats of a team." onClick={setInputsToMatchup}>Switch to Matchup Projections</button>}
      <br />
      <br />
      {swapInputsToPlayer &&
        <form key="playerForm" onSubmit={getPlayerInputs}>
          {playerNameComponent()}
          <br />
          <br />
          {seasonYearComponent(season, seasonInput, { setSeason: (v) => dispatch(setSeason(v)), setSeasonInput: (v) => dispatch(setSeasonInput(v)) })}
          <br />
          <br />
          {seasonTypeComponent(seasonType, seasonTypeInput, { setSeasonType: (v) => dispatch(setSeasonType(v)), setSeasonTypeInput: (v) => dispatch(setSeasonTypeInput(v)) })}
          <br />
          <br />
          {opposingTeamComponent(opposingTeam, opposingTeamInput, { setOpposingTeam: (v) => dispatch(setOpposingTeam(v)), setOpposingTeamInput: (v) => dispatch(setOpposingTeamInput(v)) })}
          <br />
          <br />
          {recentGamesComponent(recentGames, { sanitizeRecentGamesInput })}
          <br />
          <br />
          <button type="submit">Submit</button>
        </form>}
      {swapInputsToMatchup &&
        <form key="matchupForm" onSubmit={getMatchupInputs}>
          {teamComponent()}
          <br />
          <br />
          {seasonYearComponent(seasonM, seasonMInput, { setSeason: (v) => dispatch(setSeasonM(v)), setSeasonInput: (v) => dispatch(setSeasonMInput(v)) })}
          <br />
          <br />
          {seasonTypeComponent(seasonTypeM, seasonTypeMInput, { setSeasonType: (v) => dispatch(setSeasonTypeM(v)), setSeasonTypeInput: (v) => dispatch(setSeasonTypeMInput(v)) })}
          <br />
          <br />
          {opposingTeamComponent(opposingTeamM, opposingTeamMInput, { setOpposingTeam: (v) => dispatch(setOpposingTeamM(v)), setOpposingTeamInput: (v) => dispatch(setOpposingTeamMInput(v)) })}
          <br />
          <br />
          {recentGamesComponent(recentGamesM, { sanitizeRecentGamesInput: sanitizeRecentGamesInputM })}
          <br />
          <br />
          <button type="submit">Submit</button>
        </form>}
    </div>
  );
};

export default Inputs;