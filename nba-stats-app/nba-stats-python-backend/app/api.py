# api.py

# Function: Return data to the frontend based on api call from the frontend.

# Inputs:

# API Call from the frontend.

# Output:

# Data related to the NBA, or data related to user credentials.

# Time complexity: Variable. At best, it is O(1), for when
# there are no rows for nbastatcalculations and nbaplusminus.
# The worst and most likely average case is O(n+m+q+(i*j+x*y)).

# - n, m and q are the rows of the queries of the database for 
# the get_matchup_calculated_stats function of nba_stat_calculator.py.

# - i is the number of player dataframes and j is the number of rows
# within the dataframes.

# - x is the number of opposing player dataframes and y is the number of rows
# within the dataframes.

# This is slightly misleading, if I am being honest. The actual time 
# complexity, when only considering the biggest time sinks of the algorithm,
# is O(max(i*j, x*y)), so basically quadratic time complexity.

# Space complexity: Same as the time complexity. At best, O(1) space is used.
# At worst, O(n+m+q+(i*j+x*y)) space is used. 

# Again, this is slightly misleading. The space boils down to O(max(i*j, x*y)).
# That is the part of the algorithm that takes up the most space.

#################################################################################
# Date modified              Modifier             What was modified             #
# 06/28/2025                 Eram Kabir           Initial Development           #
# 09/15/2025                 Eram Kabir           Finalized V1.0    
#
# 11/02/2025                 Eram Kabir           Finalized V2.0
#
#################################################################################

# Libraries

from fastapi import Depends, Header, Request, Query, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Annotated, Union
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from pkce import generate_pkce
import nba_stat_calculator
import nba_stat_calculator_p
import get_team_wl_ratio_against_opp_team
import asyncio
import asyncpg
import sys
import jwt
import os
import time
import secrets
import redis
import httpx
import numpy as np
import xgboost as xgb
import threading

# One pool of connections will be used to connect to 1 database. The
# database to connect to is a PostgreSQL database (through nba_pool).

nba_pool = None

load_dotenv() #Load sensitive data from .env file

# Connection string for connecting to PostgreSQL.
# The credentials are taken from .env file.

postgres_user = os.getenv("POSTGRES_USER")

connection_string = f"postgresql://{postgres_user}:{os.getenv("POSTGRES_PASSWORD")}\
@localhost/{os.getenv("POSTGRES_DB")}"

# Remaining credentials are taken from 
# the .env file to connect to Google Cloud 
# (Google Cloud will be used for user logins).

google_client_id = os.getenv("GOOGLE_CLIENT_ID")

google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

allowed_provider = os.getenv("ALLOWED_PROVIDER")

oauth_authorize_url = os.getenv("OAUTH_AUTHORIZE_URL")

oauth_token_url = os.getenv("OAUTH_TOKEN_URL")

oauth_userinfo_url = os.getenv("OAUTH_USERINFO_URL")

frontend_url = os.getenv("FRONTEND_URL")

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))

oauth_server_url = os.getenv("OAUTH_SERVER_URL")

code_challenge_method = os.getenv("CODE_CHALLENGE_METHOD")

secure_key = secrets.token_urlsafe(32)

oauth = OAuth() #Google login method

# Initialize OAuth with Google Cloud credentials and links
oauth.register(
    name=allowed_provider,
    client_id=google_client_id,
    client_secret=google_client_secret,
    access_token_url = oauth_token_url,
    authorize_url = oauth_authorize_url,
    server_metadata_url=oauth_server_url,
    client_kwargs={"scope": "openid email profile"}
)

algorithm = os.getenv("ALGORITHM") # Algorithm for user password security.

# The following code initializes variables for
# three regression models used to
# predict points for teams in matchups.

# It also intializes the paths to the
# models, a refresh interval used to
# refresh the models every 30 minutes,
# and a thread lock to ensure the
# models are always available.

pre_model_path = "finalized_pre_players_model.json"

reg_model_path = "finalized_reg_players_model.json"

poffs_model_path = "finalized_poffs_players_model.json"

refresh_interval = 1800

pre_model = None

reg_model = None

poffs_model = None

model_lock = threading.Lock()

# The following function
# loads the regression models
# used to predict team points
# in a matchup.

