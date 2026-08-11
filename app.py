import datetime
import pandas as pd
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="MLB Hot Streak Dashboard", page_icon="⚾", layout="wide"
)

st.title("⚾ MLB Hot Streak & Last 7 Games Analyzer")
st.markdown(
    "Automatically scans all active MLB players, applies your performance criteria, and tracks their last 7-game trends."
)


@st.cache_data(ttl=3600)  # Caches data for 1 hour to keep it fast
def load_mlb_data():
  headers = {"User-Agent": "Mozilla/5.0"}

  # 1. Schedule & Matchups
  today_str = datetime.date.today().strftime("%Y-%m-%d")
  schedule_url = (
      f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today_str}"
  )
  sched_resp = requests.get(schedule_url, headers=headers)
  team_matchups = {}

  if sched_resp.status_code == 200:
    sched_data = sched_resp.json()
    if "dates" in sched_data and sched_data["dates"]:
      for game in sched_data["dates"][0].get("games", []):
        teams = game.get("teams", {})
        away_team = (
            teams.get("away", {}).get("team", {}).get("name", "Away")
        )
        home_team = teams.get("home", {}).get("team", {}).get("name", "Home")
        matchup_str = f"{away_team} @ {home_team}"
        team_matchups[away_team] = matchup_str
        team_matchups[home_team] = matchup_str

  # 2. Teams & Rosters
  teams_url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
  teams_resp = requests.get(teams_url, headers=headers)
  if teams_resp.status_code != 200:
    return pd.DataFrame()

  teams_data = teams_resp.json().get("teams", [])
  qualified_candidates = []

  for team in teams_data:
    team_id = team.get("id")
    team_name = team.get("name")
    roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active&hydrate=person(stats(type=season,group=hitting))"
    roster_resp = requests.get(roster_url, headers=headers)

    if roster_resp.status_code != 200:
      continue

    for member in roster_resp.json().get("roster", []):
      person = member.get("person", {})
      batter_id = person.get("id")
      name = person.get("fullName", "Unknown")

      stats_list = person.get("stats", [])
      if not stats_list:
        continue

      splits = stats_list[0].get("splits", [])
      if not splits:
        continue

      stat = splits[0].get("stat", {})
      try:
        ab = int(stat.get("atBats", 0))
        avg = float(stat.get("avg", 0.0))
        obp = float(stat.get("obp", 0.0))
        ops = float(stat.get("ops", 0.0))
      except (ValueError, TypeError):
        continue

      # Filters
      if ab >= 200 and avg >= 0.240 and obp >= 0.335 and avg > 0.300 and ops > 0.800:
        qualified_candidates.append({
            "batter_id": batter_id,
            "Name": name,
            "Team": team_name,
            "Matchup": team_matchups.get(team_name, "No Game Today"),
            "Season AB": ab,
            "Season AVG": round(avg, 3),
            "Season OBP": round(obp, 3),
            "Season OPS": round(ops, 3),
        })

  # 3. Last 7 Games Stats calculation
  final_results = []
  for player in qualified_candidates:
    gamelog_url = f"https://statsapi.mlb.com/api/v1/people/{player['batter_id']}/stats?stats=gameLog&group=hitting&season=2026"
    gl_resp = requests.get(gamelog_url, headers=headers)

    l7_avg, l7_obp, l7_ops, l7_ab = 0.0, 0.0, 0.0, 0
    if gl_resp.status_code == 200:
      gl_data = gl_resp.json().get("stats", [])
      if gl_data and gl_data[0].get("splits"):
        recent_games = gl_data[0]["splits"][-7:]
        t_ab, t_h, t_bb, t_hbp, t_sf, t_tb = 0, 0, 0, 0, 0, 0
        for g in recent_games:
          s = g.get("stat", {})
          t_ab += int(s.get("atBats", 0))
          t_h += int(s.get("hits", 0))
          t_bb += int(s.get("baseOnBalls", 0))
          t_hbp += int(s.get("hitByPitch", 0))
          t_sf += int(s.get("sacFlies", 0))
          t_tb += int(s.get("totalBases", 0))

        l7_ab = t_ab
        if t_ab > 0:
          l7_avg = t_h / t_ab
          l7_slg = t_tb / t_ab
          denom = t_ab + t_bb + t_hbp + t_sf
          l7_obp = (t_h + t_bb + t_hbp) / denom if denom > 0 else 0.0
          l7_ops = l7_obp + l7_slg

    final_results.append({
        "Player Name": player["Name"],
        "Team": player["Team"],
        "Next Matchup": player["Matchup"],
        "L7 AB": l7_ab,
        "L7 AVG": round(l7_avg, 3),
        "L7 OBP": round(l7_obp, 3),
        "L7 OPS": round(l7_ops, 3),
        "Season AB": player["Season AB"],
        "Season AVG": player["Season AVG"],
        "Season OBP": player["Season OBP"],
        "Season OPS": player["Season OPS"],
    })

  return pd.DataFrame(final_results)


# Button to load data inside the app
if st.button("🔄 Fetch / Refresh Data"):
  with st.spinner(
      "Scanning all 30 MLB teams and calculating recent trends..."
  ):
    df = load_mlb_data()
    st.session_state["df"] = df

if "df" in st.session_state:
  df = st.session_state["df"]
  if not df.empty:
    st.success(
        f"Successfully loaded {len(df)} players matching hot-streak criteria!"
    )
    st.dataframe(df, use_container_width=True)

    # Download button
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Data as CSV",
        csv,
        "mlb_hot_streaks.csv",
        "text/csv",
        key="download-csv",
    )
  else:
    st.warning("No players matched the criteria.")
else:
  st.info(
      "Click the button above to run the scan and generate your custom"
      " dashboard."
  )