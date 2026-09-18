from datetime import timedelta

DOMAIN = "nfl"
STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings"
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
UPDATE_INTERVAL = timedelta(minutes=5)

SENSOR_TYPES = (
    ("standings", "NFL Classement Complet", "nfl_standings_flat"),
    ("preseason_standings", "NFL Classement Pre-saison", "nfl_preseason_standings_flat"),
    ("global_standings", "NFL Classement Global", "nfl_standings_global"),
    ("games", "NFL Matchs Du Jour", "nfl_games_today"),
    ("preseason_games", "NFL Matchs Pre-saison", "nfl_preseason_games_today"),
)