def load_models():
    global pre_model
    global reg_model
    global poffs_model
    new_pre_model = xgb.XGBRegressor()
    new_reg_model = xgb.XGBRegressor()
    new_poffs_model = xgb.XGBRegressor()
    new_pre_model.load_model(pre_model_path)
    new_reg_model.load_model(reg_model_path)
    new_poffs_model.load_model(poffs_model_path)
    with model_lock:
        pre_model = new_pre_model
        reg_model = new_reg_model
        poffs_model = new_poffs_model

# The following model refreshes
# the regression models
# used to predict
# team points in 
# a matchup.

def models_refresher():
    while True:
        time.sleep(refresh_interval)
        load_models()

@asynccontextmanager # Needed for initializing FastAPI variable down below (will be initialized with lifespan function, also below)

async def lifespan(app: FastAPI): 

    # Set global property on connection pool for PostgreSQL database,
    # needed for the pool to be accessible to the whole app.
    global nba_pool 

    # Initialize a global connection pool for PostgreSQL using the connection
    # string and other parameters (at least 10 connections in the pool, at most
    # 100 connections in the pool, release all connections after 300
    # seconds).

    nba_pool = await asyncpg.create_pool(dsn=connection_string, min_size=10, max_size=100, max_inactive_connection_lifetime=300)
       
    num_conns = 10

    # The following code is used to warm up the connections for
    # the PostgreSQL database, so that quick queries can be done.
    
    async def warmup_min_conns():

        async with nba_pool.acquire() as cur:
    
            await cur.fetch("SELECT * FROM nbaplayerstatsregseason WHERE matchup LIKE 'DEN%' AND season_id = '22024' ORDER BY player_id")

            await cur.fetch("SELECT * FROM nbaplayerstatspreseason WHERE matchup LIKE 'DEN%' AND season_id = '22024' ORDER BY player_id")

            await cur.fetch("SELECT * FROM nbaplayerstatspoffsseason WHERE matchup LIKE 'DEN%' AND season_id = '22024' ORDER BY player_id")

            await cur.fetch("SELECT matchup, wl FROM nbateamstatsregseason WHERE matchup LIKE 'DEN%'")

            await cur.fetch("SELECT matchup, wl FROM nbateamstatspreseason WHERE matchup LIKE 'DEN%'")

            await cur.fetch("SELECT matchup, wl FROM nbateamstatspoffsseason WHERE matchup LIKE 'DEN%'")

            await cur.fetch("SELECT player_name FROM nbaplayers ORDER BY player_name ASC")

            await cur.fetch("SELECT * FROM nbastatcalculations ORDER BY team_abbreviation ASC, player_name ASC")

            await cur.fetch("SELECT plus_minus FROM nbaplusminus ORDER BY team_abbreviation ASC, player_name ASC")

            await cur.fetch("SELECT team_abbreviation FROM nbateamabbreviations ORDER BY team_abbreviation ASC")

            await cur.fetch("SELECT first_team_abbreviation, second_team_abbreviation FROM upcominggames")

            await cur.fetch("SELECT * FROM injurednbaplayers")
    
            await cur.fetch("SELECT team_abbreviation, starter FROM nbastarters")

    await asyncio.gather(*[warmup_min_conns() for _ in range(num_conns)])

    #load regression models for use in calculating
    #team points in a matchup

    load_models() 

    #separate thread for refreshing regression models

    t = threading.Thread(target=models_refresher, daemon=True)

    t.start()

    yield #allow connections to be used in entire app

    await nba_pool.close() #close pool upon deceased lifespan

app = FastAPI(lifespan=lifespan) #Fast API initialization and startup.

# Origins for backend api calls.

origins = [
    "http://localhost:5173",
]

# Cors will be used to allow
# cross-communication.

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
# Session middleware will
# be used to create and
# keep track of a user's
# session.

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    https_only=True,
    same_site="none",
    session_cookie="session"
)

# The following classes are used to define the data types
# of data being sent to and from the backend. This is
# necessary due to FastAPI requiring types for any data
# that is managed.

class statCalculatorParams(BaseModel):
    playerFullName: str
    season: str
    seasonType: str
    opposingTeam: str
    recentGames: str

class matchupCalculatorParams(BaseModel):
    team: str
    season: str
    seasonType: str
    opposingTeam: str
    recentGames: str

class ratioCalculatorParams(BaseModel):
    playerFullName: str
    seasonType: str
    opposingTeam: str

class OAuthRequest(BaseModel):
    code: str
    state: str

