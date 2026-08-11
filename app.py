import datetime
import pandas as pd
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="MLB Hot Streak Dashboard", page_icon="⚾", layout="wide"
)

st.title("⚾ MLB Hot Streak Analytics Dashboard")
st.markdown(
    "Scans all active MLB players using official season metrics matching your"
    " exact performance thresholds."
)


@st.cache_data(ttl=3600)
def load_mlb_data():
  headers = {"User-Agent": "Mozilla/5.0"}

  # 1. Fetch Today's Schedule & Matchups
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

  # 2. Fetch Teams List
  teams_url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
  teams_resp = requests.get(teams_url, headers=headers)
  if teams_resp.status_code != 200:
    return pd.DataFrame()

  teams_data = teams_resp.json().get("teams", [])
  qualified_candidates = []

  # 3. Scan Rosters safely with error handling per team
  for team in teams_data:
    team_id = team.get("id")
    team_name = team.get("name")
    roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active&hydrate=person(stats(type=season,group=hitting))"

    try:
      roster_resp = requests.get(roster_url, headers=headers, timeout=5)
      if roster_resp.status_code != 200:
        continue

      roster_data = roster_resp.json().get("roster", [])
      for member in roster_data:
        person = member.get("person", {})
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

        # Exact Filters: AB >= 200, AVG >= .240, OBP >= .335, AVG > .300, OPS > .800
        if (
            ab >= 200
            and avg >= 0.240
            and obp >= 0.335
            and avg > 0.300
            and ops > 0.800
        ):
          qualified_candidates.append({
              "Player Name": name,
              "Team": team_name,
              "Next Matchup": team_matchups.get(team_name, "No Game Today"),
              "At Bats (AB)": ab,
              "Batting Avg (AVG)": round(avg, 3),
              "On-Base Pct (OBP)": round(obp, 3),
              "OPS": round(ops, 3),
          })
    except Exception:
      continue

  return pd.DataFrame(qualified_candidates)


# Streamlit UI Interface Execution
if st.button("🔄 Run / Refresh Scan"):
  with st.spinner("Fetching stable MLB data across all teams..."):
    df = load_mlb_data()
    st.session_state["df"] = df

if "df" in st.session_state:
  df = st.session_state["df"]
  if not df.empty:
    st.success(
        f"Scan complete! Found {len(df)} players matching your criteria."
    )
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Table as CSV",
        csv,
        "mlb_hot_streaks.csv",
        "text/csv",
        key="download-csv",
    )
  else:
    st.warning(
        "No players matched the criteria configuration right now. Try again"
        " later."
    )
else:
  st.info(
      "Click the **Run / Refresh Scan** button above to load your live web app"
      " data."
  )
