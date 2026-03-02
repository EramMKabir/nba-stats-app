# NBA Stats App

<a name="readme-top"></a>

<div align="center">

[![Contributors][contributors-shield]][contributors-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<br />

  <a href="https://github.com/EramMKabir/nba-stats-app">
    <img src="nba-stats-app/nba-stats-frontend/nba-stats-app-logo.png" alt="Logo" width="100" height="100">
  </a>

<br />

</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-this-project">About this Project</a>
      <ul>
        <li><a href="#features">Features</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href=#getting-started>Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
  </ol>
</details>

<br />

## About this Project

**NBA Stats App** is a stats calculation app for determining NBA matchup outcomes and player stats.

### Features

* **Modular Stat Calculations**: Calculate stats for NBA players based on opposing team performance, recent games, season, type of season, etc.

* **Matchup Predictions with XGBoost** Predict matchup outcomes for the NBA using XGBoost Regressor, trained on historical data.

* **Upcoming Game Stats** View the latest upcoming games for the NBA, complete with player stats.

* **Secure User Authentication** View the NBA stats you need with secure login through OAuth2.

* **Fast Performance** Calculate the stats you need, as soon as you need them.

<p align="right">(<a href="#readme-top">Back to Top</a>)</p>

### Built With:

[![React][React]][React-url]
[![Redux][Redux]][Redux-url]
[![Playwright][Playwright]][Playwright-url]
[![JavaScript][JavaScript]][JavaScript-url]
[![FastAPI][FastAPI]][FastAPI-url]
[![Python][Python]][Python-url]
[![Cython][Cython]][Cython-url]
[![XGBoost][XGBoost]][XGBoost-url]
[![Google Cloud Platform][Google Cloud Platform]][Google Cloud Platform-url]
[![PostgreSQL][PostgreSQL]][PostgreSQL-url]
[![nba_api][nba_api]][nba_api-url]
[![OAuth2][OAuth2]][OAuth2-url]

## App in Action

<div align="center">
  <div style="margin-bottom: 20px;">
    <p><strong>Logging in with Google</strong></p>
    <img src="nba-stats-app/nba-stats-frontend/gifs/LoggingIn.gif" width="75%">
  </div>
  <div style="margin-bottom: 20px;">
    <p><strong>Calculating Player Stats</strong></p>
    <img src="nba-stats-app/nba-stats-frontend/gifs/PlayerStatsCalculation.gif" width="75%">
  </div>
  <div style="margin-bottom: 20px;">
    <p><strong>Calculating Matchup Stats</strong></p>
    <img src="nba-stats-app/nba-stats-frontend/gifs/TeamStatsCalculation.gif" width="75%">
  </div>
  <div style="margin-bottom: 20px;">
    <p><strong>Seeing Upcoming Games and Stats</strong></p>
    <img src="nba-stats-app/nba-stats-frontend/gifs/UpcomingGames.gif" width="75%">
  </div>
</div>

## Getting Started

### Prerequisites

For this app, you'll need:

* Python (latest version is preferred)
* npm
* Vite
* Cython
* Databases with nba_api data

### Installation

1. Install a database client for PostgreSQL, then
   install psql and use the following command:

   ```sh
   psql -U yourusername -d yourdatabasename -f /path/to/schemas.sql
   ```

2. Clone this repository:

   ```sh
   git clone https://github.com/EramMKabir/nba-stats-app.git
   ```
   Open Directory:

   ```sh
   cd nba-stats-app
   ```

3. Setup the backend:

   ```sh
   cd nba-stats-python-backend
   python -m venv .venv
   source .venv/bin/activate
   ```

   Install the Python packages:

   ```sh
   pip install -r requirements.txt
   python main.py
   ```

   Compile the .pyx file:

   ```sh
   python setup.py build_ext --inplace
   ```

   Then run the server:

   ```sh
   uvicorn main:app
   ```

4. Setup the frontend:

   Open a new terminal and navigate to nba-stats-frontend:

   ```sh
   cd nba-stats-frontend
   ```

   Install NPM packages and start the server:

   ```sh
   npm install
   npm run dev
   ```

5. Setup redis-server:

   Install redis if not present:

   ```sh
   brew install redis
   ```

   Then run the server:

   ```sh
   redis-server
   ```

6. Setup Google Cloud Platform URI.
   Make sure to go to Google Cloud
   Platform, setup a Client ID, and
   add the URL of your frontend to
   the Client.

7. Make sure to setup the proper
   .env variables in both 
   .env.example files,
   and rename both files to .env.
   Here are explanations for some
   of the variables:

   SECRET/SESSION_SECRET: Long, random
   strings used for starting user sessions.

   REDIS_URL: The url for hosting
   redis-server, which hosts user sessions.

   GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET:
   When setting up the URI in the Installation
   steps, you will be presented with an ID
   and Secret from Google. Those are what
   should be in these variables.

   OAUTH_URLS: OAuth based URLS, for logging
   a user in with an established email provider.

   PROVIDER: The email provider mentioned in 
   OAUTH_URLS above, used to log users in.

   ALGORITHM: JWT signing algorithm, used to
   initiate token authentication.

   CODE_CHALLENGE_METHOD: Used to provide
   security to the token authentication.

<p align="right">(<a href="#readme-top">Back to Top</a>)</p>

[contributors-shield]: https://img.shields.io/github/contributors/EramMKabir/nba-stats-app?style=for-the-badge

[contributors-url]: https://github.com/EramMKabir/nba-stats-app/graphs/contributors

[stars-shield]: https://img.shields.io/github/stars/EramMKabir/nba-stats-app?style=for-the-badge

[stars-url]: https://github.com/EramMKabir/nba-stats-app/stargazers

[issues-shield]: https://img.shields.io/github/issues/EramMKabir/nba-stats-app?style=for-the-badge

[issues-url]: https://github.com/EramMKabir/nba-stats-app/issues

[license-shield]: https://img.shields.io/github/license/EramMKabir/nba-stats-app?style=for-the-badge

[license-url]: https://github.com/EramMKabir/nba-stats-app/blob/main/LICENSE

[linkedin-shield]: https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white

[linkedin-url]: https://www.linkedin.com/in/eram-kabir/

[React]: https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB

[React-url]: https://react.dev/

[Redux]: https://img.shields.io/badge/redux-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB

[Redux-url]: https://redux.js.org

[Playwright]: https://img.shields.io/badge/playwright-%2320232a.svg?style=for-the-badge&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAAlwSFlzAAABLgAAAS4Be3EaTQAAAQtQTFRFR3BMLqwzLqczNF9J01RLMEZTH5EkK6gxIpIoWElO0VNJK54y2VNILEpPIJMmLqwznE5MLLIsLqwzLa0z2FRJyVNKLkZRLERRhExNLUVSLKsyIpAoKYo2PYYqLEpRIZcnLq0yLUVSJYwsLUNR2lRJLntCLq0yLpk5La0ze282Lqw0Ip0qLURSLUVSLqwz11FKdUpNK0NVLq0zL6wyJ28/LVNTK6ozH6MzL60zqVBLTkVSJJco2FdKKI4mrlFMKWlBL6g0LUVR41dLLV5KLUVSMkdUJ15IJ4A1J3g5K1tIHY0iLq0z1lNIy09EH5IkJosk4VZLKKMtol493FVKI5oot1pCUH8uwE1BJp0qzOOdyQAAAEp0Uk5TAOgyBLdn+mziDuvJ9vDz88IHidbl31mNlrD96ZH6ntDFQd851sK/uUj+skIi3WAmsCqcVpYiHhmfpoa4df7R3tvVUtbXtFzZ3+Aggez3AAABPUlEQVQ4y92T11rCQBSEk5AmSYiGkAJIkY6AvRew62YTQWzv/yRuS0Q/4F7ndv7szjmz4bh/p5SqrS0F9gHIbC7xVzYA0tnRQsC7wACIykpq3ufX4htgiszKsWXtdrNt4ti6Xbd1OB6/xMBrwLSHgV4aEo2nHQBkNYOASQwIZLYcBabwHRQcqY+S5pmfp0OvIjct5mC4jk4oFw05CgKTx0CFxjuFUNw6hzB8TiK0Src3CLEosMNCJMAkaCpCqcEisDtmARJhpAXZeAWSjn3xTgbg4bGAI1ApSUf4CJHbxiHv3f5TQzOxz38XV0OT1vUQLwqV1ZN8ozV7AL6E5PwgIdRBe9BFfvNHIc4lTtkhRdAA/OGvriTvxDPwnj+pL8zr2zEKrIisMP9FVK+G6sjkteLBwldZdX3frf21n+kLpsJVnjlZdhUAAAAASUVORK5CYII=&logoColor=%2361DAFB

[Playwright-url]: https://playwright.dev

[JavaScript]: https://img.shields.io/badge/javascript-%2320232a.svg?style=for-the-badge&logo=javascript&logoColor=%2361DAFB

[JavaScript-url]: https://www.javascript.com

[FastAPI]: https://img.shields.io/badge/fastapi-3670A0.svg?style=for-the-badge&logo=fastapi&logoColor=ffdd54

[FastAPI-url]: https://fastapi.tiangolo.com

[Python]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54

[Python-url]: https://www.python.org/

[Cython]: https://img.shields.io/badge/cython-3670A0?style=for-the-badge&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAgCAMAAABAUVr7AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAAlwSFlzAAACaAAAAmgBN/2/ewAAAMxQTFRFR3BMZGRkbGxsZGRk/+VpZGRkZGRkZGRkZmZmZGRkZmZmZWVlZGRk/9lIZGRkZGRkN3KiM22d/9xPZGRk/9lGXmVrZGRkZGRkU3ubbm5uRIO0/+hy/+ZrOXWl/9hKZWVl/9Y/oaGh/+Nl/udzMWua/9U9ZGRkSYm7SYm8Q4GyQHmi/9U/bnqASYm6Roa4/+Vq/9dDN2+a/9dD/9Y/SIm7/9Q6R4W4ZGRkP32u/9tNPHip/+Jg/95XQ4K0/+hx/9ZBNXCfOXSlR4e5MGqZp6n8eQAAADd0Uk5TAPES5f531ChaG0Uzmt/6yNmpjK9yBoamCQLruteRBWj2H8h459a6q9NpY74OHEefTngcHllYgqUactcAAAHUSURBVDjLZZTrYoIwDIULyEVkyFQQnYjTeddNd3PMC8re/52WJmHCPL9K+dqcpGmFuMqM23VN2bmK0QxsX9xI1Y1dUYpTKwMdXdndqF0tENV6vnbiBM5Ey7+sP6LGc227Q3vajkszQU5QEAODh+t1KOfYmU5GaQ8DIq+n3ex4/OpGoVCZwVhNimvCcDqbA/H1fYnAH61UYKVd2HH26XclcfHgw6IfTSEoGWWFyJGI8xM6IAmTk0Fb7/P5fPF9OROSSyckFu+zLJM+JPHzNDpVXvqMTAipPWeZTIYIRCotRji36vRKAOI1KpX9kBEubIgFQatA/Gx7+/3hwJG40iER3j1q8SKJ5JUQPuEVEtHoQWq4ByJJkreSF1UWxBudQOBCbpGkg345oylYjYZFIl2y3YBP6xmSiXp/ABDphhE+IkcsPG/bk8QdaZyXRfjkV8Nm6kmfDVCr1LYObWMTgi7Gg7sSYlJl6nI85Exa43L3B9f2apHPBvqgVjNkm/pUGk223WY5SNPB8gOGMc66dJu4BZER/dc3rFjsXltX2uE21VX1UWrVMSmKa91cNaWtW7YVB/yp2QXLPl9Yt3hhner/a6/9u/bm7dsgajo+Hgo8Hnrh8fgFwll7OfJ+FK4AAAAASUVORK5CYII=&logoColor=ffdd54

[Cython-url]: https://www.cython.org/

[XGBoost]: https://img.shields.io/badge/xgboost-3670A0?style=for-the-badge

[XGBoost-url]: https://xgboost.ai

[Google Cloud Platform]: https://img.shields.io/badge/Google%20Cloud%20Platform-3670A0?style=for-the-badge&logo=google%20cloud&logoColor=ffdd54

[Google Cloud Platform-url]: https://cloud.google.com

[PostgreSQL]: https://img.shields.io/badge/postgresql-4169e1?style=for-the-badge&logo=postgresql&logoColor=white

[PostgreSQL-url]: https://www.postgresql.org

[nba_api]: https://img.shields.io/badge/nba_api-3670A0?style=for-the-badge

[nba_api-url]: https://github.com/swar/nba_api

[OAuth2]: https://img.shields.io/badge/oauth2-3670A0?style=for-the-badge

[OAuth2-url]: https://oauth.net/2/