# The following code verifies any and all requests
# to the backend. It checks the request headers 
# for a token and scheme. If the token and scheme 
# are there and are valid, the frontend request 
# is processed by the corresponding backend service.
# Otherwise, the request is not processed, and a 401
# error code is sent back.

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    try:
        session_data = jwt.decode(token, secure_key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return session_data

# This function calculates the points
# an NBA team scores in a matchup
# based on historical data

def use_model(features_array: list[Union[int, float]], params: Annotated[matchupCalculatorParams, Query()]) -> Union[int, float]:

    necessary_stat_indices = {1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 15, 16, 17}

    ml_regression_features = [features_array[i] for i in range(len(features_array)) if i in necessary_stat_indices]

    fgm = ml_regression_features[0]

    fga = ml_regression_features[1]

    fg3m = ml_regression_features[2]

    fg3a = ml_regression_features[3]

    ftm = ml_regression_features[4]

    fta = ml_regression_features[5]

    ast = ml_regression_features[8]

    fgm_rate = nba_stat_calculator_p.round_to_two_decimal_places(fgm/fga) if fga else 0

    fg3m_rate = nba_stat_calculator_p.round_to_two_decimal_places(fg3m/fg3a) if fg3a else 0

    ftm_rate = nba_stat_calculator_p.round_to_two_decimal_places(ftm/fta) if fta else 0

    fga_rate = nba_stat_calculator_p.round_to_two_decimal_places(fg3a/fga) if fga else 0

    fta_rate = nba_stat_calculator_p.round_to_two_decimal_places(fta/fga) if fga else 0

    ast_rate = nba_stat_calculator_p.round_to_two_decimal_places(ast/fgm) if fgm else 0

    ml_regression_features.append(fgm_rate)
    ml_regression_features.append(fg3m_rate)
    ml_regression_features.append(ftm_rate)
    ml_regression_features.append(fga_rate)
    ml_regression_features.append(fta_rate)
    ml_regression_features.append(ast_rate)

    ml_regression_features = [ml_regression_features]

    if params.seasonType == "Regular Season":

        ml_regression_model = reg_model

    elif params.seasonType == "Playoffs":

        ml_regression_model = poffs_model

    else:

        ml_regression_model = pre_model

    predicted_team_points = ml_regression_model.predict(ml_regression_features)

    return predicted_team_points[0]

# function to process arrays of
# player names stored as numbers

# meant to convert numbers of player
# names to actual strings

def convert_name_nums_to_strings(player_names_list: list[list[list[int]]], num_iterations: int=1) -> list[list[str]]:

    player_names_ = []

    for index in range(len(player_names_list)):

        player_name_nums = player_names_list[index][0]

        player_name_nums_to_convert = []

        for j in range(len(player_name_nums)):

            name_num = player_name_nums[j]

            if name_num:

                player_name_nums_to_convert.append(name_num)

        player_name = bytes(player_name_nums_to_convert).decode("utf8")

        for j in range(num_iterations):

            player_names_.append(player_name)

    return player_names_

# Just a long string used for pulling
# last game data for a matchup from a 
# database with asyncpg

def query_last_game_string(param: str):

    query_string = "SELECT minutes, points, \
    field_goals_made, field_goals_attempted, field_goals_percentage, \
    field_goal_threes_made, field_goal_threes_attempted, \
    field_goal_threes_percentage, free_throws_made, free_throws_attempted, \
    free_throws_percentage, offensive_rebounds, defensive_rebounds, rebounds, \
    assists, turnovers, steals, blocks, personal_fouls, plus_minus, player_id \
    FROM nbaplayerstats" + param + " \
    WHERE LEAST(home_team, away_team) = LEAST($1, $2) \
    AND GREATEST(home_team, away_team) = GREATEST($1, $2) \
    AND game_date = ( \
    SELECT MAX(game_date) \
    FROM nbaplayerstats" + param + " \
    WHERE LEAST(home_team, away_team) = LEAST($1, $2) \
    AND GREATEST(home_team, away_team) = GREATEST($1, $2) \
    ) \
    ORDER BY season_id DESC, game_date DESC, matchup DESC, points DESC\
    "

    return query_string

# The oauth login service allows the user
# to login with their google account, upon
# which the service contacts the exchange
# service below.

@app.get("/oauth/login")
async def oauth_login(request: Request):
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(32)
    redis_client.setex(
        f"oauth_state:{state}",
        300,            
        verifier
    )
    url = (
        f"{oauth_authorize_url}"
        f"?response_type=code"
        f"&client_id={google_client_id}"
        f"&redirect_uri={frontend_url}"
        f"&scope=openid%20email%20profile"
        f"&code_challenge={challenge}"
        f"&code_challenge_method={code_challenge_method}"
        f"&state={state}"
    )

    return RedirectResponse(url)

# The oauth exchange service takes
# the user's login data, verifies
# that the user has logged in, and
# then issues a token for the user
# of the website, which is sent to
# the frontend. 

@app.post("/oauth/exchange")
async def exchange_code(request: Request, data: OAuthRequest):
    key = f"oauth_state:{data.state}"
    verifier = redis_client.get(key).decode("utf-8")

    if not verifier:
        return {"error": "invalid_or_expired_state"}
    redis_client.delete(key)

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            oauth_token_url,
            data={
                "grant_type": "authorization_code",
                "code": data.code,
                "redirect_uri": frontend_url,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "code_verifier": verifier,
            },
        )
        token_data = token_resp.json()
        userinfo_resp = await client.get(
            oauth_userinfo_url,
            headers={
                "Authorization": f"Bearer {token_data["access_token"]}"
            },
        )
        user = userinfo_resp.json()
    
    jwt_payload = {
        "sub": user["sub"],
        "email": user["email"],
        "exp": int(time.time()) + 600,
    }

    username, email = user.get("name"), user.get("email")

    async with nba_pool.acquire() as cur:

        await cur.execute("INSERT INTO users (username, email) \
                          VALUES ($1, $2) \
                          ON CONFLICT (username, email) DO NOTHING", username, email)

    app_token = jwt.encode(jwt_payload, secure_key, algorithm=algorithm)

    return JSONResponse(content={"token": app_token, "email": email, "user": username})

