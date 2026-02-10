
# NBA Team ID Mappings
# Maps various string representations (Full Name, Abbreviation, Mascot, City) to valid Integer IDs.

TEAM_MAP = {
    # Atlanta Hawks
    "atlanta hawks": 5, "hawks": 5, "atl": 5, "atlanta": 5,
    # Boston Celtics
    "boston celtics": 6, "celtics": 6, "bos": 6, "boston": 6,
    # Brooklyn Nets
    "brooklyn nets": 38, "nets": 38, "bkn": 38, "brooklyn": 38,
    # Charlotte Hornets
    "charlotte hornets": 41, "hornets": 41, "cha": 41, "charlotte": 41,
    # Chicago Bulls
    "chicago bulls": 22, "bulls": 22, "chi": 22, "chicago": 22,
    # Cleveland Cavaliers
    "cleveland cavaliers": 7, "cavaliers": 7, "cavs": 7, "cle": 7, "cleveland": 7,
    # Dallas Mavericks
    "dallas mavericks": 14, "mavericks": 14, "mavs": 14, "dal": 14, "dallas": 14,
    # Denver Nuggets
    "denver nuggets": 16, "nuggets": 16, "den": 16, "denver": 16,
    # Detroit Pistons
    "detroit pistons": 26, "pistons": 26, "det": 26, "detroit": 26,
    # Golden State Warriors
    "golden state warriors": 21, "warriors": 21, "gsw": 21, "golden state": 21, "dubs": 21,
    # Houston Rockets
    "houston rockets": 15, "rockets": 15, "hou": 15, "houston": 15,
    # Indiana Pacers
    "indiana pacers": 2, "pacers": 2, "ind": 2, "indiana": 2,
    # LA Clippers
    "la clippers": 18, "clippers": 18, "lac": 18,
    # Los Angeles Lakers
    "los angeles lakers": 12, "lakers": 12, "lal": 12, "l.a. lakers": 12,
    # Memphis Grizzlies
    "memphis grizzlies": 11, "grizzlies": 11, "mem": 11, "memphis": 11,
    # Miami Heat
    "miami heat": 20, "heat": 20, "mia": 20, "miami": 20,
    # Milwaukee Bucks
    "milwaukee bucks": 25, "bucks": 25, "mil": 25, "milwaukee": 25,
    # Minnesota Timberwolves
    "minnesota timberwolves": 1, "timberwolves": 1, "wolves": 1, "min": 1, "minnesota": 1,
    # New Orleans Pelicans
    "new orleans pelicans": 10, "pelicans": 10, "nop": 10, "new orleans": 10,
    # New York Knicks
    "new york knicks": 9, "knicks": 9, "nyk": 9, "new york": 9,
    # Oklahoma City Thunder
    "oklahoma city thunder": 13, "thunder": 13, "okc": 13, "oklahoma city": 13,
    # Orlando Magic
    "orlando magic": 4, "magic": 4, "orl": 4, "orlando": 4,
    # Philadelphia 76ers
    "philadelphia 76ers": 17, "76ers": 17, "sixers": 17, "phi": 17, "philadelphia": 17,
    # Phoenix Suns
    "phoenix suns": 24, "suns": 24, "phx": 24, "phoenix": 24,
    # Portland Trail Blazers
    "portland trail blazers": 28, "trail blazers": 28, "blazers": 28, "por": 28, "portland": 28,
    # Sacramento Kings
    "sacramento kings": 19, "kings": 19, "sac": 19, "sacramento": 19,
    # San Antonio Spurs
    "san antonio spurs": 8, "spurs": 8, "sas": 8, "san antonio": 8,
    # Toronto Raptors
    "toronto raptors": 30, "raptors": 30, "tor": 30, "toronto": 30,
    # Utah Jazz
    "utah jazz": 3, "jazz": 3, "uta": 3, "utah": 3,
    # Washington Wizards
    "washington wizards": 29, "wizards": 29, "was": 29, "washington": 29,
}

def resolve_team(team_input: str | int) -> int | None:
    """
    Resolves a team input (ID or string name) to the canonical Team ID.
    Returns None if not found.
    """
    if isinstance(team_input, int):
        return team_input
    
    if isinstance(team_input, str):
        # Check if digit string
        if team_input.isdigit():
            return int(team_input)
        
        # Normalize string
        normalized = team_input.lower().strip()
        if normalized in TEAM_MAP:
            return TEAM_MAP[normalized]
    
    return None