# This function returns a list of
# dictionaries of all NBA player names
# to the website.

@app.get("/playernames", status_code=200)
async def get_player_names(current_user: dict = Depends(get_current_user)):
    
    async with nba_pool.acquire() as cur:

        player_names = await cur.fetch("SELECT player_name \
                                       FROM nbaplayers \
                                       ORDER BY player_name ASC")
    
        player_names = [dict(row) for row in player_names]

        return player_names
    
# This function returns a list of 
# dictionaries of all NBA player 
# stats to the website.

@app.get("/playerstats", status_code=200)
async def get_player_stats(current_user: dict = Depends(get_current_user)):
    
    async with nba_pool.acquire() as cur:

        upcoming_matchups_player_stats = await cur.fetch("SELECT nsc.team_abbreviation, \
                                                         nsc.player_name, \
                                                         nsc.minutes, \
                                                         nsc.field_goals_made, \
                                                         nsc.field_goals_attempted, \
                                                         nsc.field_goals_percentage, \
                                                         nsc.field_goal_threes_made, \
                                                         nsc.field_goal_threes_attempted, \
                                                         nsc.field_goal_threes_percentage, \
                                                         nsc.free_throws_made, \
                                                         nsc.free_throws_attempted, \
                                                         nsc.free_throws_percentage, \
                                                         nsc.offensive_rebounds, \
                                                         nsc.defensive_rebounds, \
                                                         nsc.rebounds, \
                                                         nsc.assists, \
                                                         nsc.steals, \
                                                         nsc.blocks, \
                                                         nsc.turnovers, \
                                                         nsc.personal_fouls, \
                                                         nsc.points \
                                                         FROM nbastatcalculations nsc \
                                                         INNER JOIN nbaplusminus npm \
                                                         ON nsc.player_name=npm.player_name \
                                                         AND nsc.team_abbreviation=npm.team_abbreviation \
                                                         ORDER BY nsc.team_abbreviation ASC, nsc.player_name ASC")

        upcoming_matchups_pm_stats = await cur.fetch("SELECT npm.plus_minus \
                                                     FROM nbaplusminus npm \
                                                     INNER JOIN nbastatcalculations nsc \
                                                     ON npm.player_name=nsc.player_name \
                                                     AND npm.team_abbreviation=nsc.team_abbreviation \
                                                     ORDER BY npm.team_abbreviation ASC, npm.player_name ASC")        
        
        upcoming_matchups_all_stats = [dict(upcoming_matchups_player_stats[i]) |
                                       dict(upcoming_matchups_pm_stats[i]) 
                                       for i in range(len(upcoming_matchups_player_stats))]

        return upcoming_matchups_all_stats
    
# This function returns a list of 
# dictionaries of all NBA team
# abbreviations to the website.

@app.get("/teamabbreviations", status_code=200)
async def get_teams(current_user: dict = Depends(get_current_user)):
    
    async with nba_pool.acquire() as cur:

        team_names = await cur.fetch("SELECT team_abbreviation \
                                     FROM nbateamabbreviations \
                                     ORDER BY team_abbreviation ASC")
    
        team_names = [dict(row) for row in team_names]
                                            
        return team_names
    
# This function returns a list of 
# dictionaries of all NBA team
# abbreviations for upcoming games
# to the website.

@app.get("/upcominggameteams", status_code=200)
async def get_teams_in_matchup(current_user: dict = Depends(get_current_user)):
    
    async with nba_pool.acquire() as cur:

        team_names_for_upcoming_matchups = await cur.fetch("SELECT first_team_abbreviation, second_team_abbreviation \
                                                           FROM upcominggames \
                                                           ORDER BY game_datetime \
                                                           LIMIT 5")
    
        team_names_for_upcoming_matchups = [dict(row) for row in team_names_for_upcoming_matchups]

        return team_names_for_upcoming_matchups

# The following function gets an NBA player's
# stats. It first checks if a season is
# provided, and returns an error number if 
# this is not the case. If the recent games
# parameter is not provided, it assumes all of
# the player's games need to be considered 
# when calculating a player's stats.

# A function from the nba_stat_calculator.py file
# is then called to calculate the NBA player's
# stats. The results of this function, which is
# a dictionary of stats, is returned.

async def get_player_calculated_stats(params: Annotated[statCalculatorParams, Query()]):
    if not params.season:
        return 3
    elif not params.recentGames:
        params.recentGames = sys.maxsize
    elif params.opposingTeam == '':
        params.opposingTeam = 'n'
    
    params.recentGames = int(params.recentGames)

    async with nba_pool.acquire() as cur:

        player_calculated_stats = await nba_stat_calculator_p.player_stat_avg_hm(params.playerFullName, 
                                                                                 params.season, 
                                                                                 params.seasonType, 
                                                                                 params.opposingTeam, 
                                                                                 params.recentGames, 
                                                                                 cur)

        return player_calculated_stats
    
# The following function gets an NBA matchup's
# stats. It first checks if a season is
# provided, and returns an error number if 
# this is not the case. If the recent games
# parameter is not provided, it assumes all of
# the player's games need to be considered 
# when calculating a player's stats.

# A function from the nba_stat_calculator_p.py file
# is then called to pull the necessary data for
# matchup calculations. If the team_abbreviation
# is an integer, then that means the data was not
# found, and as such, an error is thrown.
# Another function is then called from 
# nba_stat_calculator.pyx to perform the
# calculations. If the error variable returned by
# the function is true, then the matchup was not
# able to be calculated, and an error is thrown.
# Otherwise, all the results returned by the
# function are compressed into 1D lists, and the
# byte results are converted into strings.
# Finally, the cleaned results are stored 
# into a dictionary that is returned by the
# function.

# Note: the team_abbreviation_list and the
# opp_team_abbreviation_list are simply lists
# of one abbreviation repeated multiple times.
# That is why the list is only indexed into
# once. This will be fixed later, but for now,
# it is not a major area of concern.

async def get_matchup_calculated_stats(params: Annotated[matchupCalculatorParams, Query()]):
    if not params.season:
        return 3
    elif not params.recentGames:
        params.recentGames = sys.maxsize

    params.recentGames = int(params.recentGames)

    async with nba_pool.acquire() as cur:
   
        stat_arrays = await nba_stat_calculator_p.calculate_player_stats_arrays(params.team, 
                                                                                params.season, 
                                                                                params.seasonType, 
                                                                                params.opposingTeam, 
                                                                                cur)

        if isinstance(stat_arrays[0], int):

            return stat_arrays[0]
        
        calculated_stats_lists = nba_stat_calculator.calculate_matchup_stats(params.team, 
                                                                             params.season, 
                                                                             params.seasonType, 
                                                                             params.opposingTeam, 
                                                                             params.recentGames, 
                                                                             *stat_arrays)
        
        team_abbreviation_list = calculated_stats_lists[0]

        player_names_list = calculated_stats_lists[1]

        player_stats_list = calculated_stats_lists[2]

        opp_team_abbreviation_list = calculated_stats_lists[3]

        opp_player_names_list = calculated_stats_lists[4]

        opp_player_stats_list = calculated_stats_lists[5]

        error = calculated_stats_lists[6]

        if error:
            
            return team_abbreviation_list[0][0]

        np_player_stats_list = np.array(player_stats_list, dtype=float)

        np_opp_player_stats_list = np.array(opp_player_stats_list, dtype=float)

        player_names_ = convert_name_nums_to_strings(player_names_list)

        opp_player_names_ = convert_name_nums_to_strings(opp_player_names_list)

        players_from_last_game = await get_last_game_stats(params)

        indices_of_relevant_players = [i for i in range(len(player_names_)) 
                                       if player_names_[i] in players_from_last_game]

        indices_of_relevant_opp_players = [i for i in range(len(opp_player_names_)) 
                                           if opp_player_names_[i] in players_from_last_game]

        np_player_stats_list = np_player_stats_list[indices_of_relevant_players]

        np_opp_player_stats_list = np_opp_player_stats_list[indices_of_relevant_opp_players]

        np_player_stats_list = np.nansum(np_player_stats_list, axis=0)

        np_opp_player_stats_list = np.nansum(np_opp_player_stats_list, axis=0)
        
        team_pts = use_model(np_player_stats_list, params)

        opp_team_pts = use_model(np_opp_player_stats_list, params)

        num_stats = 20

        team_abbreviation_list = [bytes(team_abbreviation_list[0]).decode("utf8")]
        
        player_names_list = convert_name_nums_to_strings(player_names_list, 
                                                         num_iterations=num_stats)

        stat_names = ["MIN",
                      "FGM",
                      "FGA",
                      "FG_PCT",
                      "FG3M",
                      "FG3A",
                      "FG3_PCT",
                      "FTM",
                      "FTA",
                      "FT_PCT",
                      "OREB",
                      "DREB",
                      "REB",
                      "AST",
                      "STL",
                      "BLK",
                      "TOV",
                      "PF",
                      "PTS",
                      "PLUS_MINUS"]

        stat_names_for_players_list = stat_names*len(player_names_list)

        player_stats_list = [player_stats_list[index][i] 
                             for index in range(len(player_stats_list)) 
                             for i in range(num_stats)]
        
        opp_team_abbreviation_list = [bytes(opp_team_abbreviation_list[0]).decode("utf8")]
        
        opp_player_names_list = convert_name_nums_to_strings(opp_player_names_list, num_iterations=num_stats)

        stat_names_for_opp_players_list = stat_names*len(opp_player_names_list)

        opp_player_stats_list = [opp_player_stats_list[index][i] 
                                 for index in range(len(opp_player_stats_list)) 
                                 for i in range(num_stats)]

        returned_player_stats_len = len(player_stats_list)

        returned_opp_player_stats_len = len(opp_player_stats_list)

        max_num_of_returned_player_stats = max(returned_player_stats_len, returned_opp_player_stats_len)

        matchup_stats = {}

        team_abb = team_abbreviation_list[0]

        opp_team_abb = opp_team_abbreviation_list[0]

        matchup_stats[team_abb] = {}

        matchup_stats[opp_team_abb] = {}

        for i in range(max_num_of_returned_player_stats):

            if i < returned_player_stats_len:

                player_name = player_names_list[i]

                stat_name = stat_names_for_players_list[i]

                player_stat = player_stats_list[i]

                if player_name not in matchup_stats[team_abb]:

                    matchup_stats[team_abb][player_name] = {}

                matchup_stats[team_abb][player_name][stat_name] = player_stat

            if i < returned_opp_player_stats_len:

                opp_player_name = opp_player_names_list[i]

                opp_stat_name = stat_names_for_opp_players_list[i]

                opp_player_stat = opp_player_stats_list[i]

                if opp_player_name not in matchup_stats[opp_team_abb]:

                    matchup_stats[opp_team_abb][opp_player_name] = {}

                matchup_stats[opp_team_abb][opp_player_name][opp_stat_name] = opp_player_stat

        return matchup_stats, players_from_last_game, team_pts, opp_team_pts
    
# The following function gets an NBA matchup's
# win-loss ratio.

# A function is called from the get_team_wl_
# ratio_against_opp_team.py file, to calculate 
# the win-loss ratio of the matchup. The result,
# a dictionary containing the matchup's win-loss
# ratio, is returned.

async def get_wl_ratio_for_matchup(params: Annotated[matchupCalculatorParams, Query()]):

    async with nba_pool.acquire() as cur:

        ratio_stats = await get_team_wl_ratio_against_opp_team.get_team_wl_ratio_against_opp_team(params.team, 
                                                                                                  params.seasonType, 
                                                                                                  params.opposingTeam, 
                                                                                                  cur)
        
        return ratio_stats

# This function retrieves all the player stats
# for a matchup's last game.

async def get_last_game_stats(params: Annotated[matchupCalculatorParams, Query()]):

    table_names_hm = {"Pre Season": "preseason", "Regular Season": "regseason", "All Star": "astars", "Playoffs": "poffs"}

    async with nba_pool.acquire() as cur:
        
        last_game_query_string = query_last_game_string(table_names_hm[params.seasonType])

        last_game_players_stats = await cur.fetch(last_game_query_string, params.team, params.opposingTeam)

        last_game_players_stats = [dict(row) for row in last_game_players_stats]

        player_ids_to_player_hm = nba_stat_calculator_p.player_ids_to_player()

        last_game_players_stats = {player_ids_to_player_hm[row["player_id"]]: row for row in last_game_players_stats}

        return last_game_players_stats

# This function retrieves all the players
# that are currently injured in the NBA.

async def get_injured_players():

    async with nba_pool.acquire() as cur:

        injured_players = await cur.fetch("SELECT * FROM injurednbaplayers")

        injured_players_set = {row["player_name"] for row in injured_players}

        injured_players = {"injured_players": injured_players_set}

        return injured_players

# This function retrieves all the players
# that are starting for a matchup.

async def get_starters(params: Annotated[matchupCalculatorParams, Query()]):

    async with nba_pool.acquire() as cur:

        starters = await cur.fetch("SELECT team_abbreviation, starter \
                                   FROM nbastarters \
                                   WHERE team_abbreviation \
                                   IN ($1, $2)", params.team, params.opposingTeam)

        starters_hm = {}

        for row in starters:

            if row["team_abbreviation"] not in starters_hm:

                starters_hm[row["team_abbreviation"]] = set()

            starters_hm[row["team_abbreviation"]].add(row["starter"])

        return starters_hm

# This function calls the get_player_calculated_stats
# function and returns the result to the website.

@app.get("/calculatedplayerstats", status_code=200)
async def get_player_stats(params: Annotated[statCalculatorParams, Query()], current_user: dict = Depends(get_current_user)):
    player_stats = await get_player_calculated_stats(params)
    return player_stats

# This function calls the get_matchup_calculated_stats,
# get_wl_ratio_for_matchup, get_injured_players and
# get_starters functions, and then returns
# their results, combined into one dictionary, to the
# website.

# If opposing team is empty, then the functions will
# return error codes to halt progression of data
# collection.

@app.get("/calculatedmatchupstats", status_code=200)
async def get_matchup_stats(params: Annotated[matchupCalculatorParams, Query()], current_user: dict = Depends(get_current_user)):
    if params.opposingTeam == '':
        params.opposingTeam = 'n'
    matchup_stats, ratio_stats, injured_players, starters_hm = await asyncio.gather(
        get_matchup_calculated_stats(params),
        get_wl_ratio_for_matchup(params),
        get_injured_players(),
        get_starters(params)
    )

    if isinstance(matchup_stats, int):

        return {"matchup_stats": matchup_stats, "ratio_stats": matchup_stats}

    elif isinstance(ratio_stats, int):

        return {"matchup_stats": ratio_stats, "ratio_stats": ratio_stats}

    matchup_stats, last_game_stats, team_pts, opp_team_pts = matchup_stats

    team_pts = int(team_pts)

    opp_team_pts = int(opp_team_pts)

    return {"matchup_stats": matchup_stats, 
            "ratio_stats": ratio_stats, 
            "last_game_stats": last_game_stats, 
            "injured_nba_players": injured_players, 
            "starters": starters_hm, 
            "team_points": team_pts, 
            "opposing_team_points": opp_team_pts}
